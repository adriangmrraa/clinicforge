import React, { useState, useEffect } from 'react';
import { X, Calendar, User, Clock, FileText, DollarSign, Activity, AlertTriangle, Trash2, Check } from 'lucide-react';
import type { Appointment, Patient, Professional } from '../views/AgendaView';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

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
    const [activeTab, setActiveTab] = useState<TabType>('general');
    const [formData, setFormData] = useState({
        patient_id: '',
        professional_id: '',
        appointment_datetime: '',
        appointment_type: 'checkup',
        notes: '',
        duration_minutes: 30
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [collisionWarning, setCollisionWarning] = useState<string | null>(null);

    // Format date for datetime-local input: local YYYY-MM-DDTHH:mm (avoid UTC display bug)
    const toLocalDatetimeInput = (isoOrDate: string | Date): string => {
        const d = new Date(isoOrDate);
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    // Initialize form data
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
            setError(null);
            setCollisionWarning(null);
            setActiveTab('general');
        }
    }, [isOpen, initialData, professionals]);

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
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
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
                className={`fixed inset-y-0 right-0 z-[70] w-full md:w-[450px] bg-white/90 backdrop-blur-xl shadow-2xl transform transition-transform duration-300 ease-out border-l border-white/50 flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
            >
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-white/50">
                    <div>
                        <h2 className="text-xl font-bold text-slate-800">
                            {isEditing ? t('agenda.form_edit_appointment') : t('agenda.form_new_appointment')}
                        </h2>
                        <p className="text-xs text-slate-500">{t('agenda.clinical_inspector')}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="flex border-b border-gray-100 bg-white/50">
                    {renderTabButton('general', t('agenda.tab_general'), FileText)}
                    {renderTabButton('anamnesis', t('agenda.tab_anamnesis'), Activity)}
                    {renderTabButton('billing', t('agenda.tab_billing'), DollarSign)}
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {error && (
                        <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg flex items-center gap-2">
                            <AlertTriangle size={16} />
                            {error}
                        </div>
                    )}

                    {activeTab === 'general' && (
                        <div className="space-y-5">
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.patient')}</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                                    <select
                                        className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none cursor-pointer"
                                        value={formData.patient_id}
                                        onChange={(e) => handleChange('patient_id', e.target.value)}
                                        disabled={isEditing}
                                    >
                                        <option value="">{t('agenda.select_patient')}</option>
                                        {patients.map(p => (
                                            <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.professional')}</label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                                    <select
                                        className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none cursor-pointer"
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
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.date_time')}</label>
                                    <div className="relative">
                                        <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                                        <input
                                            type="datetime-local"
                                            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                                            value={formData.appointment_datetime}
                                            onChange={(e) => handleChange('appointment_datetime', e.target.value)}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.duration_min')}</label>
                                    <div className="relative">
                                        <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                                        <select
                                            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none"
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
                                <div className="p-3 bg-yellow-50 text-yellow-800 text-xs rounded-lg flex items-start gap-2 border border-yellow-100">
                                    <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
                                    <span>{collisionWarning}</span>
                                </div>
                            )}

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.appointment_type')}</label>
                                <div className="grid grid-cols-3 gap-2">
                                    {['checkup', 'cleaning', 'ortho', 'surgery', 'emergency'].map(type => (
                                        <button
                                            key={type}
                                            type="button"
                                            onClick={() => handleChange('appointment_type', type)}
                                            className={`px-3 py-2 text-xs font-medium rounded-lg border transition-all ${formData.appointment_type === type
                                                ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-sm'
                                                : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                                                }`}
                                        >
                                            {type.charAt(0).toUpperCase() + type.slice(1)}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.notes')}</label>
                                <textarea
                                    className="w-full p-3 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm min-h-[100px]"
                                    placeholder={t('agenda.notes_placeholder')}
                                    value={formData.notes}
                                    onChange={(e) => handleChange('notes', e.target.value)}
                                />
                            </div>
                        </div>
                    )}

                    {activeTab === 'anamnesis' && (
                        <div className="text-center py-10 text-gray-400">
                            <Activity size={48} className="mx-auto mb-3 opacity-20" />
                            <p className="text-sm">{t('agenda.medical_history_coming')}</p>
                        </div>
                    )}

                    {activeTab === 'billing' && (
                        <div className="text-center py-10 text-gray-400">
                            <DollarSign size={48} className="mx-auto mb-3 opacity-20" />
                            <p className="text-sm">{t('agenda.billing_coming')}</p>
                        </div>
                    )}
                </div>

                <div className="sticky bottom-0 bg-white/80 backdrop-blur-md border-t border-gray-100 p-4 flex items-center justify-between gap-4">
                    {isEditing && onDelete ? (
                        <button
                            type="button"
                            onClick={handleDelete}
                            className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        >
                            <Trash2 size={20} />
                        </button>
                    ) : <div />}

                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
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
