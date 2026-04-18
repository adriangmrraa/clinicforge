import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Edit, Trash2, X, FileText, Brain, Calendar, User, Clock, Stethoscope, Mail, Phone, Upload, CheckCircle, AlertTriangle, XCircle, UserCheck } from 'lucide-react';
import api, { setTenantId } from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import PageHeader from '../components/PageHeader';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

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
  next_appointment_date?: string;
  pending_balance?: number;
  has_appointments?: boolean;
  last_treatment?: string;
  assigned_professional_id?: number | null;
  assigned_professional_name?: string | null;
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

interface ClinicOption {
  id: number;
  clinic_name: string;
}

export default function PatientsView() {
  const { t, language } = useTranslation();
  const { user } = useAuth();
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

  // Bulk assign state
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showBulkAssignModal, setShowBulkAssignModal] = useState(false);
  const [bulkProfId, setBulkProfId] = useState('');

  // Import state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importStep, setImportStep] = useState<'upload' | 'preview' | 'result'>('upload');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importPreview, setImportPreview] = useState<any>(null);
  const [importResult, setImportResult] = useState<any>(null);
  const [duplicateAction, setDuplicateAction] = useState<'skip' | 'update'>('skip');
  const [dragOver, setDragOver] = useState(false);
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [appointmentFilter, setAppointmentFilter] = useState<'all' | 'with' | 'without'>('all');
  const [treatmentFilter, setTreatmentFilter] = useState<string>('all');

  // Debounce ref for semantic search
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch clinics + patients on mount; clean up debounce timeout on unmount
  useEffect(() => {
    api.get<ClinicOption[]>('/admin/chat/tenants').then((res) => {
      setClinics(res.data);
      if (res.data.length >= 1) setSelectedTenantId(res.data[0].id);
    });
    fetchResources();
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  // Refetch patients when tenant changes
  useEffect(() => {
    if (selectedTenantId != null) fetchPatients();
  }, [selectedTenantId]);

  // Filter patients when search term or filter controls change
  useEffect(() => {
    let filtered = patients.filter((patient) => {
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

    if (appointmentFilter === 'with') {
      filtered = filtered.filter(p => p.has_appointments);
    } else if (appointmentFilter === 'without') {
      filtered = filtered.filter(p => !p.has_appointments);
    }

    if (treatmentFilter !== 'all') {
      filtered = filtered.filter(p => p.last_treatment === treatmentFilter);
    }

    setFilteredPatients(filtered);
  }, [searchTerm, patients, appointmentFilter, treatmentFilter]);

  const fetchPatients = async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      // RBAC: professionals only see their own patients
      if (user?.role === 'professional' && user?.professional_id) {
        params.professional_id = String(user.professional_id);
      }
      console.log('[PatientsView] Fetching patients with params:', params);
      const response = await api.get('/admin/patients', { params });
      console.log('[PatientsView] Patients response:', response.data);
      setPatients(response.data);
      setFilteredPatients(response.data);
    } catch (error: any) {
      console.error('[PatientsView] Error fetching patients:', error?.response?.data || error?.message || error);
    } finally {
      setLoading(false);
    }
  };

  const fetchResources = async () => {
    try {
      console.log('[PatientsView] Fetching resources...');
      const [treatResponse, profResponse] = await Promise.all([
        api.get('/admin/treatment-types'),
        api.get('/admin/professionals')
      ]);
      console.log('[PatientsView] Treatment types:', treatResponse.data?.length);
      console.log('[PatientsView] Professionals:', profResponse.data?.length);
      setTreatments(treatResponse.data);
      setProfessionals((profResponse.data || []).filter((p: Professional) => p.is_active));
    } catch (error: any) {
      console.error('[PatientsView] Error fetching resources:', error?.response?.data || error?.message || error);
    }
  };

  const handleSemanticSearch = async (value: string) => {
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

  const handleSemanticSearchDebounced = (value: string) => {
    setSemanticSearchTerm(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => {
      handleSemanticSearch(value);
    }, 300);
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

  const handleBulkAssign = async () => {
    try {
      await api.patch('/admin/patients/bulk-assign-professional', {
        patient_ids: selectedIds,
        professional_id: bulkProfId ? Number(bulkProfId) : null,
      });
      setShowBulkAssignModal(false);
      setBulkProfId('');
      setSelectedIds([]);
      fetchPatients();
    } catch (err) {
      console.error('Error bulk assigning professional:', err);
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
        timeout: 120000,
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
    <div className="p-4 lg:p-6 h-full overflow-y-auto">
      <PageHeader
        title={t('patients.title')}
        subtitle={t('patients.subtitle')}
        icon={<User size={22} />}
        action={
          <div className="flex gap-2 w-full sm:w-auto">
            <button
              onClick={openImportModal}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white/[0.06] hover:bg-white/[0.1] text-white/70 px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shadow-md active:scale-[0.98]"
            >
              <Upload size={18} />
              {t('patients.import_button')}
            </button>
            <button
              onClick={openCreateModal}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white text-[#0a0e1a] hover:bg-white/90 px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shadow-md active:scale-[0.98]"
            >
              <Plus size={20} />
              {t('patients.new_patient')}
            </button>
          </div>
        }
      />

      {/* Clinic filter (CEO multi-tenant) */}
      {clinics.length > 1 && (
        <div className="mb-4">
          <label className="block text-xs font-medium text-white/40 mb-1">{t('chats.clinic_label')}</label>
          <select
            value={selectedTenantId ?? ''}
            onChange={(e) => { const id = Number(e.target.value); setTenantId(String(id)); setSelectedTenantId(id); }}
            className="w-full sm:w-64 px-3 py-2 border border-white/[0.08] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-white/[0.04] text-white"
          >
            {clinics.map((c) => (
              <option key={c.id} value={c.id}>{c.clinic_name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Appointment filter chips */}
        <div className="flex rounded-lg overflow-hidden border border-white/[0.08]">
          <button
            onClick={() => setAppointmentFilter('all')}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${appointmentFilter === 'all' ? 'bg-white/[0.12] text-white' : 'bg-white/[0.02] text-white/40 hover:text-white/60'}`}
          >
            Todos
          </button>
          <button
            onClick={() => setAppointmentFilter('with')}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${appointmentFilter === 'with' ? 'bg-green-500/20 text-green-400' : 'bg-white/[0.02] text-white/40 hover:text-white/60'}`}
          >
            Con turno
          </button>
          <button
            onClick={() => setAppointmentFilter('without')}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${appointmentFilter === 'without' ? 'bg-orange-500/20 text-orange-400' : 'bg-white/[0.02] text-white/40 hover:text-white/60'}`}
          >
            Sin turno
          </button>
        </div>

        {/* Treatment filter */}
        <select
          value={treatmentFilter}
          onChange={(e) => setTreatmentFilter(e.target.value)}
          className="px-3 py-1.5 text-xs border border-white/[0.08] rounded-lg bg-white/[0.04] text-white"
        >
          <option value="all">Todos los tratamientos</option>
          {Array.from(new Set(patients.filter(p => p.last_treatment).map(p => p.last_treatment!))).sort().map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {/* Patient count */}
        <span className="text-xs text-white/30 ml-auto">
          {filteredPatients.length} pacientes
        </span>
      </div>

      {/* Search */}
      <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-white/30" size={18} />
          <input
            type="text"
            placeholder={t('patients.search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent bg-white/[0.04] text-white placeholder-white/20"
          />
        </div>

        {/* Semantic Search */}
        <div className="relative">
          <Brain className="absolute left-3 top-1/2 transform -translate-y-1/2 text-purple-500" size={18} />
          <input
            type="text"
            placeholder={t('patients.search_semantic')}
            value={semanticSearchTerm}
            onChange={(e) => handleSemanticSearchDebounced(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-purple-500/30 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white/[0.04] text-white placeholder-white/20"
          />
          {semanticLoading && (
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
              <div className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-lg mb-3">
          <span className="text-blue-400 text-sm">{selectedIds.length} {t('patients.bulk_selected')}</span>
          <button
            onClick={() => setShowBulkAssignModal(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-white/10 hover:bg-white/20 text-white text-sm rounded transition-colors"
          >
            <UserCheck size={14} />
            {t('patients.assign_professional')}
          </button>
          <button
            onClick={() => setSelectedIds([])}
            className="text-white/50 hover:text-white text-sm ml-auto transition-colors"
          >
            {t('patients.deselect_all')}
          </button>
        </div>
      )}

      {/* Table */}
      <GlassCard image={CARD_IMAGES.patients} hoverScale={false}>
      <div className="overflow-hidden">
        {loading ? (
          <div className="p-8 flex flex-col items-center justify-center gap-3 text-white/50">
            <div className="w-8 h-8 border-2 border-white/20 border-t-blue-400 rounded-full animate-spin" />
            <span className="text-sm">{t('patients.loading')}</span>
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="p-8 text-center text-white/50">
            {t('patients.no_patients_found')}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto hidden md:block">
              <table className="w-full min-w-[1100px]">
                <thead className="bg-white/[0.04]">
                  <tr>
                    <th className="px-4 py-3 text-center text-xs font-medium text-white/50 uppercase tracking-wider w-10">
                      <input
                        type="checkbox"
                        checked={filteredPatients.length > 0 && filteredPatients.every(p => selectedIds.includes(p.id))}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedIds(filteredPatients.map(p => p.id));
                          } else {
                            setSelectedIds([]);
                          }
                        }}
                        className="accent-blue-500 cursor-pointer"
                      />
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.patient')}
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.contact')}
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.dni_obra_social')}
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.next_appointment')}
                    </th>
                    {user?.role === 'ceo' && (
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.balance')}
                    </th>
                    )}
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.date_added')}
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.assigned_professional')}
                    </th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-white/50 uppercase tracking-wider">
                      {t('patients.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white/[0.02] divide-y divide-white/[0.06]">
                  {filteredPatients.map((patient) => (
                    <tr key={patient.id} className="hover:bg-white/[0.04] transition-colors">
                      <td className="px-4 py-4 whitespace-nowrap text-center w-10">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(patient.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedIds(prev => [...prev, patient.id]);
                            } else {
                              setSelectedIds(prev => prev.filter(id => id !== patient.id));
                            }
                          }}
                          className="accent-blue-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10 bg-primary-light rounded-full flex items-center justify-center text-white font-medium">
                            {patient.first_name?.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-4">
                            <div className="flex items-center gap-2">
                              <div className="text-sm font-medium text-white">
                                {patient.first_name} {patient.last_name}
                              </div>
                              {semanticResults.some(r => r.id === patient.id) && (
                                <Brain size={16} className="text-purple-500" />
                              )}
                            </div>
                            {patient.last_treatment && (
                              <span className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400">
                                {patient.last_treatment}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-white">{patient.phone_number}</div>
                        <div className="text-sm text-white/50">{patient.email}</div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-white">{patient.dni || '-'}</div>
                        <div className="text-sm text-white/50">{patient.obra_social || '-'}</div>
                      </td>
                      {/* Next appointment */}
                      <td className="px-3 py-4 whitespace-nowrap">
                        {patient.next_appointment_date ? (
                          <span className="text-xs text-blue-400">
                            {new Date(patient.next_appointment_date).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        ) : (
                          <span className="text-xs text-white/20">Sin turno</span>
                        )}
                      </td>
                      {user?.role === 'ceo' && (
                      <td className="px-3 py-4 whitespace-nowrap">
                        {patient.pending_balance > 0 ? (
                          <span className="text-xs font-semibold text-amber-400">
                            ${Math.round(patient.pending_balance).toLocaleString('es-AR')}
                          </span>
                        ) : null}
                      </td>
                      )}
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-white/50">
                        {new Date(patient.created_at).toLocaleDateString(language)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        {patient.assigned_professional_name ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-indigo-500/10 text-indigo-400">
                            <UserCheck size={12} />
                            {patient.assigned_professional_name}
                          </span>
                        ) : (
                          <span className="text-xs text-white/20">{t('patients.no_professional')}</span>
                        )}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => navigate(`/pacientes/${patient.id}`)}
                            className="p-2 text-white/50 hover:text-primary hover:bg-white/[0.04] rounded-lg transition-colors"
                            title={t('patients.view_chart')}
                          >
                            <FileText size={18} />
                          </button>
                          <button
                            onClick={() => openEditModal(patient)}
                            className="p-2 text-white/50 hover:text-primary hover:bg-white/[0.04] rounded-lg transition-colors"
                            title={t('common.edit')}
                          >
                            <Edit size={18} />
                          </button>
                          <button
                            onClick={() => handleDelete(patient.id)}
                            className="p-2 text-white/50 hover:text-red-400 hover:bg-white/[0.04] rounded-lg transition-colors"
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
            <div className="md:hidden divide-y divide-white/[0.06]">
              {filteredPatients.map((patient) => (
                <div key={patient.id} className="p-4 hover:bg-white/[0.04] transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 bg-primary-light rounded-full flex items-center justify-center text-white font-medium shrink-0">
                        {patient.first_name?.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-white truncate">
                            {patient.first_name} {patient.last_name}
                          </h3>
                          {semanticResults.some(r => r.id === patient.id) && (
                            <Brain size={14} className="text-purple-500 shrink-0" />
                          )}
                        </div>
                        <p className="text-xs text-white/50 truncate">DNI: {patient.dni || '-'}</p>
                        {patient.last_treatment && (
                          <span className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 truncate max-w-full">
                            {patient.last_treatment}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => navigate(`/pacientes/${patient.id}`)}
                        className="p-2 text-white/50 hover:text-primary active:bg-white/[0.04] rounded-lg"
                      >
                        <FileText size={18} />
                      </button>
                      <button
                        onClick={() => openEditModal(patient)}
                        className="p-2 text-white/50 hover:text-primary active:bg-white/[0.04] rounded-lg"
                      >
                        <Edit size={18} />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs text-white/50 mb-3 bg-white/[0.04] p-2 rounded-lg">
                    <div>
                      <span className="block text-[10px] text-white/30 uppercase font-semibold">{t('patients.phone_label')}</span>
                      {patient.phone_number}
                    </div>
                    <div>
                      <span className="block text-[10px] text-white/30 uppercase font-semibold">{t('patients.obra_social')}</span>
                      {patient.obra_social || '-'}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[10px] text-white/30">
                      {t('patients.loaded_on')}: {new Date(patient.created_at).toLocaleDateString(language)}
                    </span>
                    <button
                      onClick={() => handleDelete(patient.id)}
                      className="text-xs text-red-400 font-medium px-2 py-1 hover:bg-red-500/10 rounded"
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
      </GlassCard>

      {/* Modal: estilo slide-over como Agenda (Inspector Clínico) */}
      {showModal && (
        <div key={`patient-modal-${editingPatient?.id ?? 'new'}`} className="fixed inset-0 z-[60]">
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300"
            onClick={closeModal}
          />
          <div className="fixed inset-y-0 right-0 z-[70] w-full md:w-[450px] bg-[#0d1117] backdrop-blur-xl shadow-2xl transform transition-transform duration-300 ease-out border-l border-white/[0.08] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
              <div>
                <h2 className="text-xl font-bold text-white">
                  {editingPatient ? t('patients.edit_patient') : t('patients.new_patient')}
                </h2>
                <p className="text-xs text-white/50">{t('patients.personal_data')}</p>
              </div>
              <button onClick={closeModal} className="p-2 hover:bg-white/[0.04] rounded-full text-white/30 hover:text-white/50 transition-colors">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto flex flex-col">
              <div className="flex-1 p-6 space-y-6">
                {/* Datos personales */}
                <div className="space-y-5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.first_name_req')}</label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                        <input
                          type="text"
                          required
                          value={formData.first_name}
                          onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                          className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                        />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.last_name_req')}</label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                        <input
                          type="text"
                          required
                          value={formData.last_name}
                          onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                          className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.phone_req')}</label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                      <input
                        type="tel"
                        required
                        value={formData.phone_number}
                        onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.dni')}</label>
                    <div className="relative">
                      <FileText className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                      <input
                        type="text"
                        value={formData.dni}
                        onChange={(e) => setFormData({ ...formData, dni: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.email')}</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                      <input
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.obra_social')}</label>
                    <input
                      type="text"
                      value={formData.obra_social}
                      onChange={(e) => setFormData({ ...formData, obra_social: e.target.value })}
                      placeholder={t('patients.obra_social_placeholder')}
                      className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                    />
                  </div>
                  {editingPatient && (
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-white/50 uppercase tracking-wider flex items-center gap-1.5">
                        <UserCheck size={14} />
                        {t('patients.assigned_professional')}
                      </label>
                      <select
                        value={editingPatient.assigned_professional_id ?? ''}
                        onChange={async (e) => {
                          const profId = e.target.value ? Number(e.target.value) : null;
                          try {
                            await api.patch('/admin/patients/bulk-assign-professional', {
                              patient_ids: [editingPatient.id],
                              professional_id: profId,
                            });
                            setEditingPatient({ ...editingPatient, assigned_professional_id: profId });
                          } catch (err) {
                            console.error('Error assigning professional:', err);
                          }
                        }}
                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20 appearance-none cursor-pointer [&>option]:bg-[#0d1117] [&>option]:text-white"
                      >
                        <option value="">{t('patients.no_professional')}</option>
                        {professionals.map(p => (
                          <option key={p.id} value={p.id}>{[p.first_name, p.last_name].filter(Boolean).join(' ')}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.city_neighborhood')}</label>
                      <input
                        type="text"
                        value={formData.city}
                        onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                        placeholder={t('patients.city_placeholder')}
                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.birth_date')}</label>
                      <input
                        type="date"
                        value={formData.birth_date}
                        onChange={(e) => setFormData({ ...formData, birth_date: e.target.value })}
                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                      />
                    </div>
                  </div>
                </div>

                {/* Turno inicial (solo para nuevos) */}
                {!editingPatient && (
                  <div className="pt-4 border-t border-white/[0.06]">
                    <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-4 flex items-center gap-2">
                      <Calendar size={16} />
                      {t('patients.schedule_first_appointment')}
                    </h3>
                    <div className="space-y-5">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.treatment_service')}</label>
                        <div className="relative">
                          <Stethoscope className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                          <select
                            value={appointmentData.treatment_code}
                            onChange={(e) => {
                              const code = e.target.value;
                              const tr = treatments.find(t => t.code === code);
                              setAppointmentData({ ...appointmentData, treatment_code: code, duration_minutes: tr?.default_duration_minutes ?? 30 });
                            }}
                            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20 appearance-none cursor-pointer [&>option]:bg-[#0d1117] [&>option]:text-white"
                          >
                            <option value="">{t('patients.select_treatment')}</option>
                            {treatments.map(t => (
                              <option key={t.code} value={t.code}>{t.name} ({t.category})</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('agenda.professional')}</label>
                        <div className="relative">
                          <User className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                          <select
                            value={appointmentData.professional_id}
                            onChange={(e) => setAppointmentData({ ...appointmentData, professional_id: e.target.value })}
                            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20 appearance-none cursor-pointer [&>option]:bg-[#0d1117] [&>option]:text-white"
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
                          <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.date')}</label>
                          <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                            <input
                              type="date"
                              value={appointmentData.date}
                              onChange={(e) => setAppointmentData({ ...appointmentData, date: e.target.value })}
                              className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                            />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('patients.time')}</label>
                          <div className="relative">
                            <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                            <input
                              type="time"
                              value={appointmentData.time}
                              onChange={(e) => setAppointmentData({ ...appointmentData, time: e.target.value })}
                              className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20"
                            />
                          </div>
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-white/50 uppercase tracking-wider">{t('agenda.duration_min')}</label>
                        <div className="relative">
                          <Clock className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" size={18} />
                          <select
                            value={appointmentData.duration_minutes}
                            onChange={(e) => setAppointmentData({ ...appointmentData, duration_minutes: parseInt(e.target.value) || 30 })}
                            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:bg-white/[0.06] focus:border-blue-500 focus:ring-0 transition-all text-sm text-white placeholder-white/20 appearance-none [&>option]:bg-[#0d1117] [&>option]:text-white"
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

              <div className="flex justify-end gap-3 p-6 border-t border-white/[0.06]">
                <button type="button" onClick={closeModal} className="px-4 py-2.5 text-white/70 bg-white/[0.06] rounded-lg hover:bg-white/[0.1] transition-colors text-sm font-medium">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="px-4 py-2.5 text-[#0a0e1a] bg-white rounded-lg hover:bg-white/90 transition-colors text-sm font-medium">
                  {editingPatient ? t('common.save_changes') : t('patients.create_patient')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk Assign Professional Modal */}
      {showBulkAssignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0d1117] border border-white/[0.06] rounded-xl p-6 w-96 shadow-2xl">
            <div className="flex items-center gap-2 mb-4">
              <UserCheck size={18} className="text-indigo-400" />
              <h3 className="text-white font-semibold">{t('patients.assign_professional')}</h3>
            </div>
            <p className="text-xs text-white/40 mb-4">
              {selectedIds.length} {t('patients.bulk_selected')}
            </p>
            <select
              value={bulkProfId}
              onChange={(e) => setBulkProfId(e.target.value)}
              className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 mb-4 text-sm appearance-none [&>option]:bg-[#0d1117] [&>option]:text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">{t('patients.no_professional')}</option>
              {professionals.map(p => (
                <option key={p.id} value={p.id}>{[p.first_name, p.last_name].filter(Boolean).join(' ')}</option>
              ))}
            </select>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setShowBulkAssignModal(false); setBulkProfId(''); }}
                className="px-4 py-2 text-white/50 hover:text-white text-sm transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleBulkAssign}
                className="px-4 py-2 bg-white text-[#0a0e1a] rounded-lg font-medium text-sm hover:bg-white/90 transition-colors"
              >
                {t('patients.assign_professional')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" onClick={e => e.target === e.currentTarget && setShowImportModal(false)}>
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl shadow-2xl w-full max-w-2xl lg:max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06] shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-white/[0.06] rounded-xl"><Upload size={20} className="text-white/50" /></div>
                <h3 className="text-lg font-bold text-white">{t('patients.import_title')}</h3>
              </div>
              <button onClick={() => setShowImportModal(false)} className="p-2 rounded-xl text-white/30 hover:text-white/50 hover:bg-white/[0.04]"><X size={20} /></button>
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
                      dragOver ? 'border-blue-400 bg-blue-500/10' : importFile ? 'border-green-500/30 bg-green-500/10' : 'border-white/[0.08] hover:border-white/[0.15] bg-white/[0.02]'
                    }`}
                  >
                    {importFile ? (
                      <div className="flex flex-col items-center gap-2">
                        <CheckCircle size={32} className="text-green-400" />
                        <p className="text-sm font-semibold text-green-400">{importFile.name}</p>
                        <p className="text-xs text-white/30">{(importFile.size / 1024).toFixed(1)} KB</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2">
                        <Upload size={32} className="text-white/30" />
                        <p className="text-sm font-medium text-white/50">{t('patients.import_drag_drop')}</p>
                        <p className="text-xs text-white/30">{t('patients.import_formats')}</p>
                      </div>
                    )}
                  </div>

                  {importFile && (
                    <button onClick={() => setImportFile(null)} className="text-xs text-red-400 hover:text-red-300 font-medium">{t('patients.import_remove_file')}</button>
                  )}

                  {/* Column format guide */}
                  <div className="bg-white/[0.03] rounded-xl p-4 border border-white/[0.06]">
                    <h4 className="text-xs font-bold text-white/50 uppercase tracking-wider mb-3">{t('patients.import_columns_title')}</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-white/[0.06]">
                            <th className="text-left py-1.5 pr-3 font-bold text-white/50">{t('patients.import_column')}</th>
                            <th className="text-left py-1.5 pr-3 font-bold text-white/50">{t('patients.import_required')}</th>
                            <th className="text-left py-1.5 font-bold text-white/50">{t('patients.import_example')}</th>
                          </tr>
                        </thead>
                        <tbody className="text-white/50">
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3 font-semibold text-white">nombre</td><td className="pr-3 text-red-400 font-bold">{t('common.yes')}</td><td>María</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">apellido</td><td className="pr-3">{t('common.no')}</td><td>López</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">telefono</td><td className="pr-3">{t('common.no')}</td><td>+5491155551234</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">dni</td><td className="pr-3">{t('common.no')}</td><td>35789456</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">email</td><td className="pr-3">{t('common.no')}</td><td>maria@mail.com</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">fecha_nacimiento</td><td className="pr-3">{t('common.no')}</td><td>15/03/1990</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">obra_social</td><td className="pr-3">{t('common.no')}</td><td>OSDE</td></tr>
                          <tr className="border-b border-white/[0.04]"><td className="py-1.5 pr-3">ciudad</td><td className="pr-3">{t('common.no')}</td><td>CABA</td></tr>
                          <tr><td className="py-1.5 pr-3">notas</td><td className="pr-3">{t('common.no')}</td><td>{t('patients.import_notes_example')}</td></tr>
                        </tbody>
                      </table>
                    </div>
                    <p className="text-[10px] text-white/30 mt-2">{t('patients.import_max_rows')}</p>
                  </div>
                </div>
              )}

              {/* STEP 2: Preview */}
              {importStep === 'preview' && importPreview && (
                <div className="space-y-4">
                  {/* Summary cards */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-green-400">{importPreview.valid_new}</div>
                      <div className="text-[10px] font-bold text-green-400/70 uppercase">{t('patients.import_new')}</div>
                    </div>
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-amber-400">{importPreview.duplicates}</div>
                      <div className="text-[10px] font-bold text-amber-400/70 uppercase">{t('patients.import_duplicates')}</div>
                    </div>
                    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 text-center">
                      <div className="text-2xl font-black text-red-400">{importPreview.errors}</div>
                      <div className="text-[10px] font-bold text-red-400/70 uppercase">{t('patients.import_errors')}</div>
                    </div>
                  </div>

                  {/* Duplicates section */}
                  {importPreview.duplicates > 0 && (
                    <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={16} className="text-amber-400" />
                        <span className="text-sm font-bold text-amber-400">{t('patients.import_duplicates_found')}</span>
                      </div>
                      <div className="max-h-32 overflow-y-auto space-y-1 mb-3">
                        {importPreview.duplicate_details.slice(0, 10).map((d: any, i: number) => (
                          <div key={i} className="text-xs text-amber-300 flex gap-2">
                            <span className="font-mono text-amber-400/70">#{d.row}</span>
                            <span>{d.csv_name} ({d.csv_phone})</span>
                            <span className="text-amber-400/50">→</span>
                            <span>{d.existing_name}</span>
                          </div>
                        ))}
                        {importPreview.duplicate_details.length > 10 && (
                          <div className="text-xs text-amber-400/70 font-medium">...{t('patients.import_and_more', { count: importPreview.duplicate_details.length - 10 })}</div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setDuplicateAction('skip')}
                          className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 transition-all ${
                            duplicateAction === 'skip' ? 'bg-white text-[#0a0e1a] border-white' : 'bg-white/[0.06] text-white/70 border-white/[0.08] hover:border-white/[0.15]'
                          }`}
                        >{t('patients.import_skip_duplicates')}</button>
                        <button
                          onClick={() => setDuplicateAction('update')}
                          className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 transition-all ${
                            duplicateAction === 'update' ? 'bg-amber-500 text-[#0a0e1a] border-amber-500' : 'bg-white/[0.06] text-amber-400 border-white/[0.08] hover:border-amber-500/30'
                          }`}
                        >{t('patients.import_update_duplicates')}</button>
                      </div>
                    </div>
                  )}

                  {/* Errors section */}
                  {importPreview.errors > 0 && (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <XCircle size={16} className="text-red-400" />
                        <span className="text-sm font-bold text-red-400">{t('patients.import_errors_found')}</span>
                      </div>
                      <div className="max-h-24 overflow-y-auto space-y-1">
                        {importPreview.error_details.map((e: any, i: number) => (
                          <div key={i} className="text-xs text-red-300"><span className="font-mono text-red-400/70">#{e.row}</span> {e.reason}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* STEP 3: Result */}
              {importStep === 'result' && importResult && (
                <div className="space-y-4 text-center py-6">
                  <CheckCircle size={48} className="text-green-400 mx-auto" />
                  <h4 className="text-lg font-bold text-white">{t('patients.import_complete')}</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-md mx-auto">
                    <div className="bg-green-500/10 rounded-xl p-3"><div className="text-xl font-black text-green-400">{importResult.imported}</div><div className="text-[9px] font-bold text-green-400/70 uppercase">{t('patients.import_imported')}</div></div>
                    <div className="bg-blue-500/10 rounded-xl p-3"><div className="text-xl font-black text-blue-400">{importResult.updated}</div><div className="text-[9px] font-bold text-blue-400/70 uppercase">{t('patients.import_updated')}</div></div>
                    <div className="bg-white/[0.04] rounded-xl p-3"><div className="text-xl font-black text-white/50">{importResult.skipped}</div><div className="text-[9px] font-bold text-white/30 uppercase">{t('patients.import_skipped')}</div></div>
                    <div className="bg-red-500/10 rounded-xl p-3"><div className="text-xl font-black text-red-400">{importResult.errors}</div><div className="text-[9px] font-bold text-red-400/70 uppercase">{t('patients.import_errors')}</div></div>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 p-5 border-t border-white/[0.06] shrink-0">
              {importStep === 'upload' && (
                <>
                  <button onClick={() => setShowImportModal(false)} className="px-4 py-2 text-white/70 font-semibold hover:bg-white/[0.04] rounded-xl text-sm">{t('common.cancel')}</button>
                  <button
                    onClick={handleImportPreview}
                    disabled={!importFile || importLoading}
                    className="px-6 py-2 bg-white text-[#0a0e1a] rounded-xl font-bold text-sm shadow-sm hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {importLoading && <div className="w-4 h-4 border-2 border-black/20 border-t-black/70 rounded-full animate-spin" />}
                    {t('patients.import_preview_btn')}
                  </button>
                </>
              )}
              {importStep === 'preview' && (
                <>
                  <button onClick={() => { setImportStep('upload'); setImportPreview(null); }} className="px-4 py-2 text-white/70 font-semibold hover:bg-white/[0.04] rounded-xl text-sm">{t('common.back')}</button>
                  <button
                    onClick={handleImportExecute}
                    disabled={importLoading || importPreview?.valid_new === 0}
                    className="px-6 py-2 bg-green-500 text-[#0a0e1a] rounded-xl font-bold text-sm shadow-sm hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {importLoading && <div className="w-4 h-4 border-2 border-black/20 border-t-black/70 rounded-full animate-spin" />}
                    {t('patients.import_confirm')}
                  </button>
                </>
              )}
              {importStep === 'result' && (
                <button onClick={() => setShowImportModal(false)} className="px-6 py-2 bg-white text-[#0a0e1a] rounded-xl font-bold text-sm shadow-sm hover:bg-white/90">{t('common.close')}</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
