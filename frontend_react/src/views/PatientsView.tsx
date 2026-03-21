import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Edit, Trash2, X, FileText, Brain, Calendar, User, Clock, Stethoscope, Mail, Upload, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

interface Patient {
  id: number;
  first_name: string;
  last_name?: string;
  phone_number: string;
  email?: string;
  obra_social?: string;
  dni?: string;
  city?: string;
  birth_date?: string;
  created_at: string;
  status?: string;
  health_conditions?: string[];
}

interface TreatmentType {
  code: string;
  name: string;
  description: string;
  category: string;
  default_duration_minutes?: number;
}

interface Professional {
  id: number;
  first_name: string;
  last_name?: string;
  specialty?: string;
  is_active: boolean;
}

export default function PatientsView() {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [filteredPatients, setFilteredPatients] = useState<Patient[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [semanticSearchTerm, setSemanticSearchTerm] = useState('');
  const [semanticResults, setSemanticResults] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null);

  // Resources for dropdowns
  const [treatments, setTreatments] = useState<TreatmentType[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone_number: '',
    email: '',
    obra_social: '',
    dni: '',
    city: '',
    birth_date: '',
  });

  const [appointmentData, setAppointmentData] = useState({
    treatment_code: '',
    professional_id: '',
    date: '',
    time: '',
    duration_minutes: 30
  });

  // Import state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importStep, setImportStep] = useState<'upload' | 'preview' | 'result'>('upload');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importPreview, setImportPreview] = useState<any>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [duplicateAction, setDuplicateAction] = useState<'skip' | 'update'>('skip');
  const [dragOver, setDragOver] = useState(false);

  // Fetch patients on mount
  useEffect(() => {
    fetchPatients();
    fetchResources();
  }, []);

  // Filter patients when search term changes
  useEffect(() => {
    const filtered = patients.filter((patient) => {
      const searchLower = searchTerm.toLowerCase();
      // Safe check for nulls
      const fname = patient.first_name || '';
      const lname = patient.last_name || '';
      const phone = patient.phone_number || '';
      const dni = patient.dni || '';
      const email = patient.email || '';

      return (
        fname.toLowerCase().includes(searchLower) ||
        lname.toLowerCase().includes(searchLower) ||
        phone.includes(searchTerm) ||
        dni.includes(searchTerm) ||
        email.toLowerCase().includes(searchLower)
      );
    });
    setFilteredPatients(filtered);
  }, [searchTerm, patients]);

  const fetchPatients = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/patients');
      setPatients(response.data);
      setFilteredPatients(response.data);
    } catch (error) {
      console.error('Error fetching patients:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchResources = async () => {
    try {
      const [treatResponse, profResponse] = await Promise.all([
        api.get('/admin/treatment-types'),
        api.get('/admin/professionals')
      ]);
      setTreatments(treatResponse.data);
      setProfessionals((profResponse.data || []).filter((p: Professional) => p.is_active));
    } catch (error) {
      console.error('Error fetching resources:', error);
    }
  };

  const handleSemanticSearch = async (value: string) => {
    setSemanticSearchTerm(value);

    if (!value.trim()) {
      setSemanticResults([]);
      setFilteredPatients(patients);
      return;
    }

    setSemanticLoading(true);

    try {
      const response = await api.get('/admin/patients/search-semantic', {
        params: { query: value }
      });

      setSemanticResults(response.data);

      if (response.data.length > 0) {
        setFilteredPatients(response.data);
      }
    } catch (error) {
      console.error('Error in semantic search:', error);
      setSemanticResults([]);
      setFilteredPatients(patients);
    } finally {
      setSemanticLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Map obra_social to insurance for the backend
      const payload = {
        ...formData,
        insurance: formData.obra_social
      };

      let patientId;

      if (editingPatient) {
        await api.put(`/admin/patients/${editingPatient.id}`, payload);
        patientId = editingPatient.id;
      } else {
        const res = await api.post('/admin/patients', payload);
        patientId = res.data.id;
      }

      // If creating new patient AND appointment data is filled
      if (!editingPatient && appointmentData.treatment_code && appointmentData.professional_id && appointmentData.date && appointmentData.time) {
        try {
          const aptDate = new Date(`${appointmentData.date}T${appointmentData.time}`);
          await api.post('/admin/appointments', {
            patient_id: patientId,
            professional_id: parseInt(appointmentData.professional_id),
            appointment_datetime: aptDate.toISOString(),
            appointment_type: appointmentData.treatment_code,
            duration_minutes: appointmentData.duration_minutes || 30,
            notes: t('patients.initial_appointment_notes'),
            check_collisions: true
          });
          alert(t('alerts.patient_and_appointment_ok'));
        } catch (aptError) {
          console.error("Error creating appointment:", aptError);
          alert(t('alerts.patient_ok_appointment_fail'));
        }
      } else if (!editingPatient) {
        // Just verify creation
      }

      fetchPatients();
      closeModal();
    } catch (error: any) {
      console.error('Error saving patient:', error);
      const detail = error?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x: any) => x?.msg || x).join(', ') : t('alerts.error_save_patient');
      alert(msg || t('alerts.error_save_patient'));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t('alerts.confirm_delete_patient'))) return;
    try {
      await api.delete(`/admin/patients/${id}`);
      fetchPatients();
    } catch (error) {
      console.error('Error deleting patient:', error);
      alert(t('alerts.error_delete_patient'));
    }
  };

  const openEditModal = (patient: Patient) => {
    setEditingPatient(patient);
    setFormData({
      first_name: patient.first_name || '',
      last_name: patient.last_name || '',
      phone_number: patient.phone_number || '',
      email: patient.email || '',
      obra_social: patient.obra_social || '',
      dni: patient.dni || '',
      city: patient.city || '',
      birth_date: patient.birth_date || '',
    });
    // Clear appointment data on edit
    setAppointmentData({ treatment_code: '', professional_id: '', date: '', time: '', duration_minutes: 30 });
    setShowModal(true);
  };

  const openCreateModal = () => {
    setEditingPatient(null);
    setFormData({
      first_name: '',
      last_name: '',
      phone_number: '',
      email: '',
      obra_social: '',
      dni: '',
      city: '',
      birth_date: '',
    });
    // Reset appointment data
    setAppointmentData({ treatment_code: '', professional_id: '', date: '', time: '', duration_minutes: 30 });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingPatient(null);
  };

  // --- Import handlers ---
  const openImportModal = () => {
    setShowImportModal(true);
    setImportStep('upload');
    setImportFile(null);
    setImportPreview(null);
    setImportResult(null);
    setDuplicateAction('skip');
  };

  const handleImportFileSelect = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'csv' && ext !== 'xlsx') {
      alert(t('patients.import_invalid_format'));
      return;
    }
    setImportFile(file);
  };

  const handleImportDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleImportFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleImportPreview = async () => {
    if (!importFile) return;
    setImportLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      const res = await api.post('/admin/patients/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setImportPreview(res.data);
      setImportStep('preview');
    } catch (err: any) {
      alert(err.response?.data?.detail || t('patients.import_error'));
    } finally {
      setImportLoading(false);
    }
  };

  const handleImportExecute = async () => {
    if (!importPreview) return;
    setImportLoading(true);
    try {
      const res = await api.post('/admin/patients/import/execute', {
        duplicate_action: duplicateAction,
        rows: importPreview.preview_rows,
      });
      setImportResult(res.data);
      setImportStep('result');
      fetchPatients();
    } catch (err: any) {
      alert(err.response?.data?.detail || t('patients.import_error'));
    } finally {
      setImportLoading(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 h-full overflow-y-auto bg-gray-100">
      <PageHeader
        title={t('patients.title')}
        subtitle={t('patients.subtitle')}
        icon={<User size={22} />}
        action={
          <div className="flex gap-2 w-full sm:w-auto">
            <button
              onClick={openImportModal}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shadow-md active:scale-[0.98]"
            >
              <Upload size={18} />
              {t('patients.import_button')}
            </button>
            <button
              onClick={openCreateModal}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-primary hover:bg-primary-dark text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shadow-md active:scale-[0.98]"
            >
              <Plus size={20} />
              {t('patients.new_patient')}
            </button>
          </div>
        }
      />

      {/* Search */}
      <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            placeholder={t('patients.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-white"
          />
        </div>

        {/* Semantic Search */}
        <div className="relative">
          <Brain className="absolute left-3 top-1/2 transform -translate-y-1/2 text-purple-500" size={18} />
          <input
            type="text"
            placeholder={t('patients.search_semantic')}
            value={semanticSearchTerm}
            onChange={(e) => handleSemanticSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-purple-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white"
          />
          {semanticLoading && (
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
              <div className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">{t('patients.loading')}</div>
        ) : filteredPatients.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {t('patients.no_patients_found')}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto hidden md:block">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.patient')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.contact')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.dni_obra_social')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.health')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.date_added')}
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('patients.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredPatients.map((patient) => (
                    <tr key={patient.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10 bg-primary-light rounded-full flex items-center justify-center text-white font-medium">
                            {patient.first_name?.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-4">
                            <div className="flex items-center gap-2">
                              <div className="text-sm font-medium text-gray-900">
                                {patient.first_name} {patient.last_name}
                              </div>
                              {semanticResults.some(r => r.id === patient.id) && (
                                <Brain size={16} className="text-purple-500" />
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{patient.phone_number}</div>
                        <div className="text-sm text-gray-500">{patient.email}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{patient.dni || '-'}</div>
                        <div className="text-sm text-gray-500">{patient.obra_social || '-'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">-</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(patient.created_at).toLocaleDateString(language)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => navigate(`/pacientes/${patient.id}`)}
                            className="p-2 text-gray-600 hover:text-primary hover:bg-gray-100 rounded-lg transition-colors"
                            title={t('patients.view_chart')}
                          >
                            <FileText size={18} />
                          </button>
                          <button
                            onClick={() => openEditModal(patient)}
                            className="p-2 text-gray-600 hover:text-primary hover:bg-gray-100 rounded-lg transition-colors"
                            title={t('common.edit')}
                          >
                            <Edit size={18} />
                          </button>
                          <button
                            onClick={() => handleDelete(patient.id)}
                            className="p-2 text-gray-600 hover:text-red-600 hover:bg-gray-100 rounded-lg transition-colors"
                            title={t('common.delete')}
                          >
                            <Trash2 size={18} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Cards for Mobile */}
            <div className="md:hidden divide-y">
              {filteredPatients.map((patient) => (
                <div key={patient.id} className="p-4 bg-white hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 bg-primary-light rounded-full flex items-center justify-center text-white font-medium shrink-0">
                        {patient.first_name?.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900 truncate">
                            {patient.first_name} {patient.last_name}
                          </h3>
                          {semanticResults.some(r => r.id === patient.id) && (
                            <Brain size={14} className="text-purple-500 shrink-0" />
                          )}
                        </div>
                        <p className="text-xs text-gray-500 truncate">DNI: {patient.dni || '-'}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => navigate(`/pacientes/${patient.id}`)}
                        className="p-2 text-gray-600 hover:text-primary active:bg-gray-200 rounded-lg"
                      >
                        <FileText size={18} />
                      </button>
                      <button
                        onClick={() => openEditModal(patient)}
                        className="p-2 text-gray-600 hover:text-primary active:bg-gray-200 rounded-lg"
                      >
                        <Edit size={18} />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 mb-3 bg-gray-50 p-2 rounded-lg">
                    <div>
                      <span className="block text-[10px] text-gray-400 uppercase font-semibold">{t('patients.phone_label')}</span>
                      {patient.phone_number}
                    </div>
                    <div>
                      <span className="block text-[10px] text-gray-400 uppercase font-semibold">{t('patients.obra_social')}</span>
                      {patient.obra_social || '-'}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[10px] text-gray-400">
                      {t('patients.loaded_on')}: {new Date(patient.created_at).toLocaleDateString(language)}
                    </span>
                    <button
                      onClick={() => handleDelete(patient.id)}
                      className="text-xs text-red-500 font-medium px-2 py-1 hover:bg-red-50 rounded"
                    >
                      {t('common.delete')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Modal: estilo slide-over como Agenda (Inspector Clínico) */}
      {showModal && (
        <div key={`patient-modal-${editingPatient?.id ?? 'new'}`} className="fixed inset-0 z-[60]">
          <div
            className="fixed inset-0 bg-black/20 backdrop-blur-sm transition-opacity duration-300"
            onClick={closeModal}
          />
          <div className="fixed inset-y-0 right-0 z-[70] w-full md:w-[450px] bg-white/90 backdrop-blur-xl shadow-2xl transform transition-transform duration-300 ease-out border-l border-white/50 flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-white/50">
              <div>
                <h2 className="text-xl font-bold text-slate-800">
                  {editingPatient ? t('patients.edit_patient') : t('patients.new_patient')}
                </h2>
                <p className="text-xs text-slate-500">{t('patients.personal_data')}</p>
              </div>
              <button onClick={closeModal} className="p-2 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto flex flex-col">
              <div className="flex-1 p-6 space-y-6">
                {/* Datos personales */}
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.first_name_req')}</label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                          type="text"
                          required
                          value={formData.first_name}
                          onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                          className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                        />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.last_name_req')}</label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                          type="text"
                          required
                          value={formData.last_name}
                          onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                          className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.phone_req')}</label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                      <input
                        type="tel"
                        required
                        value={formData.phone_number}
                        onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.dni')}</label>
                    <div className="relative">
                      <FileText className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                      <input
                        type="text"
                        value={formData.dni}
                        onChange={(e) => setFormData({ ...formData, dni: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.email')}</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                      <input
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.obra_social')}</label>
                    <input
                      type="text"
                      value={formData.obra_social}
                      onChange={(e) => setFormData({ ...formData, obra_social: e.target.value })}
                      placeholder={t('patients.obra_social_placeholder')}
                      className="w-full px-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.city_neighborhood')}</label>
                      <input
                        type="text"
                        value={formData.city}
                        onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                        placeholder={t('patients.city_placeholder')}
                        className="w-full px-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.birth_date')}</label>
                      <input
                        type="date"
                        value={formData.birth_date}
                        onChange={(e) => setFormData({ ...formData, birth_date: e.target.value })}
                        className="w-full px-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Turno inicial (solo para nuevos) */}
                {!editingPatient && (
                  <div className="pt-4 border-t border-gray-100">
                    <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                      <Calendar size={16} />
                      {t('patients.schedule_first_appointment')}
                    </h3>
                    <div className="space-y-5">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.treatment_service')}</label>
                        <div className="relative">
                          <Stethoscope className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                          <select
                            value={appointmentData.treatment_code}
                            onChange={(e) => {
                              const code = e.target.value;
                              const tr = treatments.find(t => t.code === code);
                              setAppointmentData({ ...appointmentData, treatment_code: code, duration_minutes: tr?.default_duration_minutes ?? 30 });
                            }}
                            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none cursor-pointer"
                          >
                            <option value="">{t('patients.select_treatment')}</option>
                            {treatments.map(t => (
                              <option key={t.code} value={t.code}>{t.name} ({t.category})</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.professional')}</label>
                        <div className="relative">
                          <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                          <select
                            value={appointmentData.professional_id}
                            onChange={(e) => setAppointmentData({ ...appointmentData, professional_id: e.target.value })}
                            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none cursor-pointer"
                          >
                            <option value="">{t('patients.select_professional')}</option>
                            {professionals.map(p => (
                              <option key={p.id} value={p.id}>Dr. {[p.first_name, p.last_name].filter(Boolean).join(' ')}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.date')}</label>
                          <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                            <input
                              type="date"
                              value={appointmentData.date}
                              onChange={(e) => setAppointmentData({ ...appointmentData, date: e.target.value })}
                              className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                            />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('patients.time')}</label>
                          <div className="relative">
                            <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                            <input
                              type="time"
                              value={appointmentData.time}
                              onChange={(e) => setAppointmentData({ ...appointmentData, time: e.target.value })}
                              className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm"
                            />
                          </div>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('agenda.duration_min')}</label>
                        <div className="relative">
                          <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                          <select
                            value={appointmentData.duration_minutes}
                            onChange={(e) => setAppointmentData({ ...appointmentData, duration_minutes: parseInt(e.target.value) || 30 })}
                            className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-transparent rounded-lg focus:bg-white focus:border-blue-500 focus:ring-0 transition-all text-sm appearance-none"
                          >
                            {[15, 30, 45, 60, 90, 120].map(m => (
                              <option key={m} value={m}>{m} min</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 p-6 border-t border-gray-100 bg-white/50">
                <button type="button" onClick={closeModal} className="px-4 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="px-4 py-2.5 text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors text-sm font-medium">
                  {editingPatient ? t('common.save_changes') : t('patients.create_patient')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={e => e.target === e.currentTarget && setShowImportModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-100 shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-slate-100 rounded-xl"><Upload size={20} className="text-slate-600" /></div>
                <h3 className="text-lg font-bold text-slate-800">{t('patients.import_title')}</h3>
              </div>
              <button onClick={() => setShowImportModal(false)} className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100"><X size={20} /></button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-5">
              {/* STEP 1: Upload */}
              {importStep === 'upload' && (
                <div className="space-y-5">
                  {/* Drop zone */}
                  <div
                    onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleImportDrop}
                    onClick={() => { const input = document.createElement('input'); input.type = 'file'; input.accept = '.csv,.xlsx'; input.onchange = (e: any) => { if (e.target.files[0]) handleImportFileSelect(e.target.files[0]); }; input.click(); }}
                    className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
                      dragOver ? 'border-blue-400 bg-blue-50' : importFile ? 'border-green-300 bg-green-50' : 'border-slate-300 hover:border-slate-400 bg-slate-50'
                    }`}
                  >
                    {importFile ? (
                      <div className="flex flex-col items-center gap-2">
                        <CheckCircle size={32} className="text-green-500" />
                        <p className="text-sm font-semibold text-green-700">{importFile.name}</p>
                        <p className="text-xs text-slate-400">{(importFile.size / 1024).toFixed(1)} KB</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2">
                        <Upload size={32} className="text-slate-400" />
                        <p className="text-sm font-medium text-slate-600">{t('patients.import_drag_drop')}</p>
                        <p className="text-xs text-slate-400">{t('patients.import_formats')}</p>
                      </div>
                    )}
                  </div>

                  {importFile && (
                    <button onClick={() => setImportFile(null)} className="text-xs text-red-500 hover:text-red-700 font-medium">{t('patients.import_remove_file')}</button>
                  )}

                  {/* Column format guide */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">{t('patients.import_columns_title')}</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="text-left py-1.5 pr-3 font-bold text-slate-600">{t('patients.import_column')}</th>
                            <th className="text-left py-1.5 pr-3 font-bold text-slate-600">{t('patients.import_required')}</th>
                            <th className="text-left py-1.5 font-bold text-slate-600">{t('patients.import_example')}</th>
                          </tr>
                        </thead>
                        <tbody className="text-slate-500">
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3 font-semibold text-slate-700">nombre</td><td className="pr-3 text-red-500 font-bold">{t('common.yes')}</td><td>María</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">apellido</td><td className="pr-3">{t('common.no')}</td><td>López</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">telefono</td><td className="pr-3">{t('common.no')}</td><td>+5491155551234</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">dni</td><td className="pr-3">{t('common.no')}</td><td>35789456</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">email</td><td className="pr-3">{t('common.no')}</td><td>maria@mail.com</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">fecha_nacimiento</td><td className="pr-3">{t('common.no')}</td><td>15/03/1990</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">obra_social</td><td className="pr-3">{t('common.no')}</td><td>OSDE</td></tr>
                          <tr className="border-b border-slate-100"><td className="py-1.5 pr-3">ciudad</td><td className="pr-3">{t('common.no')}</td><td>CABA</td></tr>
                          <tr><td className="py-1.5 pr-3">notas</td><td className="pr-3">{t('common.no')}</td><td>{t('patients.import_notes_example')}</td></tr>
                        </tbody>
                      </table>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-2">{t('patients.import_max_rows')}</p>
                  </div>
                </div>
              )}

              {/* STEP 2: Preview */}
              {importStep === 'preview' && importPreview && (
                <div className="space-y-4">
                  {/* Summary cards */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-green-50 border border-green-200 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-green-700">{importPreview.valid_new}</div>
                      <div className="text-[10px] font-bold text-green-600 uppercase">{t('patients.import_new')}</div>
                    </div>
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-amber-700">{importPreview.duplicates}</div>
                      <div className="text-[10px] font-bold text-amber-600 uppercase">{t('patients.import_duplicates')}</div>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-red-700">{importPreview.errors}</div>
                      <div className="text-[10px] font-bold text-red-600 uppercase">{t('patients.import_errors')}</div>
                    </div>
                  </div>

                  {/* Duplicates section */}
                  {importPreview.duplicates > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={16} className="text-amber-600" />
                        <span className="text-sm font-bold text-amber-800">{t('patients.import_duplicates_found')}</span>
                      </div>
                      <div className="max-h-32 overflow-y-auto space-y-1 mb-3">
                        {importPreview.duplicate_details.slice(0, 10).map((d: any, i: number) => (
                          <div key={i} className="text-xs text-amber-700 flex gap-2">
                            <span className="font-mono text-amber-500">#{d.row}</span>
                            <span>{d.csv_name} ({d.csv_phone})</span>
                            <span className="text-amber-400">→</span>
                            <span>{d.existing_name}</span>
                          </div>
                        ))}
                        {importPreview.duplicate_details.length > 10 && (
                          <div className="text-xs text-amber-500 font-medium">...{t('patients.import_and_more', { count: importPreview.duplicate_details.length - 10 })}</div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setDuplicateAction('skip')}
                          className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 transition-all ${
                            duplicateAction === 'skip' ? 'bg-slate-700 text-white border-slate-700' : 'bg-white text-slate-600 border-slate-300 hover:border-slate-400'
                          }`}
                        >{t('patients.import_skip_duplicates')}</button>
                        <button
                          onClick={() => setDuplicateAction('update')}
                          className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 transition-all ${
                            duplicateAction === 'update' ? 'bg-amber-600 text-white border-amber-600' : 'bg-white text-amber-600 border-amber-300 hover:border-amber-400'
                          }`}
                        >{t('patients.import_update_duplicates')}</button>
                      </div>
                    </div>
                  )}

                  {/* Errors section */}
                  {importPreview.errors > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <XCircle size={16} className="text-red-600" />
                        <span className="text-sm font-bold text-red-800">{t('patients.import_errors_found')}</span>
                      </div>
                      <div className="max-h-24 overflow-y-auto space-y-1">
                        {importPreview.error_details.map((e: any, i: number) => (
                          <div key={i} className="text-xs text-red-600"><span className="font-mono text-red-400">#{e.row}</span> {e.reason}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* STEP 3: Result */}
              {importStep === 'result' && importResult && (
                <div className="space-y-4 text-center py-6">
                  <CheckCircle size={48} className="text-green-500 mx-auto" />
                  <h4 className="text-lg font-bold text-slate-800">{t('patients.import_complete')}</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-md mx-auto">
                    <div className="bg-green-50 rounded-xl p-3"><div className="text-xl font-black text-green-700">{importResult.imported}</div><div className="text-[9px] font-bold text-green-600 uppercase">{t('patients.import_imported')}</div></div>
                    <div className="bg-blue-50 rounded-xl p-3"><div className="text-xl font-black text-blue-700">{importResult.updated}</div><div className="text-[9px] font-bold text-blue-600 uppercase">{t('patients.import_updated')}</div></div>
                    <div className="bg-slate-50 rounded-xl p-3"><div className="text-xl font-black text-slate-500">{importResult.skipped}</div><div className="text-[9px] font-bold text-slate-400 uppercase">{t('patients.import_skipped')}</div></div>
                    <div className="bg-red-50 rounded-xl p-3"><div className="text-xl font-black text-red-600">{importResult.errors}</div><div className="text-[9px] font-bold text-red-500 uppercase">{t('patients.import_errors')}</div></div>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 p-5 border-t border-slate-100 shrink-0 bg-slate-50/80">
              {importStep === 'upload' && (
                <>
                  <button onClick={() => setShowImportModal(false)} className="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-200 rounded-xl text-sm">{t('common.cancel')}</button>
                  <button
                    onClick={handleImportPreview}
                    disabled={!importFile || importLoading}
                    className="px-6 py-2 bg-slate-700 text-white rounded-xl font-bold text-sm shadow-sm hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {importLoading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                    {t('patients.import_preview_btn')}
                  </button>
                </>
              )}
              {importStep === 'preview' && (
                <>
                  <button onClick={() => { setImportStep('upload'); setImportPreview(null); }} className="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-200 rounded-xl text-sm">{t('common.back')}</button>
                  <button
                    onClick={handleImportExecute}
                    disabled={importLoading || importPreview?.valid_new === 0}
                    className="px-6 py-2 bg-green-600 text-white rounded-xl font-bold text-sm shadow-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {importLoading && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                    {t('patients.import_confirm')}
                  </button>
                </>
              )}
              {importStep === 'result' && (
                <button onClick={() => setShowImportModal(false)} className="px-6 py-2 bg-slate-700 text-white rounded-xl font-bold text-sm shadow-sm hover:bg-slate-800">{t('common.close')}</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
