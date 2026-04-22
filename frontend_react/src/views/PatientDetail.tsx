import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, User, Phone, Mail, AlertTriangle,
  FileText, Plus, Activity, Heart, Pill, Stethoscope, Megaphone,
  ClipboardList, History, Folder, X, HeartPulse, Link, Check, Copy, Receipt, Send
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import Odontogram from '../components/Odontogram';
import AttachmentSummaryCard from '../components/AttachmentSummaryCard';
import DocumentGallery from '../components/DocumentGallery';
import AnamnesisPanel from '../components/AnamnesisPanel';
import DigitalRecordsTab from '../components/DigitalRecordsTab';
import BillingTab from '../components/BillingTab';
import { getSocket } from '../services/socket';
import type { Socket } from 'socket.io-client';

interface Patient {
  id: number;
  first_name: string;
  last_name?: string;
  phone_number: string;
  email?: string;
  dni?: string;
  obra_social?: string;
  obra_social_number?: string;
  birth_date?: string;
  city?: string;
  insurance_provider?: string | null;
  created_at: string;
  status?: string;
  medical_notes?: string;
  acquisition_source?: string;
  meta_ad_id?: string;
  meta_ad_headline?: string;
  meta_campaign_id?: string;
  next_appointment_date?: string;
  last_visit?: string;
  pending_balance?: number;
  anamnesis_token?: string;
  patient_source?: string;
}

interface ClinicalRecord {
  id: number;
  patient_id?: number;
  professional_id?: number;
  professional_name?: string;
  appointment_id?: number;
  record_type?: string;
  chief_complaint?: string;
  diagnosis?: string;
  treatment_plan?: any;
  notes?: string;
  created_at: string;
  odontogram_data?: any;
}
interface AttachmentSummary {
  summary_text: string;
  attachments_count: number;
  attachments_types: string[];
  created_at: string;
}


const criticalConditions = [
  'diabetes', 'hipertension', 'cardiopatia', 'hemofilia',
  'alergia penicilina', 'embarazo', ' anticoagulacion',
  'vih', 'hepatitis', 'asma severa'
];

type TabType = 'summary' | 'history' | 'documents' | 'anamnesis' | 'digital_records' | 'billing';

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t, language } = useTranslation();
  const dateLocale = language === 'es' ? 'es-AR' : language === 'fr' ? 'fr-FR' : 'en-US';
  const [patient, setPatient] = useState<Patient | null>(null);
  const [records, setRecords] = useState<ClinicalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [criticalConditionsFound, setCriticalConditionsFound] = useState<string[]>([]);
  const [linkCopied, setLinkCopied] = useState(false);
  const initialTab = (searchParams.get('tab') as TabType) || 'summary';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const { user } = useAuth();
  const idRef = useRef<string | undefined>(id);
  const socketRef = useRef<Socket | null>(null);
  /** Debounce timer for RECORD_UPDATED socket events — coalesces Nova rapid-fire updates */
  const patientRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Treatment completion state
  interface CompletedTreatment {
    appointment_id: string;
    appointment_type: string;
    treatment_name: string;
    appointment_date: string;
    followup_sent: boolean;
  }
  const [completedTreatments, setCompletedTreatments] = useState<CompletedTreatment[]>([]);
  const [treatmentCompleteLoading, setTreatmentCompleteLoading] = useState<string | null>(null);
  const [treatmentCompleteResult, setTreatmentCompleteResult] = useState<Record<string, string>>({});

  const fetchCompletedTreatments = useCallback(async () => {
    if (!id) return;
    try {
      const { data } = await api.get('/admin/appointments', {
        params: { patient_id: id, status: 'completed', limit: 20 }
      });
      const apts = (data.appointments || data || [])
        .filter((a: any) => a.appointment_type && a.status === 'completed')
        .map((a: any) => ({
          appointment_id: a.id,
          appointment_type: a.appointment_type,
          treatment_name: a.treatment_name || a.appointment_type,
          appointment_date: a.appointment_datetime
            ? new Date(a.appointment_datetime).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
            : '',
          followup_sent: a.followup_sent || false,
        }));
      setCompletedTreatments(apts);
    } catch { /* silent */ }
  }, [id]);

  const handleCompleteTreatmentFromDetail = async (appointmentId: string) => {
    setTreatmentCompleteLoading(appointmentId);
    try {
      const { data } = await api.post(`/admin/appointments/${appointmentId}/complete-treatment`);
      setTreatmentCompleteResult(prev => ({
        ...prev,
        [appointmentId]: data.ok ? `✅ ${data.message}` : `⚠️ ${data.message}`,
      }));
      fetchCompletedTreatments();
    } catch (e: any) {
      setTreatmentCompleteResult(prev => ({
        ...prev,
        [appointmentId]: `❌ ${e?.response?.data?.detail ?? 'Error'}`,
      }));
    } finally {
      setTreatmentCompleteLoading(null);
    }
  };
  const [anamnesisRefreshKey, setAnamnesisRefreshKey] = useState(0);
  const [digitalRecordsRefreshKey, setDigitalRecordsRefreshKey] = useState(0);
  const [billingRefreshKey, setBillingRefreshKey] = useState(0);
  const [attachmentSummary, setAttachmentSummary] = useState<AttachmentSummary | null>(null);

  const [formData, setFormData] = useState({
    record_type: 'evolution',
    chief_complaint: '',
    diagnosis: '',
    treatment_plan: '',
    notes: '',
  });

  useEffect(() => {
    if (id) {
      setPatient(null);
      setRecords([]);
      setCriticalConditionsFound([]);
      fetchPatientData();
      fetchCompletedTreatments();
    }
  }, [id]);

  useEffect(() => {
    idRef.current = id;
  });

  const fetchPatientData = async () => {
    const fetchForId = id;
    if (!fetchForId) return;
    try {
      setLoading(true);
      const [patientRes, recordsRes] = await Promise.all([
        api.get(`/admin/patients/${fetchForId}`),
        api.get(`/admin/patients/${fetchForId}/records`),
      ]);
      if (idRef.current !== fetchForId) return;
      setPatient(patientRes.data);
      setRecords(Array.isArray(recordsRes.data) ? recordsRes.data : []);
      const notes = patientRes.data?.medical_notes || patientRes.data?.notes || '';
      if (notes) {
        setCriticalConditionsFound(
          criticalConditions.filter(c => notes.toLowerCase().includes(c.toLowerCase()))
        );
      }
    } catch (error: any) {
      if (idRef.current === fetchForId) {
        console.error('Error fetching patient data:', error);
        // Don't crash the page on 429 — show what we have
        if (error?.response?.status !== 429) {
          setPatient(null);
        }
      }
    } finally {
      if (idRef.current === fetchForId) setLoading(false);
    }
  };

  useEffect(() => {
    socketRef.current = getSocket();

    socketRef.current.on('PATIENT_UPDATED', (payload: { patient_id?: number; phone?: string }) => {
      // Si el evento coincide con el paciente actual, refrescar AnamnesisPanel
      const currentPatientId = id ? parseInt(id) : null;
      if (
        (payload.patient_id && payload.patient_id === currentPatientId) ||
        (payload.phone && patient?.phone_number === payload.phone)
      ) {
        setAnamnesisRefreshKey(prev => prev + 1);
      }
    });

    // ODONTOGRAM_UPDATED is handled directly by the Odontogram component via its own socket listener.
    // No page reload needed — the component updates in real-time with animations.

    socketRef.current.on('DIGITAL_RECORD_CREATED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (payload.patient_id && payload.patient_id === currentPatientId) {
        setDigitalRecordsRefreshKey(prev => prev + 1);
      }
    });

    socketRef.current.on('DIGITAL_RECORD_SENT', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (payload.patient_id && payload.patient_id === currentPatientId) {
        setDigitalRecordsRefreshKey(prev => prev + 1);
      }
    });

    socketRef.current.on('TREATMENT_PLAN_UPDATED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (payload.patient_id && payload.patient_id === currentPatientId) {
        setBillingRefreshKey(prev => prev + 1);
      }
    });

    socketRef.current.on('BILLING_UPDATED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (payload.patient_id && payload.patient_id === currentPatientId) {
        setBillingRefreshKey(prev => prev + 1);
      }
    });

    // Nova CRUD/odontogram updates — refresh all tabs for this patient (debounced to avoid rapid-fire refetches)
    socketRef.current.on('RECORD_UPDATED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (!payload.patient_id || payload.patient_id === currentPatientId) {
        if (patientRefreshTimer.current) clearTimeout(patientRefreshTimer.current);
        patientRefreshTimer.current = setTimeout(() => {
          fetchPatientData();
          setBillingRefreshKey(prev => prev + 1);
          setDigitalRecordsRefreshKey(prev => prev + 1);
        }, 2000);
      }
    });

    socketRef.current.on('ODONTOGRAM_UPDATED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (payload.patient_id && payload.patient_id === currentPatientId) {
        if (patientRefreshTimer.current) clearTimeout(patientRefreshTimer.current);
        patientRefreshTimer.current = setTimeout(() => {
          fetchPatientData();
        }, 2000);
      }
    });

    socketRef.current.on('PAYMENT_CONFIRMED', (payload: { patient_id?: number }) => {
      const currentPatientId = id ? parseInt(id) : null;
      if (!payload.patient_id || payload.patient_id === currentPatientId) {
        setBillingRefreshKey(prev => prev + 1);
      }
    });

    return () => {
      // Remove event handlers only — do NOT disconnect the singleton
      if (socketRef.current) {
        socketRef.current.off('PATIENT_UPDATED');
        socketRef.current.off('DIGITAL_RECORD_CREATED');
        socketRef.current.off('DIGITAL_RECORD_SENT');
        socketRef.current.off('TREATMENT_PLAN_UPDATED');
        socketRef.current.off('BILLING_UPDATED');
        socketRef.current.off('RECORD_UPDATED');
        socketRef.current.off('ODONTOGRAM_UPDATED');
        socketRef.current.off('PAYMENT_CONFIRMED');
      }
      if (patientRefreshTimer.current) clearTimeout(patientRefreshTimer.current);
    };
  }, [id, patient?.phone_number]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        patient_id: parseInt(id!),
        record_type: formData.record_type,
        chief_complaint: formData.chief_complaint,
        diagnosis: formData.diagnosis,
        treatment_plan: formData.treatment_plan,
        notes: formData.notes,
      };

      await api.post(`/admin/patients/${id}/records`, payload);
      fetchPatientData();
      setShowNoteForm(false);
      setFormData({
        record_type: 'evolution',
        chief_complaint: '',
        diagnosis: '',
        treatment_plan: '',
        notes: '',
      });
    } catch (error) {
      console.error('Error saving clinical record:', error);
      alert(t('alerts.error_save_record'));
    }
  };

  const getRecordIcon = (type: string) => {
    switch (type) {
      case 'initial': return <Stethoscope className="text-blue-500" size={18} />;
      case 'evolution': return <Activity className="text-green-500" size={18} />;
      case 'procedure': return <Heart className="text-purple-500" size={18} />;
      case 'prescription': return <Pill className="text-orange-500" size={18} />;
      default: return <FileText className="text-white/40" size={18} />;
    }
  };

  const getRecordTypeLabel = (type: string) => {
    if (!type) return '';
    const keyMap: Record<string, string> = {
      initial: 'initial_consult',
      evolution: 'evolution',
      procedure: 'procedure',
      prescription: 'prescription'
    };
    const key = keyMap[type] || type;
    const translation = t('patient_detail.' + key);
    return translation === 'patient_detail.' + key ? type : translation;
  };

  // Formatear fecha de nacimiento
  const formatBirthDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(dateLocale, { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  // Obtener etiqueta legible para fuente de adquisición
  const getAcquisitionSourceLabel = (source: string) => {
    const sourceMap: Record<string, string> = {
      'INSTAGRAM': 'Instagram',
      'GOOGLE': 'Google',
      'REFERRED': 'Referido',
      'OTHER': 'Otro',
      'ORGANIC': 'Orgánico'
    };
    return sourceMap[source] || source;
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'anamnesis':
        return (
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <HeartPulse size={20} className="text-primary" /> Anamnesis
              </h3>
              {patient?.anamnesis_token && (
                <button
                  onClick={() => {
                    const tenantId = (user as any)?.tenant_id || localStorage.getItem('X-Tenant-ID') || '1';
                    const baseUrl = window.location.origin;
                    const link = `${baseUrl}/anamnesis/${tenantId}/${patient.anamnesis_token}`;
                    navigator.clipboard.writeText(link).then(() => {
                      setLinkCopied(true);
                      setTimeout(() => setLinkCopied(false), 2000);
                    });
                  }}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    linkCopied
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-white/[0.06] text-white/70 border border-white/[0.08] hover:bg-white/[0.1] hover:text-white'
                  }`}
                >
                  {linkCopied ? <Check size={14} /> : <Copy size={14} />}
                  {linkCopied ? t('copied') || 'Copiado' : t('copyAnamnesisLink') || 'Copiar link de anamnesis'}
                </button>
              )}
            </div>
            <AnamnesisPanel
              patientId={parseInt(id!)}
              userRole={(user as any)?.role}
              compact={false}
              refreshKey={anamnesisRefreshKey}
            />
          </div>
        );

      case 'summary':
        return (
          <div className="space-y-6">
            {/* Financial Summary */}
            {(() => {
              // Calculate from records if available — or use placeholder
              return (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                  <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3">
                    <p className="text-[10px] text-white/40 uppercase font-bold">Turnos</p>
                    <p className="text-lg font-bold text-white">{patient?.appointment_count ?? records.length}</p>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3">
                    <p className="text-[10px] text-white/40 uppercase font-bold">Próximo turno</p>
                    <p className="text-sm font-semibold text-blue-400">
                      {patient?.next_appointment_date
                        ? new Date(patient.next_appointment_date).toLocaleDateString('es-AR', {day:'2-digit', month:'short'})
                        : 'Sin turno'}
                    </p>
                  </div>
                  <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3">
                    <p className="text-[10px] text-white/40 uppercase font-bold">Última visita</p>
                    <p className="text-sm font-semibold text-white/60">
                      {patient?.last_visit
                        ? new Date(patient.last_visit).toLocaleDateString('es-AR', {day:'2-digit', month:'short', year:'numeric'})
                        : 'Sin visitas'}
                    </p>
                  </div>
                  {((user as any)?.role === 'ceo' || (user as any)?.role === 'secretary') && (
                  <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3">
                    <p className="text-[10px] text-white/40 uppercase font-bold">Balance pendiente</p>
                    <p className={`text-sm font-bold ${(patient?.pending_balance || 0) > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {(patient?.pending_balance || 0) > 0
                        ? `$${Math.round(patient.pending_balance).toLocaleString('es-AR')}`
                        : 'Al día'}
                    </p>
                  </div>
                  )}
                </div>
              );
            })()}

            {/* Tratamientos completados — botón finalizar */}
            {completedTreatments.length > 0 && (
              <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 sm:p-6">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Send size={16} className="text-purple-400" />
                  {t('patient_detail.complete_treatment_title') || 'Finalizar Tratamiento'}
                </h3>
                <p className="text-xs text-white/40 mb-3">{t('patient_detail.complete_treatment_desc') || 'Marcá el tratamiento como completo para enviar el seguimiento HSM configurado.'}</p>
                <div className="space-y-2">
                  {completedTreatments.filter(ct => !ct.followup_sent).map(ct => (
                    <div key={ct.appointment_id} className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 bg-white/[0.02] border border-white/[0.04] rounded-xl p-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">{ct.treatment_name}</p>
                        <p className="text-[10px] text-white/30">{ct.appointment_date}</p>
                      </div>
                      <button
                        onClick={() => handleCompleteTreatmentFromDetail(ct.appointment_id)}
                        disabled={treatmentCompleteLoading === ct.appointment_id}
                        className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/15 text-purple-300 border border-purple-500/20 rounded-lg text-xs font-semibold hover:bg-purple-500/25 transition-all disabled:opacity-50"
                      >
                        {treatmentCompleteLoading === ct.appointment_id ? (
                          <div className="w-3 h-3 border-2 border-purple-300/30 border-t-purple-300 rounded-full animate-spin" />
                        ) : (
                          <Send size={12} />
                        )}
                        {t('patient_detail.send_followup') || 'Enviar Seguimiento'}
                      </button>
                      {treatmentCompleteResult[ct.appointment_id] && (
                        <p className="text-[10px] w-full sm:w-auto">{treatmentCompleteResult[ct.appointment_id]}</p>
                      )}
                    </div>
                  ))}
                  {completedTreatments.every(ct => ct.followup_sent) && (
                    <p className="text-xs text-emerald-400/60 flex items-center gap-1.5">
                      <Check size={12} />
                      {t('patient_detail.all_followups_sent') || 'Todos los seguimientos fueron enviados'}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Componente Odontograma */}
            <Odontogram
              patientId={parseInt(id!)}
              initialData={records[0]?.odontogram_data}
              readOnly={false}
              onSave={() => {
                // Recargar datos después de guardar
                fetchPatientData();
              }}
            />

            {/* Información básica del paciente */}
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-6">
              <h3 className="text-lg font-semibold text-white mb-4">{t('patient_detail.basic_info')}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <User className="text-white/30" size={16} />
                    <span className="text-sm font-medium text-white/60">{t('patient_detail.full_name')}:</span>
                    <span className="text-sm text-white">{patient?.first_name} {patient?.last_name}</span>
                  </div>
                  {patient?.dni && (
                    <div className="flex items-center gap-2">
                      <FileText className="text-white/30" size={16} />
                      <span className="text-sm font-medium text-white/60">DNI:</span>
                      <span className="text-sm text-white">{patient.dni}</span>
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Phone className="text-white/30" size={16} />
                    <span className="text-sm font-medium text-white/60">{t('patient_detail.phone')}:</span>
                    <span className="text-sm text-white">{patient?.phone_number}</span>
                  </div>
                  {patient?.email && (
                    <div className="flex items-center gap-2">
                      <Mail className="text-white/30" size={16} />
                      <span className="text-sm font-medium text-white/60">Email:</span>
                      <span className="text-sm text-white">{patient.email}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );

      case 'history':
        return (
          <div className="space-y-6">
            {/* Header de la sección */}
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-white">{t('patient_detail.tabs.history')}</h3>
                <p className="text-sm text-white/40">
                  {t('patient_detail.records_count', { count: records.length })}
                </p>
              </div>
              <button
                onClick={() => setShowNoteForm(true)}
                className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors"
              >
                <Plus size={18} />
                {t('patient_detail.add_evolution')}
              </button>
            </div>

            {/* Lista de registros clínicos */}
            {records.length === 0 ? (
              <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-8 text-center">
                <FileText size={48} className="mx-auto mb-4 text-white/30" />
                <h4 className="text-lg font-medium text-white/40 mb-2">{t('patient_detail.no_records_title')}</h4>
                <p className="text-white/40">{t('patient_detail.no_records')}</p>
                <button
                  onClick={() => setShowNoteForm(true)}
                  className="mt-4 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 transition-colors font-medium"
                >
                  {t('patient_detail.add_first_record')}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {records.map((record) => (
                  <div key={record.id} className="bg-white/[0.03] border border-white/[0.06] rounded-lg overflow-hidden">
                    <div className="p-4 border-b border-white/[0.06]">
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-3">
                          {getRecordIcon(record.record_type || 'evolution')}
                          <div>
                            <span className="inline-flex items-center px-2 py-1 bg-blue-500/10 text-blue-400 text-xs font-medium rounded-full">
                              {getRecordTypeLabel(record.record_type || 'evolution')}
                            </span>
                            <span className="ml-2 text-sm text-white/40">
                              {new Date(record.created_at).toLocaleString(dateLocale)}
                            </span>
                          </div>
                        </div>
                        <span className="text-xs text-white/30">
                          {t('patient_detail.by_professional')}: {record.professional_name}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 space-y-3">
                      {record.chief_complaint && (
                        <div>
                          <p className="text-xs font-medium text-white/40">{t('patient_detail.chief_complaint')}</p>
                          <p className="text-sm text-white">{record.chief_complaint}</p>
                        </div>
                      )}

                      {record.diagnosis && (
                        <div>
                          <p className="text-xs font-medium text-white/40">{t('patient_detail.diagnosis')}</p>
                          <p className="text-sm text-white">{record.diagnosis}</p>
                        </div>
                      )}

                      {record.treatment_plan && record.treatment_plan !== '{}' && (() => {
                        const tp = record.treatment_plan;
                        // Si es objeto {plan: "texto"} extraer el texto directamente
                        const displayText = typeof tp === 'object' && tp !== null && Object.keys(tp).length > 0
                          ? (tp.plan || (Object.keys(tp).length === 1 ? Object.values(tp)[0] : JSON.stringify(tp, null, 2)))
                          : (typeof tp === 'string' && tp !== '{}' ? tp : null);
                        if (!displayText) return null;
                        return (
                          <div>
                            <p className="text-xs font-medium text-white/40">{t('patient_detail.treatment_plan')}</p>
                            <div className="text-sm text-white">{String(displayText)}</div>
                          </div>
                        );
                      })()}

                      {record.notes && record.notes.trim() !== '' && record.notes !== '{}' && (
                        <div>
                          <p className="text-xs font-medium text-white/40">{t('patient_detail.notes')}</p>
                          <p className="text-sm text-white/60">{record.notes}</p>
                        </div>
                      )}

                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'documents':
        return (
          <DocumentGallery
            patientId={parseInt(id!)}
            readOnly={false}
          />
        );

      case 'digital_records':
        return (
          <DigitalRecordsTab
            patientId={parseInt(id!)}
            patientEmail={patient?.email || ''}
            refreshKey={digitalRecordsRefreshKey}
          />
        );

      case 'billing':
        if ((user as any)?.role !== 'ceo') return null;
        return (
          <BillingTab
            patientId={parseInt(id!)}
            refreshKey={billingRefreshKey}
          />
        );

      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-white/40">
        {t('patient_detail.loading')}
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="p-6 text-center text-white/40">
        {t('patient_detail.not_found')}
      </div>
    );
  }

  return (
    <div key={`patient-detail-${id}`} className="flex flex-col h-screen overflow-hidden">
      {/* Header Fijo */}
      <div className="shrink-0 bg-white/[0.03] border-b border-white/[0.06]">
        <div className="p-4 lg:p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/pacientes')}
                className="p-2 hover:bg-white/[0.04] rounded-lg transition-colors shrink-0 text-white"
              >
                <ArrowLeft size={20} />
              </button>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-xl lg:text-2xl font-bold text-white truncate">
                    {patient.first_name} {patient.last_name}
                  </h1>
                  {patient.patient_source === 'art' && (
                    <span
                      title={t('patients.art_badge_tooltip')}
                      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/20"
                    >
                      {t('patients.art_badge')}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  {patient.dni && (
                    <span className="text-sm text-white/60">DNI: {patient.dni}</span>
                  )}
                  <span className="text-sm text-white/60">•</span>
                  <span className="text-sm text-white/60">{patient.phone_number}</span>
                  {patient.email && (
                    <>
                      <span className="text-sm text-white/60">•</span>
                      <span className="text-sm text-white/60">{patient.email}</span>
                    </>
                  )}
                </div>

                {/* Datos Demográficos - Nuevos campos de admisión */}
                <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-white/40">
                  {patient.city && (
                    <span className="bg-white/[0.04] px-2 py-0.5 rounded">
                      📍 {patient.city}
                    </span>
                  )}
                  {patient.birth_date && (
                    <span className="bg-white/[0.04] px-2 py-0.5 rounded">
                      🎂 {formatBirthDate(patient.birth_date)}
                    </span>
                  )}
                  {patient.acquisition_source && patient.acquisition_source !== 'ORGANIC' && (
                    <span className="bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded">
                      {getAcquisitionSourceLabel(patient.acquisition_source)}
                    </span>
                  )}
                  {patient.insurance_provider ? (
                    <span className="bg-green-500/10 text-green-400 px-2 py-0.5 rounded">
                      🏥 {patient.insurance_provider}{patient.obra_social_number ? ` · ${patient.obra_social_number}` : ''}
                    </span>
                  ) : (
                    <span className="bg-white/[0.04] text-white/60 px-2 py-0.5 rounded">
                      🏥 Particular
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Alertas Médicas */}
            {criticalConditionsFound.length > 0 && (
              <div className="sm:ml-auto flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-2 rounded-lg">
                <AlertTriangle size={18} className="shrink-0" />
                <div>
                  <span className="text-sm font-semibold">{t('patient_detail.medical_alerts')}</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {criticalConditionsFound.map((condition) => (
                      <span key={condition} className="text-xs bg-red-500/10 text-red-400 px-2 py-0.5 rounded">
                        {condition}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Meta Ads Badge */}
            {patient.acquisition_source && patient.acquisition_source !== 'ORGANIC' && (
              <div className="group relative flex items-center gap-2 bg-blue-500/10 text-blue-400 px-3 py-1.5 rounded-full cursor-pointer">
                <Megaphone size={16} className="shrink-0" />
                <span className="text-xs sm:text-sm font-semibold">Meta Ads</span>
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-64 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
                  {patient.meta_campaign_id && (
                    <p className="mb-1"><span className="text-white/30">{t('patient_extra.meta_campaign')}</span> {patient.meta_campaign_id}</p>
                  )}
                  {patient.meta_ad_headline && (
                    <p className="truncate"><span className="text-white/30">{t('patient_extra.meta_ad')}</span> {patient.meta_ad_headline}</p>
                  )}
                  {!patient.meta_campaign_id && !patient.meta_ad_headline && (
                    <p className="text-white/30">ID: {patient.meta_ad_id || 'N/A'}</p>
                  )}
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45"></div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ART Incomplete Data Alert */}
        {patient.patient_source === 'art' && (
          <div className="mx-4 my-3 flex items-start gap-3 bg-orange-500/10 border border-orange-500/20 text-orange-300 px-4 py-3 rounded-lg">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-orange-400">{t('patients.art_badge')}</p>
              <p className="text-xs text-orange-300/80 mt-0.5">{t('patients.art_incomplete_alert')}</p>
            </div>
          </div>
        )}

        {/* Sistema de Pestañas con Scroll Isolation Horizontal */}
        <div className="border-t border-white/[0.06]">
          <div className="flex overflow-x-auto hide-scrollbar">
            <button
              onClick={() => setActiveTab('summary')}
              className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'summary'
                ? 'text-primary border-b-2 border-primary'
                : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
            >
              <div className="flex items-center justify-center gap-1.5">
                <ClipboardList size={16} />
                <span className="hidden sm:inline">{t('patient_detail.tabs.summary')}</span>
                <span className="sm:hidden">Resumen</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'history'
                ? 'text-primary border-b-2 border-primary'
                : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
            >
              <div className="flex items-center justify-center gap-1.5">
                <History size={16} />
                <span className="hidden sm:inline">{t('patient_detail.tabs.history')}</span>
                <span className="sm:hidden">Historia</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('documents')}
              className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'documents'
                ? 'text-primary border-b-2 border-primary'
                : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
            >
              <div className="flex items-center justify-center gap-1.5">
                <Folder size={16} />
                <span className="hidden sm:inline">{t('patient_detail.tabs.documents')}</span>
                <span className="sm:hidden">Archivos</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('anamnesis')}
              className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'anamnesis'
                ? 'text-primary border-b-2 border-primary'
                : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
            >
              <div className="flex items-center justify-center gap-1.5">
                <HeartPulse size={16} />
                Anamnesis
              </div>
            </button>
            <button
              onClick={() => setActiveTab('digital_records')}
              className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'digital_records'
                ? 'text-primary border-b-2 border-primary'
                : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                }`}
            >
              <div className="flex items-center justify-center gap-1.5">
                <FileText size={16} />
                <span className="hidden sm:inline">{t('digitalRecords.tab')}</span>
                <span className="sm:hidden">Fichas</span>
              </div>
            </button>
            {((user as any)?.role === 'ceo' || (user as any)?.role === 'secretary') && (
              <button
                onClick={() => setActiveTab('billing')}
                className={`flex-shrink-0 py-3 px-3 lg:px-4 text-xs lg:text-sm font-medium transition-colors whitespace-nowrap ${activeTab === 'billing'
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
                  }`}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <Receipt size={16} />
                  <span className="hidden sm:inline">{t('billing.tab')}</span>
                  <span className="sm:hidden">Presupuesto</span>
                </div>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Contenido Principal con Aislamiento de Scroll */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-4 lg:p-6">
          {renderTabContent()}
        </div>
      </div>

      {/* Modal para agregar nota (Adaptación Mobile) */}
      {showNoteForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-end sm:items-center justify-center z-50">
          <div className="bg-[#0d1117] border border-white/[0.08] w-full sm:max-w-2xl lg:max-w-5xl sm:mx-4 sm:rounded-lg rounded-t-xl sm:rounded-t-lg h-[90vh] sm:h-auto sm:max-h-[90vh] flex flex-col">
            {/* Header del Modal */}
            <div className="flex justify-between items-center p-4 border-b border-white/[0.06] shrink-0">
              <h2 className="text-xl font-bold text-white">{t('patient_detail.new_evolution')}</h2>
              <button
                onClick={() => setShowNoteForm(false)}
                className="text-white/40 hover:text-white/70 bg-white/[0.06] p-1 rounded-full"
              >
                <X size={20} />
              </button>
            </div>

            {/* Scrollable Form Area */}
            <div className="flex-1 min-h-0 overflow-y-auto p-4">
              <form id="note-form" onSubmit={handleSubmit}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-white/60 mb-1">
                      {t('patient_detail.record_type')}
                    </label>
                    <select
                      value={formData.record_type}
                      onChange={(e) => setFormData({ ...formData, record_type: e.target.value })}
                      className="w-full px-3 py-2 border border-white/[0.08] rounded-lg bg-white/[0.04] text-white focus:outline-none focus:ring-2 focus:ring-primary h-11"
                    >
                      <option value="initial" className="bg-[#0d1117] text-white">{t('patient_detail.initial_consult')}</option>
                      <option value="evolution" className="bg-[#0d1117] text-white">{t('patient_detail.evolution')}</option>
                      <option value="procedure" className="bg-[#0d1117] text-white">{t('patient_detail.procedure')}</option>
                      <option value="prescription" className="bg-[#0d1117] text-white">{t('patient_detail.prescription')}</option>
                    </select>
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-white/60 mb-1">
                    {t('patient_detail.chief_complaint_label')}
                  </label>
                  <input
                    type="text"
                    value={formData.chief_complaint}
                    onChange={(e) => setFormData({ ...formData, chief_complaint: e.target.value })}
                    placeholder={t('patient_detail.placeholder_complaint')}
                    className="w-full px-3 py-2 border border-white/[0.08] rounded-lg bg-white/[0.04] text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary h-11"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-white/60 mb-1">
                    {t('patient_detail.diagnosis')}
                  </label>
                  <textarea
                    value={formData.diagnosis}
                    onChange={(e) => setFormData({ ...formData, diagnosis: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-white/[0.08] rounded-lg bg-white/[0.04] text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-white/60 mb-1">
                    {t('patient_detail.treatment_plan')}
                  </label>
                  <textarea
                    value={formData.treatment_plan}
                    onChange={(e) => setFormData({ ...formData, treatment_plan: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-white/[0.08] rounded-lg bg-white/[0.04] text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-white/60 mb-1">
                    {t('patient_detail.additional_notes')}
                  </label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-white/[0.08] rounded-lg bg-white/[0.04] text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </form>
            </div>

            {/* Sticky Bottom Actions */}
            <div className="flex flex-col sm:flex-row justify-end gap-3 p-4 bg-[#0d1117] border-t border-white/[0.06] shrink-0">
              <button
                type="button"
                onClick={() => setShowNoteForm(false)}
                className="w-full sm:w-auto px-4 py-3 sm:py-2 text-white/60 bg-white/[0.04] rounded-lg hover:bg-white/[0.08] font-medium"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                form="note-form"
                className="w-full sm:w-auto px-4 py-3 sm:py-2 text-white bg-primary rounded-lg hover:bg-primary-dark font-medium"
              >
                {t('patient_detail.save_record')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}