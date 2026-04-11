import React, { useState, useEffect, useRef, useMemo } from 'react';
import { X, Calendar, User, Clock, FileText, DollarSign, Activity, AlertTriangle, Trash2, Check, ExternalLink, Info, Search, Send } from 'lucide-react';
import type { Appointment, Patient, Professional } from '../views/AgendaView';
import api, { WS_URL } from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import AnamnesisPanel from './AnamnesisPanel';
import { io, Socket } from 'socket.io-client';
import { addMonths } from 'date-fns';

interface AppointmentFormProps {
    isOpen: boolean;
    onClose: () => void;
    initialData: Partial<Appointment>;
    professionals: Professional[];
    patients: Patient[];
    onSubmit: (data: any) => Promise<void>;
    onDelete?: (id: string) => Promise<void>;
    isEditing: boolean;
}

type TabType = 'general' | 'anamnesis' | 'billing';

export default function AppointmentForm({
    isOpen,
    onClose,
    initialData,
    professionals,
    patients,
    onSubmit,
    onDelete,
    isEditing
}: AppointmentFormProps) {
    const { t } = useTranslation();
    const { user } = useAuth();
    const [activeTab, setActiveTab] = useState<TabType>('general');
    const [formData, setFormData] = useState({
        patient_id: '',
        professional_id: '',
        appointment_datetime: '',
        appointment_type: 'checkup',
        notes: '',
        duration_minutes: 30
    });
    const [appointmentStatus, setAppointmentStatus] = useState<string>('scheduled');
    const [statusLoading, setStatusLoading] = useState(false);
    const [statusSuccess, setStatusSuccess] = useState<string | null>(null);
    const [treatmentCompleteLoading, setTreatmentCompleteLoading] = useState(false);
    const [treatmentCompleteResult, setTreatmentCompleteResult] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [collisionWarning, setCollisionWarning] = useState<string | null>(null);
    const [treatmentTypes, setTreatmentTypes] = useState<any[]>([]);
    const [anamnesisRefreshKey, setAnamnesisRefreshKey] = useState(0);
    const socketRef = useRef<Socket | null>(null);
    const [patientSearch, setPatientSearch] = useState('');
    const [patientDropdownOpen, setPatientDropdownOpen] = useState(false);
    const patientDropdownRef = useRef<HTMLDivElement>(null);
    const filteredPatients = useMemo(() => {
        if (!patientSearch.trim()) return patients.slice(0, 30);
        const q = patientSearch.toLowerCase();
        return patients.filter(p =>
            `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
            (p.phone_number || '').includes(q) ||
            (p.dni || '').includes(q)
        ).slice(0, 30);
    }, [patients, patientSearch]);

    // Billing state
    const [billingData, setBillingData] = useState({
        billing_amount: '',
        billing_installments: '',
        billing_notes: '',
        payment_status: 'pending',
    });
    const [billingSaving, setBillingSaving] = useState(false);
    const [billingSuccess, setBillingSuccess] = useState<string | null>(null);

    // Fetch treatment types
    // Close patient dropdown on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (patientDropdownRef.current && !patientDropdownRef.current.contains(e.target as Node)) {
                setPatientDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Reset search when modal opens with existing patient
    useEffect(() => {
        if (isOpen && formData.patient_id) {
            const p = patients.find(p => p.id.toString() === formData.patient_id);
            if (p) setPatientSearch(`${p.first_name} ${p.last_name}`);
        }
        if (!isOpen) setPatientSearch('');
    }, [isOpen, formData.patient_id, patients]);

    useEffect(() => {
        const fetchTreatmentTypes = async () => {
            try {
                const response = await api.get('/admin/treatment_types', {
                    params: { only_active: true }
                });
                setTreatmentTypes(response.data);
            } catch (err) {
                console.error('Error fetching treatment types:', err);
                // Fallback to basic types if request fails
                setTreatmentTypes([
                    { code: 'checkup', name: 'Consulta' },
                    { code: 'cleaning', name: 'Limpieza' },
                    { code: 'emergency', name: 'Urgencia' }
                ]);
            }
        };
        fetchTreatmentTypes();
    }, []);

    // Format date for datetime-local input: local YYYY-MM-DDTHH:mm (avoid UTC display bug)
    const toLocalDatetimeInput = (isoOrDate: string | Date): string => {
        const d = new Date(isoOrDate);
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    // Full appointment data (fetched fresh when modal opens, includes billing + receipt)
    const [fullAppointment, setFullAppointment] = useState<any>(null);

    // Initialize form data + fetch full appointment for billing/receipt
    useEffect(() => {
        if (isOpen) {
            setFormData({
                patient_id: initialData.patient_id?.toString() || '',
                professional_id: initialData.professional_id?.toString() || (professionals.length > 0 ? professionals[0].id.toString() : ''),
                appointment_datetime: initialData.appointment_datetime ? toLocalDatetimeInput(initialData.appointment_datetime) : '',
                appointment_type: initialData.appointment_type || 'checkup',
                notes: initialData.notes || '',
                duration_minutes: initialData.duration_minutes || 30
            });
            setAppointmentStatus((initialData as any).status || 'scheduled');
            setBillingSuccess(null);
            setStatusSuccess(null);
            setError(null);
            setCollisionWarning(null);
            setActiveTab('general');
            setFullAppointment(null);

            // Fetch full appointment data (billing, receipt, etc.) directly from API
            if (isEditing && initialData.id) {
                api.get(`/admin/appointments/${initialData.id}`)
                    .then(res => {
                        const apt = res.data;
                        setFullAppointment(apt);
                        // billing_amount = treatment base_price (the actual cost of the procedure)
                        // The seña (deposit) is shown separately in the receipt section
                        let amount = '';
                        // First priority: if billing_amount was manually set and is different from seña, use it
                        if (apt.billing_amount != null && apt.billing_amount > 0) {
                            amount = String(apt.billing_amount);
                        }
                        // Always try to use treatment base_price as the billing amount
                        // (overrides seña amount that may have been auto-set during booking)
                        if (apt.appointment_type && treatmentTypes.length > 0) {
                            const tt = treatmentTypes.find((t: any) => t.code === apt.appointment_type);
                            if (tt?.base_price && tt.base_price > 0) {
                                amount = String(tt.base_price);
                            }
                        }
                        setBillingData({
                            billing_amount: amount,
                            billing_installments: apt.billing_installments != null ? String(apt.billing_installments) : '1',
                            billing_notes: apt.billing_notes || '',
                            payment_status: apt.payment_status || 'pending',
                        });
                    })
                    .catch(() => {
                        // Fallback to initialData if individual fetch fails
                        setBillingData({
                            billing_amount: (initialData as any).billing_amount != null ? String((initialData as any).billing_amount) : '',
                            billing_installments: (initialData as any).billing_installments != null ? String((initialData as any).billing_installments) : '',
                            billing_notes: (initialData as any).billing_notes || '',
                            payment_status: (initialData as any).payment_status || 'pending',
                        });
                    });
            } else {
                setBillingData({
                    billing_amount: '',
                    billing_installments: '',
                    billing_notes: '',
                    payment_status: 'pending',
                });
            }
        }
    }, [isOpen, initialData, professionals, isEditing]);

    // Cambio de estado del turno (event-driven → dispara feedback si es 'completed')
    const handleStatusChange = async (newStatus: string) => {
        if (!initialData.id || !isEditing) return;
        setStatusLoading(true);
        setStatusSuccess(null);
        try {
            await api.patch(`/admin/appointments/${initialData.id}/status`, { status: newStatus });
            setAppointmentStatus(newStatus);
            setStatusSuccess(newStatus === 'completed' ? '✅ Turno completado. Feedback programado en 45 min.' : `✅ Estado actualizado a "${newStatus}".`);
            setTimeout(() => setStatusSuccess(null), 5000);
        } catch (e: any) {
            setError(e?.response?.data?.detail ?? 'Error al cambiar el estado.');
        } finally {
            setStatusLoading(false);
        }
    };


    // Finalizar tratamiento — envía HSM followup
    const handleCompleteTreatment = async () => {
        if (!initialData.id || !isEditing) return;
        setTreatmentCompleteLoading(true);
        setTreatmentCompleteResult(null);
        try {
            const { data } = await api.post(`/admin/appointments/${initialData.id}/complete-treatment`);
            setTreatmentCompleteResult(data.ok ? `✅ ${data.message}` : `⚠️ ${data.message}`);
            setTimeout(() => setTreatmentCompleteResult(null), 8000);
        } catch (e: any) {
            setTreatmentCompleteResult(`❌ ${e?.response?.data?.detail ?? 'Error al finalizar tratamiento'}`);
            setTimeout(() => setTreatmentCompleteResult(null), 8000);
        } finally {
            setTreatmentCompleteLoading(false);
        }
    };

    // Check collisions
    const checkCollisions = async (profId: string, dateStr: string) => {
        if (!profId || !dateStr) return;
        try {
            const response = await api.get('/admin/appointments/check-collisions', {
                params: {
                    professional_id: profId,
                    datetime_str: dateStr,
                    duration_minutes: formData.duration_minutes,
                    exclude_appointment_id: isEditing ? initialData.id : undefined
                }
            });

            if (response.data.has_collisions) {
                const conflicts = [];
                if (response.data.conflicting_appointments?.length) conflicts.push('Turno existente');
                if (response.data.conflicting_blocks?.length) conflicts.push('Bloqueo GCal');
                setCollisionWarning(`⚠️ Conflicto detectado: ${conflicts.join(', ')}`);
            } else {
                setCollisionWarning(null);
            }
        } catch (err) {
            console.error('Error checking collisions:', err);
        }
    };

    // Socket for real-time anamnesis refresh
    useEffect(() => {
        if (!isOpen) return;

        const jwtToken = localStorage.getItem('access_token');

        socketRef.current = io(WS_URL, {
            transports: ['websocket', 'polling'],
            auth: { token: jwtToken || '' },
        });

        socketRef.current.on('PATIENT_UPDATED', (payload: { patient_id?: number; phone?: string }) => {
            const currentPatientId = formData.patient_id ? parseInt(formData.patient_id) : null;
            const patientObj = patients.find(p => p.id.toString() === formData.patient_id);
            
            if (
                (payload.patient_id && payload.patient_id === currentPatientId) ||
                (payload.phone && patientObj?.phone_number === payload.phone)
            ) {
                setAnamnesisRefreshKey(prev => prev + 1);
            }
        });

        return () => {
            socketRef.current?.disconnect();
        };
    }, [isOpen, formData.patient_id, patients]);

    const handleChange = (field: string, value: any) => {
        setFormData(prev => {
            const newData = { ...prev, [field]: value };
            if (field === 'professional_id' || field === 'appointment_datetime' || field === 'duration_minutes') {
                checkCollisions(newData.professional_id || prev.professional_id, newData.appointment_datetime || prev.appointment_datetime);
            }
            return newData;
        });
    };

    const handleSubmit = async () => {
        if (!formData.patient_id || !formData.professional_id || !formData.appointment_datetime) {
            setError('Por favor complete los campos requeridos');
            return;
        }

        setLoading(true);
        try {
            // Send datetime as ISO so backend parses correctly (datetime-local gives local YYYY-MM-DDThh:mm)
            const payload = {
                ...formData,
                appointment_datetime: new Date(formData.appointment_datetime).toISOString(),
            };
            await onSubmit(payload);
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.message || 'Error al guardar');
        } finally {
            setLoading(false);
        }
    };

    const handleFollowup = () => {
        if (!formData.patient_id) return;
        
        // Calcular fecha + 6 meses
        const baseDate = formData.appointment_datetime ? new Date(formData.appointment_datetime) : new Date();
        const futureDate = addMonths(baseDate, 6);
        
        setFormData(prev => ({
            ...prev,
            appointment_datetime: toLocalDatetimeInput(futureDate),
            notes: (t('agenda.followup_notes_prefix') || '') + prev.notes
        }));
        
        // Forzar tab general para ver el cambio
        setActiveTab('general');
        setError(null);
        setCollisionWarning(null);
    };

    // Close on Escape key
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    if (!isOpen) return null;

    const handleDelete = async () => {
        if (!onDelete || !initialData.id) return;
        if (confirm(t('alerts.confirm_delete_appointment'))) {
            setLoading(true);
            try {
                await onDelete(initialData.id);
                onClose();
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        }
    };

    const renderTabButton = (id: TabType, label: string, icon: any) => (
        <button
            type="button"
            onClick={() => setActiveTab(id)}
            className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
        >
            {React.createElement(icon, { size: 16 })}
            {label}
        </button>
    );

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[60] transition-opacity duration-300"
                onClick={onClose}
            />

            {/* Slide-over Panel */}
            <div
                className={`fixed inset-y-0 right-0 z-[70] w-full md:w-[450px] bg-[#0d1117] backdrop-blur-xl shadow-2xl transform transition-transform duration-300 ease-out border-l border-white/[0.08] flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
            >
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-white/[0.02]">
                    <div>
                        <div className="flex items-center gap-2">
                            <h2 className="text-xl font-bold text-white">
                                {isEditing ? t('agenda.form_edit_appointment') : t('agenda.form_new_appointment')}
                            </h2>
                            {isEditing && (initialData as any).source && (() => {
                                const src = (initialData as any).source;
                                const sourceConfig: Record<string, { bg: string; text: string; label: string }> = {
                                    ai: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: t('agenda.source_ai') },
                                    nova: { bg: 'bg-purple-500/10', text: 'text-purple-400', label: t('agenda.source_nova') },
                                    manual: { bg: 'bg-green-500/10', text: 'text-green-400', label: t('agenda.source_manual') },
                                    gcalendar: { bg: 'bg-white/[0.06]', text: 'text-white/50', label: t('agenda.source_gcalendar') },
                                };
                                const cfg = sourceConfig[src] || sourceConfig.manual;
                                return (
                                    <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${cfg.bg} ${cfg.text}`}>
                                        {cfg.label}
                                    </span>
                                );
                            })()}
                        </div>
                        <p className="text-xs text-slate-500">{t('agenda.clinical_inspector')}</p>
                    </div>
                    <button onClick={onClose} aria-label="Cerrar" className="p-2 hover:bg-white/[0.06] rounded-full text-white/30 hover:text-white/60 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="flex border-b border-white/[0.06] bg-white/[0.02]">
                    {renderTabButton('general', t('agenda.tab_general'), FileText)}
                    {renderTabButton('anamnesis', t('agenda.tab_anamnesis'), Activity)}
                    {renderTabButton('billing', t('agenda.tab_billing'), DollarSign)}
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {error && (
                        <div className="p-3 bg-red-500/10 text-red-400 text-sm rounded-lg flex items-center gap-2 border border-red-500/20">
                            <AlertTriangle size={16} />
                            {error}
                        </div>
                    )}

                    {activeTab === 'general' && (
                        <div className="space-y-5">
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">{t('agenda.patient')}</label>
                                <div className="relative" ref={patientDropdownRef}>
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                                    {isEditing ? (
                                        <div className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm opacity-60">
                                            {patients.find(p => p.id.toString() === formData.patient_id)
                                                ? `${patients.find(p => p.id.toString() === formData.patient_id)!.first_name} ${patients.find(p => p.id.toString() === formData.patient_id)!.last_name}`
                                                : t('agenda.select_patient')}
                                        </div>
                                    ) : (
                                        <>
                                            <input
                                                type="text"
                                                className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 text-white focus:ring-0 transition-all text-sm"
                                                placeholder={t('agenda.select_patient')}
                                                value={patientSearch}
                                                onChange={(e) => {
                                                    setPatientSearch(e.target.value);
                                                    setPatientDropdownOpen(true);
                                                    if (!e.target.value) handleChange('patient_id', '');
                                                }}
                                                onFocus={() => setPatientDropdownOpen(true)}
                                            />
                                            {formData.patient_id && !patientDropdownOpen && (
                                                <button
                                                    type="button"
                                                    onClick={() => { setPatientSearch(''); handleChange('patient_id', ''); }}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60"
                                                >
                                                    <X size={14} />
                                                </button>
                                            )}
                                            {patientDropdownOpen && (
                                                <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto bg-[#0d1117] border border-white/[0.08] rounded-lg shadow-xl">
                                                    {filteredPatients.length === 0 ? (
                                                        <div className="px-4 py-3 text-sm text-white/30">Sin resultados</div>
                                                    ) : (
                                                        filteredPatients.map(p => (
                                                            <button
                                                                key={p.id}
                                                                type="button"
                                                                className={`w-full px-4 py-2.5 text-left text-sm hover:bg-white/[0.06] transition-colors flex items-center justify-between ${formData.patient_id === p.id.toString() ? 'bg-blue-500/10 text-blue-400' : 'text-white'}`}
                                                                onClick={() => {
                                                                    handleChange('patient_id', p.id.toString());
                                                                    setPatientSearch(`${p.first_name} ${p.last_name}`);
                                                                    setPatientDropdownOpen(false);
                                                                }}
                                                            >
                                                                <span>{p.first_name} {p.last_name}</span>
                                                                {p.phone_number && <span className="text-xs text-white/30">{p.phone_number}</span>}
                                                            </button>
                                                        ))
                                                    )}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">{t('agenda.professional')}</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                                    <select
                                        className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 text-white focus:ring-0 transition-all text-sm appearance-none cursor-pointer"
                                        value={formData.professional_id}
                                        onChange={(e) => handleChange('professional_id', e.target.value)}
                                    >
                                        <option value="">{t('agenda.select_professional')}</option>
                                        {professionals.map(p => (
                                            <option key={p.id} value={p.id}>Dr. {p.first_name} {p.last_name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">{t('agenda.date_time')}</label>
                                    <div className="relative">
                                        <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                                        <input
                                            type="datetime-local"
                                            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 text-white focus:ring-0 transition-all text-sm"
                                            value={formData.appointment_datetime}
                                            onChange={(e) => handleChange('appointment_datetime', e.target.value)}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">{t('agenda.duration_min')}</label>
                                    <div className="relative">
                                        <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                                        <select
                                            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 text-white focus:ring-0 transition-all text-sm appearance-none"
                                            value={formData.duration_minutes}
                                            onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value))}
                                        >
                                            <option value="15">15 min</option>
                                            <option value="30">30 min</option>
                                            <option value="45">45 min</option>
                                            <option value="60">60 min</option>
                                            <option value="90">90 min</option>
                                            <option value="120">2 horas</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            {collisionWarning && (
                                <div className="p-3 bg-yellow-500/10 text-yellow-400 text-xs rounded-lg flex items-start gap-2 border border-yellow-500/20">
                                    <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
                                    <span>{collisionWarning}</span>
                                </div>
                            )}

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">
                                    {t('agenda.appointment_type')}
                                </label>
                                <div className="grid grid-cols-2 gap-2">
                                    {treatmentTypes.map(s => (
                                        <button
                                            key={s.code}
                                            type="button"
                                            onClick={() => {
                                                handleChange('appointment_type', s.code);
                                                // Auto-fill billing amount with treatment base_price
                                                if (s.base_price && s.base_price > 0) {
                                                    setBillingData(prev => ({
                                                        ...prev,
                                                        billing_amount: String(s.base_price),
                                                    }));
                                                }
                                            }}
                                            className={`px-3 py-2 text-xs font-medium rounded-lg border transition-all ${formData.appointment_type === s.code
                                                ? 'bg-blue-500/15 border-blue-500/30 text-blue-400 shadow-sm'
                                                : 'bg-white/[0.04] border-white/[0.08] text-white/50 hover:bg-white/[0.06]'
                                                }`}
                                        >
                                            {s.name}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Estado del turno — solo en edición */}
                            {isEditing && (
                                <div className="space-y-2 p-4 bg-white/[0.03] rounded-xl border border-white/[0.06]">
                                    <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{t('agenda.appointment_status')}</label>
                                    <p className="text-xs text-slate-400">{t('agenda.status_completed_hint')}</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        {[
                                            { value: 'scheduled', label: `📅 ${t('agenda.status_scheduled')}`, color: 'blue' },
                                            { value: 'confirmed', label: `✅ ${t('agenda.status_confirmed')}`, color: 'green' },
                                            { value: 'completed', label: `🏁 ${t('agenda.status_completed')}`, color: 'purple' },
                                            { value: 'cancelled', label: `❌ ${t('agenda.status_cancelled')}`, color: 'red' },
                                            { value: 'no_show', label: `👻 ${t('agenda.status_no_show')}`, color: 'gray' },
                                        ].map(s => (
                                            <button
                                                key={s.value}
                                                type="button"
                                                disabled={statusLoading}
                                                onClick={() => handleStatusChange(s.value)}
                                                className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${
                                                    appointmentStatus === s.value
                                                        ? 'bg-indigo-600 border-indigo-600 text-white shadow-sm'
                                                        : 'bg-white/[0.04] border-white/[0.08] text-white/50 hover:bg-white/[0.06]'
                                                } ${statusLoading ? 'opacity-50 cursor-wait' : ''}`}
                                            >
                                                {s.label}
                                            </button>
                                        ))}
                                    </div>
                                    {statusSuccess && (
                                        <p className="text-xs text-emerald-600 font-medium mt-1">{statusSuccess}</p>
                                    )}

                                    {/* Finalizar Tratamiento — solo visible cuando el turno está completado */}
                                    {appointmentStatus === 'completed' && (
                                        <div className="mt-3 pt-3 border-t border-white/[0.06]">
                                            <button
                                                type="button"
                                                disabled={treatmentCompleteLoading}
                                                onClick={handleCompleteTreatment}
                                                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold transition-all ${
                                                    treatmentCompleteLoading
                                                        ? 'bg-purple-500/10 text-purple-300/50 cursor-wait'
                                                        : 'bg-purple-500/15 text-purple-300 border border-purple-500/20 hover:bg-purple-500/25'
                                                }`}
                                            >
                                                {treatmentCompleteLoading ? (
                                                    <div className="w-4 h-4 border-2 border-purple-300/30 border-t-purple-300 rounded-full animate-spin" />
                                                ) : (
                                                    <Send size={14} />
                                                )}
                                                {t('agenda.complete_treatment')}
                                            </button>
                                            <p className="text-[10px] text-white/30 mt-1 text-center">{t('agenda.complete_treatment_hint')}</p>
                                            {treatmentCompleteResult && (
                                                <p className="text-xs font-medium mt-1 text-center">{treatmentCompleteResult}</p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}


                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-white/40 uppercase tracking-wider">{t('agenda.notes')}</label>
                                <textarea
                                    className="w-full p-3 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 text-white focus:ring-0 transition-all text-sm min-h-[100px]"
                                    placeholder={t('agenda.notes_placeholder')}
                                    value={formData.notes}
                                    onChange={(e) => handleChange('notes', e.target.value)}
                                />
                            </div>
                        </div>
                    )}

                    {activeTab === 'anamnesis' && (
                        formData.patient_id ? (
                             <AnamnesisPanel
                                patientId={parseInt(formData.patient_id)}
                                userRole={(user as any)?.role}
                                compact={false}
                                refreshKey={anamnesisRefreshKey}
                            />
                        ) : (
                            <div className="text-center py-10 text-white/30">
                                <Activity size={48} className="mx-auto mb-3 opacity-20" />
                                <p className="text-sm">{t('agenda.select_patient_anamnesis')}</p>
                            </div>
                        )
                    )}

                    {activeTab === 'billing' && (
                        <div className="space-y-4 p-1">
                            {!isEditing ? (
                                <div className="text-center py-10 text-white/30">
                                    <DollarSign size={48} className="mx-auto mb-3 opacity-20" />
                                    <p className="text-sm">{t('agenda.billing_save_first')}</p>
                                </div>
                            ) : fullAppointment?.plan_item_id ? (
                                /* ── Read-only billing: appointment linked to treatment plan ── */
                                <div className="space-y-4">
                                    {/* Info banner */}
                                    <div className="rounded-xl border border-blue-500/20 bg-blue-500/[0.07] p-4 space-y-3">
                                        <div className="flex items-start gap-3">
                                            <Info size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
                                            <div className="space-y-1">
                                                <p className="text-sm font-semibold text-blue-300">
                                                    {t('billing.linked_to_plan')}
                                                </p>
                                                {fullAppointment?.plan_name && (
                                                    <p className="text-xs text-blue-400/70">
                                                        {fullAppointment.plan_name}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Read-only billing summary */}
                                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 space-y-3">
                                        <h4 className="text-xs font-bold text-white/40 uppercase tracking-wider">
                                            {t('agenda.tab_billing')}
                                        </h4>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div className="space-y-1">
                                                <span className="text-[11px] text-white/40">{t('agenda.appointment_type')}</span>
                                                <p className="text-sm font-medium text-white">
                                                    {fullAppointment?.appointment_name || formData.appointment_type}
                                                </p>
                                            </div>
                                            <div className="space-y-1">
                                                <span className="text-[11px] text-white/40">{t('agenda.billing_amount')}</span>
                                                <p className="text-sm font-medium text-white">
                                                    {billingData.billing_amount ? `$${Number(billingData.billing_amount).toLocaleString('es-AR')}` : '—'}
                                                </p>
                                            </div>
                                            <div className="space-y-1 col-span-2">
                                                <span className="text-[11px] text-white/40">{t('agenda.payment_status')}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className={`inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-full ${
                                                        billingData.payment_status === 'paid'
                                                            ? 'bg-green-500/15 text-green-400 border border-green-500/20'
                                                            : billingData.payment_status === 'partial'
                                                            ? 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/20'
                                                            : 'bg-white/[0.06] text-white/50 border border-white/[0.08]'
                                                    }`}>
                                                        {t(`agenda.payment_${billingData.payment_status}`)}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Navigate to plan button */}
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const patientId = fullAppointment?.patient_id || formData.patient_id;
                                            if (patientId) {
                                                onClose();
                                                window.location.href = `/pacientes/${patientId}?tab=billing`;
                                            }
                                        }}
                                        className="w-full px-4 py-3 text-sm font-semibold text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 hover:border-blue-500/30 rounded-xl transition-all flex items-center justify-center gap-2"
                                    >
                                        <ExternalLink size={16} />
                                        {t('billing.view_plan')}
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <label className="text-xs font-semibold text-white/50">{t('agenda.billing_amount')}</label>
                                            <div className="relative">
                                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-sm">$</span>
                                                <input type="number" step="0.01" min="0" placeholder="0.00"
                                                    className="w-full pl-7 pr-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm text-white"
                                                    value={billingData.billing_amount}
                                                    onChange={(e) => setBillingData(prev => ({ ...prev, billing_amount: e.target.value }))} />
                                            </div>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs font-semibold text-white/50">{t('agenda.billing_installments')}</label>
                                            <input type="number" min="1" max="48" placeholder="1"
                                                className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm text-white"
                                                value={billingData.billing_installments}
                                                onChange={(e) => setBillingData(prev => ({ ...prev, billing_installments: e.target.value }))} />
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-semibold text-white/50">{t('agenda.billing_notes')}</label>
                                        <textarea rows={3} placeholder={t('agenda.billing_notes_placeholder')}
                                            className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm text-white resize-none"
                                            value={billingData.billing_notes}
                                            onChange={(e) => setBillingData(prev => ({ ...prev, billing_notes: e.target.value }))} />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-semibold text-white/50">{t('agenda.payment_status')}</label>
                                        <div className="flex gap-2">
                                            {(['pending', 'partial', 'paid'] as const).map((ps) => (
                                                <button key={ps} type="button"
                                                    onClick={() => setBillingData(prev => ({ ...prev, payment_status: ps }))}
                                                    className={`px-4 py-2 text-xs font-semibold rounded-lg border transition-colors ${
                                                        billingData.payment_status === ps
                                                            ? ps === 'paid' ? 'bg-green-100 border-green-300 text-green-700'
                                                              : ps === 'partial' ? 'bg-yellow-100 border-yellow-300 text-yellow-700'
                                                              : 'bg-white/[0.04] border-white/[0.08] text-white/50'
                                                            : 'bg-white/[0.04] border-white/[0.08] text-white/50 hover:bg-white/[0.06]'
                                                    }`}>
                                                    {t(`agenda.payment_${ps}`)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    {/* Payment Receipt Section */}
                                    {(() => {
                                        try {
                                            const raw = fullAppointment?.payment_receipt_data || (initialData as any)?.payment_receipt_data;
                                            if (!raw) return null;
                                            const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
                                            if (!parsed || typeof parsed !== 'object') return null;
                                            const isVerified = parsed.status === 'verified' || parsed.status === 'verified_manual';
                                            const isPendingReview = parsed.status === 'pending_review';
                                            const filePath = parsed.receipt_file_path || '';
                                            const apiBase = import.meta.env.VITE_API_URL || '';
                                            const docId = parsed.receipt_doc_id;
                                            const patientId = (initialData as any)?.patient_id || fullAppointment?.patient_id;
                                            const imgSrc = docId && patientId
                                                ? `${apiBase}/admin/patients/${patientId}/documents/${docId}/proxy`
                                                : filePath ? (filePath.startsWith('http') ? filePath : `${apiBase}${filePath.startsWith('/') ? '' : '/'}${filePath}`) : '';
                                            return (
                                                <div className={`rounded-xl border p-4 space-y-3 mt-4 ${isVerified ? 'bg-emerald-500/10 border-emerald-500/20' : isPendingReview ? 'bg-amber-500/10 border-amber-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
                                                    <div className="flex items-center justify-between">
                                                        <h4 className="text-xs font-bold text-white/70 flex items-center gap-1.5">
                                                            <DollarSign size={14} className={isVerified ? 'text-emerald-400' : isPendingReview ? 'text-amber-400' : 'text-red-400'} /> Comprobante de pago
                                                        </h4>
                                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${isVerified ? 'bg-emerald-500/20 text-emerald-400' : isPendingReview ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'}`}>
                                                            {parsed.status === 'verified_manual' ? '✅ Aprobado manual' : isVerified ? '✅ Verificado' : isPendingReview ? '🔍 Pendiente de revisión' : '⚠️ No verificado'}
                                                        </span>
                                                    </div>
                                                    {imgSrc && (
                                                        <div className="rounded-lg overflow-hidden border border-white/[0.08] bg-white/[0.04]">
                                                            <img
                                                                src={imgSrc}
                                                                alt="Comprobante"
                                                                className="w-full max-h-48 object-contain cursor-pointer hover:opacity-90 transition-opacity"
                                                                onClick={() => window.open(imgSrc, '_blank')}
                                                                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                                            />
                                                        </div>
                                                    )}
                                                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                                                        {parsed.amount_detected && (
                                                            <div>
                                                                <span className="text-white/40">Monto detectado:</span>
                                                                <span className="ml-1 font-semibold text-white">${parsed.amount_detected}</span>
                                                            </div>
                                                        )}
                                                        {parsed.amount_expected && (
                                                            <div>
                                                                <span className="text-white/40">Monto esperado:</span>
                                                                <span className="ml-1 font-semibold text-white">${Math.round(parsed.amount_expected).toLocaleString('es-AR')}</span>
                                                            </div>
                                                        )}
                                                        {parsed.total_paid > 0 && (
                                                            <div>
                                                                <span className="text-white/40">Total pagado:</span>
                                                                <span className="ml-1 font-semibold text-emerald-400">${Math.round(parsed.total_paid).toLocaleString('es-AR')}</span>
                                                            </div>
                                                        )}
                                                        {parsed.overpaid > 0 && (
                                                            <div>
                                                                <span className="text-white/40">Excedente:</span>
                                                                <span className="ml-1 font-semibold text-amber-400">${Math.round(parsed.overpaid).toLocaleString('es-AR')}</span>
                                                            </div>
                                                        )}
                                                        {parsed.verified_at && (
                                                            <div className="col-span-2">
                                                                <span className="text-white/40">Verificado:</span>
                                                                <span className="ml-1 font-semibold text-white/70">{new Date(parsed.verified_at).toLocaleString('es-AR')}</span>
                                                            </div>
                                                        )}
                                                        {parsed.holder_match === false && (
                                                            <div className="col-span-2">
                                                                <span className="text-red-400 text-[10px]">⚠ Titular no coincide con datos bancarios de la clínica</span>
                                                            </div>
                                                        )}
                                                        {parsed.failure_reason && (
                                                            <div className="col-span-2">
                                                                <span className="text-amber-400 text-[10px]">Motivo: {parsed.failure_reason === 'holder_mismatch' ? 'Titular no coincide' : parsed.failure_reason === 'amount_underpaid' ? 'Monto insuficiente' : 'Verificación automática fallida'}</span>
                                                            </div>
                                                        )}
                                                        {parsed.submitted_at && !parsed.verified_at && (
                                                            <div className="col-span-2">
                                                                <span className="text-white/40">Enviado:</span>
                                                                <span className="ml-1 font-semibold text-white/70">{new Date(parsed.submitted_at).toLocaleString('es-AR')}</span>
                                                            </div>
                                                        )}
                                                        {parsed.manually_approved_by && (
                                                            <div className="col-span-2">
                                                                <span className="text-white/40">Aprobado por:</span>
                                                                <span className="ml-1 font-semibold text-emerald-400">{parsed.manually_approved_by}</span>
                                                                {parsed.manually_approved_at && (
                                                                    <span className="ml-1 text-white/40">({new Date(parsed.manually_approved_at).toLocaleString('es-AR')})</span>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                    {isPendingReview && (
                                                        <button
                                                            type="button"
                                                            className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-2.5 px-4 rounded-lg transition-colors"
                                                            onClick={async () => {
                                                                try {
                                                                    const aptId = (initialData as any)?.id || fullAppointment?.id;
                                                                    await api.post(`/admin/appointments/${aptId}/approve-payment`);
                                                                    // Refresh the appointment data
                                                                    if (aptId) {
                                                                        const resp = await api.get(`/admin/appointments/${aptId}`);
                                                                        setFullAppointment(resp.data);
                                                                    }
                                                                } catch (err) {
                                                                    console.error('Error approving payment:', err);
                                                                }
                                                            }}
                                                        >
                                                            ✅ Aprobar pago manualmente
                                                        </button>
                                                    )}
                                                </div>
                                            );
                                        } catch { return null; }
                                    })()}

                                    {billingSuccess && (
                                        <div className="flex items-center gap-2 text-green-400 text-xs bg-green-500/10 px-3 py-2 rounded-lg">
                                            <Check size={14} /> {billingSuccess}
                                        </div>
                                    )}
                                    <button type="button"
                                        disabled={billingSaving}
                                        onClick={async () => {
                                            if (!initialData.id) return;
                                            setBillingSaving(true);
                                            setBillingSuccess(null);
                                            try {
                                                await api.put(`/admin/appointments/${initialData.id}/billing`, {
                                                    billing_amount: billingData.billing_amount ? parseFloat(billingData.billing_amount) : null,
                                                    billing_installments: billingData.billing_installments ? parseInt(billingData.billing_installments) : null,
                                                    billing_notes: billingData.billing_notes || null,
                                                    payment_status: billingData.payment_status,
                                                });
                                                setBillingSuccess(t('agenda.billing_saved'));
                                                setTimeout(() => setBillingSuccess(null), 3000);
                                            } catch (err) {
                                                console.error('Error saving billing:', err);
                                            } finally {
                                                setBillingSaving(false);
                                            }
                                        }}
                                        className="w-full px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 rounded-lg shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center gap-2">
                                        {billingSaving ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <DollarSign size={16} />}
                                        {t('agenda.billing_save')}
                                    </button>
                                </>
                            )}
                        </div>
                    )}
                </div>

                <div className="sticky bottom-0 bg-[#0d1117]/90 backdrop-blur-md border-t border-white/[0.06] p-4 flex items-center justify-between gap-4">
                    {isEditing && onDelete ? (
                        <button
                            type="button"
                            onClick={handleDelete}
                            className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                        >
                            <Trash2 size={20} />
                        </button>
                    ) : (
                        formData.patient_id && (
                            <button
                                type="button"
                                onClick={handleFollowup}
                                className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 rounded-lg transition-colors border border-blue-500/20"
                            >
                                <Calendar size={14} />
                                {t('agenda.schedule_followup')}
                            </button>
                        )
                    )}

                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-white/50 hover:bg-white/[0.06] rounded-lg transition-colors"
                        >
                            {t('common.cancel')}
                        </button>
                        <button
                            type="button"
                            onClick={handleSubmit}
                            disabled={loading}
                            className={`px-6 py-2 text-sm font-medium text-white rounded-lg shadow-lg shadow-blue-500/30 flex items-center gap-2 transition-all ${loading ? 'bg-blue-400 cursor-not-allowed' : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 hover:scale-[1.02]'
                                }`}
                        >
                            {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Check size={16} />}
                            {isEditing ? t('common.save_changes') : t('agenda.schedule_appointment')}
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
}
