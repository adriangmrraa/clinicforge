import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, User, Phone, Mail, Calendar, AlertTriangle,
  FileText, Plus, Activity, Heart, Pill, Stethoscope, Megaphone
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

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
  created_at: string;
  status?: string;
  medical_notes?: string; // Antecedentes médicos
  // Meta Ads (Spec 08)
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
}

const criticalConditions = [
  'diabetes', 'hipertension', 'cardiopatia', 'hemofilia',
  'alergia penicilina', 'embarazo', ' anticoagulacion',
  'vih', 'hepatitis', 'asma severa'
];

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [records, setRecords] = useState<ClinicalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [criticalConditionsFound, setCriticalConditionsFound] = useState<string[]>([]);

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

      // Check for critical medical conditions
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
    const keyMap: Record<string, string> = { initial: 'initial_consult', evolution: 'evolution', procedure: 'procedure', prescription: 'prescription' };
    return t('patient_detail.' + (keyMap[type] || type)) || type;
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
    <div className="p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
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
            <p className="text-sm text-gray-500">{t('patient_detail.digital_record')}</p>
          </div>
        </div>

        {criticalConditionsFound.length > 0 && (
          <div className="sm:ml-auto flex items-center gap-2 bg-red-100 text-red-800 px-3 py-1.5 rounded-full shadow-sm">
            <AlertTriangle size={16} className="shrink-0" />
            <span className="text-xs sm:text-sm font-semibold truncate">{t('patient_detail.critical_antecedents')}</span>
          </div>
        )}

        {/* Spec 08: Meta Ads Badge */}
        {patient.acquisition_source && patient.acquisition_source !== 'ORGANIC' && (
          <div className="sm:ml-auto group relative flex items-center gap-2 bg-blue-100 text-blue-800 px-3 py-1.5 rounded-full shadow-sm cursor-pointer">
            <Megaphone size={16} className="shrink-0" />
            <span className="text-xs sm:text-sm font-semibold">Meta Ads</span>
            {/* Tooltip */}
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Patient Profile */}
        <div className="lg:col-span-1 space-y-4">
          {/* Basic Info */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-primary rounded-full flex items-center justify-center text-white text-xl font-bold">
                {patient.first_name?.charAt(0)}
              </div>
              <div>
                <div className="font-medium text-gray-900">
                  {patient.first_name} {patient.last_name}
                </div>
                <div className="text-sm text-gray-500">{t('patient_detail.patient')}</div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Phone className="text-gray-400" size={16} />
                <span>{patient.phone_number}</span>
              </div>
              {patient.email && (
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="text-gray-400" size={16} />
                  <span>{patient.email}</span>
                </div>
              )}
              {patient.dni && (
                <div className="flex items-center gap-2 text-sm">
                  <User className="text-gray-400" size={16} />
                  <span>DNI: {patient.dni}</span>
                </div>
              )}
              {patient.obra_social && (
                <div className="flex items-center gap-2 text-sm">
                  <FileText className="text-gray-400" size={16} />
                  <span>{patient.obra_social} {patient.obra_social_number}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="text-gray-400" size={16} />
                <span>{t('patient_detail.admission_date')}: {new Date(patient.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {/* Medical Notes / Antecedentes */}
          {patient.medical_notes && (
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="text-red-500" size={18} />
                <h3 className="font-medium text-gray-900">{t('patient_detail.medical_antecedents')}</h3>
              </div>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">
                {patient.medical_notes}
              </p>
              {criticalConditionsFound.length > 0 && (
                <div className="mt-3 pt-3 border-t">
                  <p className="text-xs font-medium text-red-600 mb-2">{t('patient_detail.critical_conditions')}</p>
                  <div className="flex flex-wrap gap-1">
                    {criticalConditionsFound.map((condition) => (
                      <span key={condition} className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">
                        {condition}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Add Note Button */}
          <button
            onClick={() => setShowNoteForm(true)}
            className="w-full flex items-center justify-center gap-2 bg-primary text-white py-3 rounded-lg hover:bg-primary-dark transition-colors"
          >
            <Plus size={18} />
            {t('patient_detail.add_evolution')}
          </button>
        </div>

        {/* Clinical Records Timeline */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b">
              <h2 className="font-medium text-gray-900">{t('patient_detail.clinical_timeline')}</h2>
              <p className="text-sm text-gray-500">{t('patient_detail.records_count').replace('{{count}}', String(records.length))}</p>
            </div>

            <div className="p-4">
              {records.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FileText size={48} className="mx-auto mb-2 opacity-50" />
                  <p>{t('patient_detail.no_records')}</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {records.map((record, index) => (
                    <div key={record.id} className="relative pl-8 pb-4">
                      {/* Timeline line */}
                      {index < records.length - 1 && (
                        <div className="absolute left-[11px] top-6 bottom-0 w-0.5 bg-gray-200"></div>
                      )}

                      {/* Timeline dot */}
                      <div className="absolute left-0 top-1 w-6 h-6 bg-white border-2 border-gray-200 rounded-full flex items-center justify-center">
                        {getRecordIcon(record.record_type)}
                      </div>

                      {/* Content */}
                      <div className="bg-gray-50 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                              {getRecordTypeLabel(record.record_type)}
                            </span>
                            <span className="ml-2 text-sm text-gray-500">
                              {new Date(record.created_at).toLocaleString()}
                            </span>
                          </div>
                          <span className="text-xs text-gray-400">
                            Dr. {record.professional_name}
                          </span>
                        </div>

                        {record.chief_complaint && (
                          <div className="mb-2">
                            <p className="text-xs font-medium text-gray-500">{t('patient_detail.chief_complaint')}</p>
                            <p className="text-sm">{record.chief_complaint}</p>
                          </div>
                        )}

                        {record.diagnosis && (
                          <div className="mb-2">
                            <p className="text-xs font-medium text-gray-500">{t('patient_detail.diagnosis')}</p>
                            <p className="text-sm">{record.diagnosis}</p>
                          </div>
                        )}

                        {record.treatment_plan && (
                          <div className="mb-2">
                            <p className="text-xs font-medium text-gray-500">{t('patient_detail.treatment_plan')}</p>
                            <div className="text-sm">
                              {typeof record.treatment_plan === 'string'
                                ? record.treatment_plan
                                : JSON.stringify(record.treatment_plan, null, 2)}
                            </div>
                          </div>
                        )}

                        {record.notes && (
                          <div className="mb-2">
                            <p className="text-xs font-medium text-gray-500">{t('patient_detail.notes')}</p>
                            <p className="text-sm text-gray-600">{record.notes}</p>
                          </div>
                        )}

                        {record.vital_signs && (
                          <div className="flex gap-4 mt-2 pt-2 border-t">
                            {record.vital_signs.blood_pressure && (
                              <div className="text-xs">
                                <span className="text-gray-400">PA: </span>
                                <span>{record.vital_signs.blood_pressure}</span>
                              </div>
                            )}
                            {record.vital_signs.heart_rate && (
                              <div className="text-xs">
                                <span className="text-gray-400">FC: </span>
                                <span>{record.vital_signs.heart_rate} ppm</span>
                              </div>
                            )}
                            {record.vital_signs.temperature && (
                              <div className="text-xs">
                                <span className="text-gray-400">T°: </span>
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
          </div>
        </div>
      </div>

      {/* Add Note Modal */}
      {showNoteForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center p-4 border-b sticky top-0 bg-white">
              <h2 className="text-xl font-bold">{t('patient_detail.new_evolution')}</h2>
              <button
                onClick={() => setShowNoteForm(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-4">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('patient_detail.record_type')}
                  </label>
                  <select
                    value={formData.record_type}
                    onChange={(e) => setFormData({ ...formData, record_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
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

              {/* Vital Signs */}
              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <h3 className="text-sm font-medium text-gray-700 mb-2">{t('patient_detail.vital_signs')}</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">{t('patient_detail.blood_pressure')}</label>
                    <input
                      type="text"
                      placeholder={t('patient_detail.placeholder_bp')}
                      value={formData.blood_pressure}
                      onChange={(e) => setFormData({ ...formData, blood_pressure: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
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
                    <label className="block text-xs text-gray-500 mb-1">{t('patient_detail.temperature')}</label>
                    <input
                      type="text"
                      placeholder={t('patient_detail.placeholder_temp')}
                      value={formData.temperature}
                      onChange={(e) => setFormData({ ...formData, temperature: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notas Adicionales
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowNoteForm(false)}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-white bg-primary rounded-lg hover:bg-primary-dark"
                >
                  {t('patient_detail.save_record')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
