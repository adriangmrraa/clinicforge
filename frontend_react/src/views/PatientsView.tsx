import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Edit, Trash2, X, FileText, Brain, Calendar, User, Clock, Stethoscope } from 'lucide-react';
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
  created_at: string;
  status?: string;
  health_conditions?: string[];
}

interface TreatmentType {
  code: string;
  name: string;
  description: string;
  category: string;
}

interface Professional {
  id: number;
  first_name: string;
  last_name?: string;
  specialty?: string;
  is_active: boolean;
}

export default function PatientsView() {
  const { t } = useTranslation();
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
  });

  const [appointmentData, setAppointmentData] = useState({
    treatment_code: '',
    professional_id: '',
    date: '',
    time: ''
  });

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
            notes: "Turno inicial (Alta manual)",
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
    });
    // Clear appointment data on edit
    setAppointmentData({ treatment_code: '', professional_id: '', date: '', time: '' });
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
    });
    // Reset appointment data
    setAppointmentData({ treatment_code: '', professional_id: '', date: '', time: '' });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingPatient(null);
  };

  return (
    <div className="p-4 lg:p-6 h-full overflow-y-auto bg-gray-100">
      <PageHeader
        title={t('patients.title')}
        subtitle={t('patients.subtitle')}
        icon={<User size={22} />}
        action={
          <button
            onClick={openCreateModal}
            className="w-full sm:w-auto flex items-center justify-center gap-2 bg-primary hover:bg-primary-dark text-white px-4 py-2.5 rounded-xl transition-colors text-sm font-medium shadow-md active:scale-[0.98]"
          >
            <Plus size={20} />
            {t('patients.new_patient')}
          </button>
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
                      Paciente
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Contacto
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
                        {new Date(patient.created_at).toLocaleDateString('es-AR')}
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
                      Cargado el {new Date(patient.created_at).toLocaleDateString('es-AR')}
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

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <div className="bg-white rounded-lg w-full max-w-2xl mx-4 my-8">
            <div className="flex justify-between items-center p-4 border-b sticky top-0 bg-white z-10">
              <h2 className="text-xl font-bold">
                {editingPatient ? t('patients.edit_patient') : t('patients.new_patient')}
              </h2>
              <button onClick={closeModal} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6">

              {/* Sections Container */}
              <div className="space-y-6">

                {/* 1. Datos Personales */}
                <div>
                  <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center gap-2">
                    <User size={18} />
                    {t('patients.personal_data')}
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.first_name_req')}
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.first_name}
                        onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.last_name_req')}
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.last_name}
                        onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.phone_req')}
                      </label>
                      <input
                        type="tel"
                        required
                        value={formData.phone_number}
                        onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.dni')}
                      </label>
                      <input
                        type="text"
                        value={formData.dni}
                        onChange={(e) => setFormData({ ...formData, dni: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.email')}
                      </label>
                      <input
                        type="email"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {t('patients.obra_social')}
                      </label>
                      <input
                        type="text"
                        value={formData.obra_social}
                        onChange={(e) => setFormData({ ...formData, obra_social: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                        placeholder={t('patients.obra_social_placeholder')}
                      />
                    </div>
                  </div>
                </div>

                {/* 2. Turno Inicial (Solo para Nuevos) */}
                {!editingPatient && (
                  <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center gap-2">
                      <Calendar size={18} />
                      {t('patients.schedule_first_appointment')}
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          {t('patients.treatment_service')}
                        </label>
                        <div className="relative">
                          <Stethoscope className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
                          <select
                            value={appointmentData.treatment_code}
                            onChange={(e) => setAppointmentData({ ...appointmentData, treatment_code: e.target.value })}
                            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                          >
                            <option value="">{t('patients.select_treatment')}</option>
                            {treatments.map(t => (
                              <option key={t.code} value={t.code}>{t.name} ({t.category})</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          {t('agenda.professional')}
                        </label>
                        <div className="relative">
                          <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
                          <select
                            value={appointmentData.professional_id}
                            onChange={(e) => setAppointmentData({ ...appointmentData, professional_id: e.target.value })}
                            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                          >
                            <option value="">{t('patients.select_professional')}</option>
                            {professionals.map(p => (
                              <option key={p.id} value={p.id}>
                                {[p.first_name, p.last_name].filter(Boolean).join(' ') || t('patients.professional')}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          {t('patients.date')}
                        </label>
                        <input
                          type="date"
                          value={appointmentData.date}
                          onChange={(e) => setAppointmentData({ ...appointmentData, date: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          {t('patients.time')}
                        </label>
                        <div className="relative">
                          <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
                          <input
                            type="time"
                            value={appointmentData.time}
                            onChange={(e) => setAppointmentData({ ...appointmentData, time: e.target.value })}
                            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-white bg-primary rounded-lg hover:bg-primary-dark transition-colors"
                >
                  {editingPatient ? t('common.save_changes') : t('patients.create_patient')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
