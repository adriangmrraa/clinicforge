import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, User, Phone, Mail, Calendar, AlertTriangle,
  FileText, Plus, Activity, Heart, Pill, Stethoscope, Megaphone,
  ClipboardList, History, Folder, X
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import Odontogram from '../components/Odontogram';
import DocumentGallery from '../components/DocumentGallery';

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
}

interface ClinicalRecord {
  id: number;
  patient_id: number;
  professional_id: number;
  professional_name: string;
  appointment_id?: number;
  record_type: string;
  chief_complaint?: string;
  diagnosis?: string;
  treatment_plan?: any;
  notes?: string;
  vital_signs?: Record<string, string>;
  created_at: string;
  odontogram_data?: any;
}

const criticalConditions = [
  'diabetes', 'hipertension', 'cardiopatia', 'hemofilia',
  'alergia penicilina', 'embarazo', ' anticoagulacion',
  'vih', 'hepatitis', 'asma severa'
];

type TabType = 'summary' | 'history' | 'documents';

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t, language } = useTranslation();
  const dateLocale = language === 'es' ? 'es-AR' : language === 'fr' ? 'fr-FR' : 'en-US';
  const [patient, setPatient] = useState<Patient | null>(null);
  const [records, setRecords] = useState<ClinicalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [criticalConditionsFound, setCriticalConditionsFound] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>('summary');

  const [formData, setFormData] = useState({
    record_type: 'evolution',
    chief_complaint: '',
    diagnosis: '',
    treatment_plan: '',
    notes: '',
    blood_pressure: '',
    heart_rate: '',
    temperature: '',
  });

  useEffect(() => {
    if (id) {
      fetchPatientData();
    }
  }, [id]);

  const fetchPatientData = async () => {
    try {
      setLoading(true);
      const [patientRes, recordsRes] = await Promise.all([
        api.get(`/admin/patients/${id}`),
        api.get(`/admin/patients/${id}/records`),
      ]);
      setPatient(patientRes.data);
      setRecords(recordsRes.data);

      if (patientRes.data.medical_notes) {
        const notes = patientRes.data.medical_notes.toLowerCase();
        const found = criticalConditions.filter(condition =>
          notes.includes(condition.toLowerCase())
        );
        setCriticalConditionsFound(found);
      }
    } catch (error) {
      console.error('Error fetching patient data:', error);
    } finally {
      setLoading(false);
    }
  };

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
        vital_signs: {
          blood_pressure: formData.blood_pressure,
          heart_rate: formData.heart_rate,
          temperature: formData.temperature,
        },
      };

      await api.post('/admin/clinical-records', payload);
      fetchPatientData();
      setShowNoteForm(false);
      setFormData({
        record_type: 'evolution',
        chief_complaint: '',
        diagnosis: '',
        treatment_plan: '',
        notes: '',
        blood_pressure: '',
        heart_rate: '',
        temperature: '',
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
      default: return <FileText className="text-gray-500" size={18} />;
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
      case 'summary':
        return (
          <div className="space-y-6">
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
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">{t('patient_detail.basic_info')}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <User className="text-gray-400" size={16} />
                    <span className="text-sm font-medium text-gray-600">{t('patient_detail.full_name')}:</span>
                    <span className="text-sm">{patient?.first_name} {patient?.last_name}</span>
                  </div>
                  {patient?.dni && (
                    <div className="flex items-center gap-2">
                      <FileText className="text-gray-400" size={16} />
                      <span className="text-sm font-medium text-gray-600">DNI:</span>
                      <span className="text-sm">{patient.dni}</span>
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Phone className="text-gray-400" size={16} />
                    <span className="text-sm font-medium text-gray-600">{t('patient_detail.phone')}:</span>
                    <span className="text-sm">{patient?.phone_number}</span>
                  </div>
                  {patient?.email && (
                    <div className="flex items-center gap-2">
                      <Mail className="text-gray-400" size={16} />
                      <span className="text-sm font-medium text-gray-600">Email:</span>
                      <span className="text-sm">{patient.email}</span>
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
                <h3 className="text-lg font-semibold text-gray-800">{t('patient_detail.tabs.history')}</h3>
                <p className="text-sm text-gray-500">
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
              <div className="bg-white rounded-lg shadow p-8 text-center">
                <FileText size={48} className="mx-auto mb-4 text-gray-300" />
                <h4 className="text-lg font-medium text-gray-700 mb-2">{t('patient_detail.no_records_title')}</h4>
                <p className="text-gray-500">{t('patient_detail.no_records')}</p>
                <button
                  onClick={() => setShowNoteForm(true)}
                  className="mt-4 bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors"
                >
                  {t('patient_detail.add_first_record')}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {records.map((record, index) => (
                  <div key={record.id} className="bg-white rounded-lg shadow overflow-hidden">
                    <div className="p-4 border-b">
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-3">
                          {getRecordIcon(record.record_type)}
                          <div>
                            <span className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
                              {getRecordTypeLabel(record.record_type)}
                            </span>
                            <span className="ml-2 text-sm text-gray-500">
                              {new Date(record.created_at).toLocaleString(dateLocale)}
                            </span>
                          </div>
                        </div>
                        <span className="text-xs text-gray-400">
                          {t('patient_detail.by_professional')}: {record.professional_name}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 space-y-3">
                      {record.chief_complaint && (
                        <div>
                          <p className="text-xs font-medium text-gray-500">{t('patient_detail.chief_complaint')}</p>
                          <p className="text-sm">{record.chief_complaint}</p>
                        </div>
                      )}

                      {record.diagnosis && (
                        <div>
                          <p className="text-xs font-medium text-gray-500">{t('patient_detail.diagnosis')}</p>
                          <p className="text-sm">{record.diagnosis}</p>
                        </div>
                      )}

                      {record.treatment_plan && record.treatment_plan !== '{}' && (
                        <div>
                          <p className="text-xs font-medium text-gray-500">{t('patient_detail.treatment_plan')}</p>
                          <div className="text-sm">
                            {typeof record.treatment_plan === 'string'
                              ? (record.treatment_plan === '{}' ? null : record.treatment_plan)
                              : (Object.keys(record.treatment_plan).length > 0 ? JSON.stringify(record.treatment_plan, null, 2) : null)}
                          </div>
                        </div>
                      )}

                      {record.notes && record.notes.trim() !== '' && record.notes !== '{}' && (
                        <div>
                          <p className="text-xs font-medium text-gray-500">{t('patient_detail.notes')}</p>
                          <p className="text-sm text-gray-600">{record.notes}</p>
                        </div>
                      )}

                      {record.vital_signs && (
                        <div className="flex gap-4 pt-3 border-t">
                          {record.vital_signs.blood_pressure && (
                            <div className="text-xs">
                              <span className="text-gray-400">{t('patient_detail.blood_pressure_short') || 'PA'}: </span>
                              <span>{record.vital_signs.blood_pressure}</span>
                            </div>
                          )}
                          {record.vital_signs.heart_rate && (
                            <div className="text-xs">
                              <span className="text-gray-400">{t('patient_detail.heart_rate_short') || 'FC'}: </span>
                              <span>{record.vital_signs.heart_rate} ppm</span>
                            </div>
                          )}
                          {record.vital_signs.temperature && (
                            <div className="text-xs">
                              <span className="text-gray-400">{t('patient_detail.temperature_short') || 'T°'}: </span>
                              <span>{record.vital_signs.temperature}°C</span>
                            </div>
                          )}
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

      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        {t('patient_detail.loading')}
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="p-6 text-center text-gray-500">
        {t('patient_detail.not_found')}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Header Fijo */}
      <div className="shrink-0 bg-white border-b">
        <div className="p-4 lg:p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/pacientes')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors shrink-0"
              >
                <ArrowLeft size={20} />
              </button>
              <div className="min-w-0">
                <h1 className="text-xl lg:text-2xl font-bold text-gray-800 truncate">
                  {patient.first_name} {patient.last_name}
                </h1>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  {patient.dni && (
                    <span className="text-sm text-gray-600">DNI: {patient.dni}</span>
                  )}
                  <span className="text-sm text-gray-600">•</span>
                  <span className="text-sm text-gray-600">{patient.phone_number}</span>
                  {patient.email && (
                    <>
                      <span className="text-sm text-gray-600">•</span>
                      <span className="text-sm text-gray-600">{patient.email}</span>
                    </>
                  )}
                </div>

                {/* Datos Demográficos - Nuevos campos de admisión */}
                <div className="flex flex-wrap items-center gap-2 mt-2 text-xs text-gray-500">
                  {patient.city && (
                    <span className="bg-gray-100 px-2 py-0.5 rounded">
                      📍 {patient.city}
                    </span>
                  )}
                  {patient.birth_date && (
                    <span className="bg-gray-100 px-2 py-0.5 rounded">
                      🎂 {formatBirthDate(patient.birth_date)}
                    </span>
                  )}
                  {patient.acquisition_source && patient.acquisition_source !== 'ORGANIC' && (
                    <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                      {getAcquisitionSourceLabel(patient.acquisition_source)}
                    </span>
                  )}
                  {patient.insurance_provider ? (
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">
                      🏥 {patient.insurance_provider}
                    </span>
                  ) : (
                    <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      🏥 Particular
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Alertas Médicas */}
            {criticalConditionsFound.length > 0 && (
              <div className="sm:ml-auto flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg">
                <AlertTriangle size={18} className="shrink-0" />
                <div>
                  <span className="text-sm font-semibold">{t('patient_detail.medical_alerts')}</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {criticalConditionsFound.map((condition) => (
                      <span key={condition} className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">
                        {condition}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Meta Ads Badge */}
            {patient.acquisition_source && patient.acquisition_source !== 'ORGANIC' && (
              <div className="group relative flex items-center gap-2 bg-blue-100 text-blue-800 px-3 py-1.5 rounded-full shadow-sm cursor-pointer">
                <Megaphone size={16} className="shrink-0" />
                <span className="text-xs sm:text-sm font-semibold">Meta Ads</span>
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-64 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
                  {patient.meta_campaign_id && (
                    <p className="mb-1"><span className="text-gray-400">{t('patient_extra.meta_campaign')}</span> {patient.meta_campaign_id}</p>
                  )}
                  {patient.meta_ad_headline && (
                    <p className="truncate"><span className="text-gray-400">{t('patient_extra.meta_ad')}</span> {patient.meta_ad_headline}</p>
                  )}
                  {!patient.meta_campaign_id && !patient.meta_ad_headline && (
                    <p className="text-gray-400">ID: {patient.meta_ad_id || 'N/A'}</p>
                  )}
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45"></div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sistema de Pestañas con Scroll Isolation Horizontal */}
        <div className="border-t">
          <div className="flex overflow-x-auto hide-scrollbar">
            <button
              onClick={() => setActiveTab('summary')}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${activeTab === 'summary'
                ? 'text-primary border-b-2 border-primary'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
            >
              <div className="flex items-center justify-center gap-2">
                <ClipboardList size={18} />
                {t('patient_detail.tabs.summary')}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${activeTab === 'history'
                ? 'text-primary border-b-2 border-primary'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
            >
              <div className="flex items-center justify-center gap-2">
                <History size={18} />
                {t('patient_detail.tabs.history')}
              </div>
            </button>
            <button
              onClick={() => setActiveTab('documents')}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors ${activeTab === 'documents'
                ? 'text-primary border-b-2 border-primary'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
            >
              <div className="flex items-center justify-center gap-2">
                <Folder size={18} />
                {t('patient_detail.tabs.documents')}
              </div>
            </button>
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
          <div className="bg-white w-full sm:max-w-2xl sm:mx-4 sm:rounded-lg rounded-t-xl sm:rounded-t-lg h-[90vh] sm:h-auto sm:max-h-[90vh] flex flex-col">
            {/* Header del Modal */}
            <div className="flex justify-between items-center p-4 border-b shrink-0">
              <h2 className="text-xl font-bold">{t('patient_detail.new_evolution')}</h2>
              <button
                onClick={() => setShowNoteForm(false)}
                className="text-gray-500 hover:text-gray-700 bg-gray-100 p-1 rounded-full"
              >
                <X size={20} />
              </button>
            </div>

            {/* Scrollable Form Area */}
            <div className="flex-1 overflow-y-auto p-4">
              <form id="note-form" onSubmit={handleSubmit}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('patient_detail.record_type')}
                    </label>
                    <select
                      value={formData.record_type}
                      onChange={(e) => setFormData({ ...formData, record_type: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary h-11"
                    >
                      <option value="initial">{t('patient_detail.initial_consult')}</option>
                      <option value="evolution">{t('patient_detail.evolution')}</option>
                      <option value="procedure">{t('patient_detail.procedure')}</option>
                      <option value="prescription">{t('patient_detail.prescription')}</option>
                    </select>
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('patient_detail.chief_complaint_label')}
                  </label>
                  <input
                    type="text"
                    value={formData.chief_complaint}
                    onChange={(e) => setFormData({ ...formData, chief_complaint: e.target.value })}
                    placeholder={t('patient_detail.placeholder_complaint')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary h-11"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('patient_detail.diagnosis')}
                  </label>
                  <textarea
                    value={formData.diagnosis}
                    onChange={(e) => setFormData({ ...formData, diagnosis: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('patient_detail.treatment_plan')}
                  </label>
                  <textarea
                    value={formData.treatment_plan}
                    onChange={(e) => setFormData({ ...formData, treatment_plan: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">{t('patient_detail.vital_signs')}</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">{t('patient_detail.blood_pressure')}</label>
                      <input
                        type="text"
                        placeholder={t('patient_detail.placeholder_bp')}
                        value={formData.blood_pressure}
                        onChange={(e) => setFormData({ ...formData, blood_pressure: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm h-11"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('patient_detail.heart_rate')}</label>
                      <input
                        type="text"
                        placeholder={t('patient_detail.placeholder_hr')}
                        value={formData.heart_rate}
                        onChange={(e) => setFormData({ ...formData, heart_rate: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">{t('patient_detail.temperature')}</label>
                      <input
                        type="text"
                        placeholder={t('patient_detail.placeholder_temp')}
                        value={formData.temperature}
                        onChange={(e) => setFormData({ ...formData, temperature: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm h-11"
                      />
                    </div>
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('patient_detail.additional_notes')}
                  </label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </form>
            </div>

            {/* Sticky Bottom Actions */}
            <div className="flex flex-col sm:flex-row justify-end gap-3 p-4 bg-white border-t shrink-0">
              <button
                type="button"
                onClick={() => setShowNoteForm(false)}
                className="w-full sm:w-auto px-4 py-3 sm:py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 font-medium"
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