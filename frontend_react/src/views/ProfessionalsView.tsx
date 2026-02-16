import { useState, useEffect } from 'react';
import {
  Plus, Edit, Clock, Calendar, Mail, Phone, User,
  ChevronDown, ChevronUp, CheckCircle, XCircle, Save, X, ClipboardList
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

interface Professional {
  id: number;
  name: string;
  email?: string;
  phone?: string;
  specialty?: string;
  license_number?: string;
  is_active: boolean;
  working_hours?: WorkingHours;
  availability?: any;
  tenant_id?: number; // Sede/clínica a la que pertenece (para mostrar en edición)
}

interface WorkingHours {
  monday: DayConfig;
  tuesday: DayConfig;
  wednesday: DayConfig;
  thursday: DayConfig;
  friday: DayConfig;
  saturday: DayConfig;
  sunday: DayConfig;
}

interface DayConfig {
  enabled: boolean;
  slots: TimeSlot[];
}

interface TimeSlot {
  start: string;  // HH:mm
  end: string;    // HH:mm
}

const DAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;
const DAYS = DAY_KEYS.map((key) => ({ key }));

const SPECIALTIES: { value: string; key: string }[] = [
  { value: 'Odontología General', key: 'specialty_general' },
  { value: 'Ortodoncia', key: 'specialty_orthodontics' },
  { value: 'Endodoncia', key: 'specialty_endodontics' },
  { value: 'Periodoncia', key: 'specialty_periodontics' },
  { value: 'Cirugía Oral', key: 'specialty_oral_surgery' },
  { value: 'Prótesis Dental', key: 'specialty_prosthodontics' },
  { value: 'Odontopediatría', key: 'specialty_pediatric' },
  { value: 'Implantología', key: 'specialty_implantology' },
  { value: 'Estética Dental', key: 'specialty_aesthetic' },
];

interface ClinicOption {
  id: number;
  clinic_name: string;
}

export default function ProfessionalsView() {
  const { t } = useTranslation();
    const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingProfessional, setEditingProfessional] = useState<Professional | null>(null);
  const [expandedDays, setExpandedDays] = useState<Record<number, string[]>>({});

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    specialty: '',
    license_number: '',
    is_active: true,
    working_hours: createDefaultWorkingHours(),
    tenant_id: null as number | null,
  });

  function createDefaultWorkingHours(): WorkingHours {
    const wh: any = {};
    DAY_KEYS.forEach((key) => {
      wh[key] = {
        enabled: key !== 'sunday',
        slots: key !== 'sunday' ? [{ start: '09:00', end: '18:00' }] : []
      };
    });
    return wh as WorkingHours;
  }

  useEffect(() => {
    fetchProfessionals();
  }, []);

  useEffect(() => {
    api.get<ClinicOption[]>('/admin/chat/tenants').then((res) => {
      setClinics(res.data || []);
    }).catch(() => setClinics([]));
  }, []);

  // Al crear: si hay clínicas y aún no eligió una, preseleccionar la primera
  useEffect(() => {
    if (editingProfessional?.id === 0 && clinics.length > 0 && formData.tenant_id == null) {
      setFormData((prev) => ({ ...prev, tenant_id: clinics[0].id }));
    }
  }, [editingProfessional?.id, clinics, formData.tenant_id]);

  const fetchProfessionals = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/professionals');
      const mappedData = response.data.map((p: any) => ({
        ...p,
        name: p.name || `${p.first_name} ${p.last_name || ''}`.trim()
      }));
      setProfessionals(mappedData);
    } catch (error) {
      console.error('Error fetching professionals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingProfessional && editingProfessional.id) {
        await api.put(`/admin/professionals/${editingProfessional.id}`, formData);
      } else {
        const payload: Record<string, unknown> = { ...formData };
        if (formData.tenant_id != null) payload.tenant_id = formData.tenant_id;
        await api.post('/admin/professionals', payload);
      }
      fetchProfessionals();
      closeModal();
    } catch (error: unknown) {
      console.error('Error saving professional:', error);
      const msg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(msg || t('alerts.error_save_professional'));
    }
  };

  const handleToggleActive = async (professional: Professional) => {
    try {
      await api.put(`/admin/professionals/${professional.id}`, {
        is_active: !professional.is_active,
        name: professional.name,
      });
      fetchProfessionals();
    } catch (error) {
      console.error('Error toggling active status:', error);
    }
  };

  const openEditModal = (professional: Professional) => {
    setEditingProfessional(professional);
    setFormData({
      name: professional.name,
      email: professional.email || '',
      phone: professional.phone || '',
      specialty: professional.specialty || '',
      license_number: professional.license_number || '',
      is_active: professional.is_active,
      working_hours: professional.working_hours || createDefaultWorkingHours(),
      tenant_id: professional.tenant_id ?? null,
    });
    setExpandedDays({});
  };

  const openCreateModal = () => {
    setEditingProfessional({
      id: 0,
      name: '',
      email: '',
      phone: '',
      specialty: '',
      license_number: '',
      is_active: true,
      working_hours: createDefaultWorkingHours(),
    });
    setFormData({
      name: '',
      email: '',
      phone: '',
      specialty: '',
      license_number: '',
      is_active: true,
      working_hours: createDefaultWorkingHours(),
      tenant_id: clinics.length > 0 ? clinics[0].id : null,
    });
    setExpandedDays({});
  };

  const closeModal = () => {
    setEditingProfessional(null);
  };

  const toggleDayExpansion = (day: string) => {
    setExpandedDays(prev => {
      const current = prev[-1] || [];
      const isMobile = window.innerWidth < 768;

      if (isMobile) {
        // En mobile solo uno abierto a la vez (Acordeón real)
        return { ...prev, [-1]: current.includes(day) ? [] : [day] };
      }

      // En desktop mantenemos multi-expandible si se desea o el comportamiento anterior
      if (current.includes(day)) {
        return { ...prev, [-1]: current.filter(d => d !== day) };
      }
      return { ...prev, [-1]: [...current, day] };
    });
  };

  const toggleDayEnabled = (dayKey: keyof WorkingHours) => {
    setFormData(prev => ({
      ...prev,
      working_hours: {
        ...prev.working_hours,
        [dayKey]: {
          ...prev.working_hours[dayKey],
          enabled: !prev.working_hours[dayKey].enabled,
          slots: !prev.working_hours[dayKey].enabled && prev.working_hours[dayKey].slots.length === 0
            ? [{ start: '09:00', end: '18:00' }] : prev.working_hours[dayKey].slots
        }
      }
    }));
  };

  const addTimeSlot = (dayKey: keyof WorkingHours) => {
    setFormData(prev => ({
      ...prev,
      working_hours: {
        ...prev.working_hours,
        [dayKey]: {
          ...prev.working_hours[dayKey],
          slots: [...prev.working_hours[dayKey].slots, { start: '09:00', end: '18:00' }]
        }
      }
    }));
  };

  const removeTimeSlot = (dayKey: keyof WorkingHours, index: number) => {
    setFormData(prev => ({
      ...prev,
      working_hours: {
        ...prev.working_hours,
        [dayKey]: {
          ...prev.working_hours[dayKey],
          slots: prev.working_hours[dayKey].slots.filter((_, i) => i !== index)
        }
      }
    }));
  };

  const updateTimeSlot = (dayKey: keyof WorkingHours, index: number, field: 'start' | 'end', value: string) => {
    setFormData(prev => ({
      ...prev,
      working_hours: {
        ...prev.working_hours,
        [dayKey]: {
          ...prev.working_hours[dayKey],
          slots: prev.working_hours[dayKey].slots.map((slot, i) =>
            i === index ? { ...slot, [field]: value } : slot
          )
        }
      }
    }));
  };

  const getActiveProfessionals = () => professionals.filter(p => p.is_active).length;

  const getTotalSlots = (wh?: WorkingHours) => {
    if (!wh) return 0;
    return Object.values(wh).reduce((total, day) => total + (day.enabled ? day.slots.length : 0), 0);
  };

  return (
    <div className="flex flex-col h-full bg-gray-100 overflow-hidden">
      {/* Scrollable Container with Scroll Isolation */}
      <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6">

        {/* Header - Fixed internally with padding */}
        <PageHeader
          title={t('professionals.title')}
          subtitle={t('professionals.subtitle')}
          icon={<User size={22} />}
          action={
            <button
              onClick={openCreateModal}
              className="w-full sm:w-auto flex items-center justify-center gap-2 bg-medical-600 hover:bg-medical-700 text-white px-5 py-2.5 rounded-xl transition-all shadow-md active:scale-[0.98] text-sm font-semibold"
            >
              <Plus size={20} />
              {t('professionals.new_professional')}
            </button>
          }
        />

        {/* Stats Grid - Responsive behavior */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl shadow-sm p-4 border-l-4 border-primary">
            <div className="text-xs text-gray-500 uppercase font-bold tracking-tight">{t('professionals.total_staff')}</div>
            <div className="text-3xl font-black mt-1 text-gray-900">{professionals.length}</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-4 border-l-4 border-green-500">
            <div className="text-xs text-gray-500 uppercase font-bold tracking-tight">{t('professionals.active_doctors')}</div>
            <div className="text-3xl font-black mt-1 text-green-600">{getActiveProfessionals()}</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-4 border-l-4 border-gray-300 sm:col-span-2 lg:col-span-1">
            <div className="text-xs text-gray-500 uppercase font-bold tracking-tight">{t('professionals.on_pause')}</div>
            <div className="text-3xl font-black mt-1 text-gray-400">
              {professionals.length - getActiveProfessionals()}
            </div>
          </div>
        </div>

        {/* Professionals Grid - The core responsive refactor */}
        {loading ? (
          <div className="flex items-center justify-center p-12 bg-white rounded-2xl border border-gray-100 shadow-sm">
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
              <p className="text-gray-500 font-medium">{t('professionals.loading_team')}</p>
            </div>
          </div>
        ) : professionals.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-2xl border border-gray-100 shadow-sm">
            <div className="mx-auto w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center text-gray-300 mb-4">
              <ClipboardList size={32} />
            </div>
            <h3 className="text-lg font-bold text-gray-800">{t('professionals.no_professionals')}</h3>
            <p className="text-gray-500 max-w-xs mx-auto text-sm mb-6">{t('professionals.empty_hint')}</p>
            <button
              onClick={openCreateModal}
              className="inline-flex items-center justify-center gap-2 bg-medical-600 hover:bg-medical-700 text-white px-6 py-3 rounded-xl font-semibold shadow-md hover:shadow-lg transition-all"
            >
              <Plus size={20} />
              {t('professionals.add_first')}
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {professionals.map((professional: Professional) => (
              <div
                key={professional.id}
                className="bg-white rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-all overflow-hidden flex flex-col group"
              >
                {/* Card Header Profile */}
                <div className="p-5 flex items-start gap-4">
                  <div className={`w-14 h-14 rounded-2xl shrink-0 flex items-center justify-center text-white font-black text-xl shadow-inner ${professional.is_active ? 'bg-primary' : 'bg-gray-400'
                    }`}>
                    {professional.name.charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h3 className="font-bold text-gray-900 truncate leading-tight">
                        Dr. {professional.name}
                      </h3>
                      {professional.is_active ? (
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm shadow-green-200"></div>
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-gray-300"></div>
                      )}
                    </div>
                    <p className="text-[10px] font-black text-primary bg-primary/5 inline-block px-2 py-0.5 rounded mt-1 uppercase tracking-wider">
                      {professional.specialty || t('professionals.general_fallback')}
                    </p>
                    {/* Mobile Attribute List Format */}
                    <div className="grid grid-cols-2 gap-3 mt-3 sm:hidden">
                      {professional.email && (
                        <div>
                          <span className="block text-[9px] font-black text-gray-400 uppercase tracking-tight mb-0.5">{t('professionals.email')}</span>
                          <div className="flex items-center gap-1.5 text-xs text-gray-600 truncate font-semibold">
                            <Mail size={10} className="text-primary/60" /> {professional.email}
                          </div>
                        </div>
                      )}
                      {professional.phone && (
                        <div>
                          <span className="block text-[9px] font-black text-gray-400 uppercase tracking-tight mb-0.5">{t('professionals.whatsapp')}</span>
                          <div className="flex items-center gap-1.5 text-xs text-gray-600 font-semibold">
                            <Phone size={10} className="text-primary/60" /> {professional.phone}
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Desktop Inline Info */}
                    <div className="hidden sm:space-y-1 sm:mt-2 sm:block">
                      {professional.email && (
                        <div className="flex items-center gap-2 text-[11px] text-gray-500 truncate">
                          <Mail size={12} className="text-gray-400" /> {professional.email}
                        </div>
                      )}
                      {professional.phone && (
                        <div className="flex items-center gap-2 text-[11px] text-gray-500">
                          <Phone size={12} className="text-gray-400" /> {professional.phone}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card Divider Text */}
                <div className="px-5 py-3 border-t border-gray-50 flex items-center justify-between bg-gray-50/30">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-gray-500 uppercase tracking-wider">
                    <Clock size={14} className="text-primary/70" />
                    {getTotalSlots(professional.working_hours)} Bloques Disponibles
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => openEditModal(professional)}
                      className="p-3 text-gray-500 hover:text-primary hover:bg-white rounded-xl transition-all border border-transparent hover:border-gray-200 min-h-[44px] min-w-[44px] flex items-center justify-center"
                      title={t('professionals.edit_profile')}
                    >
                      <Edit size={18} />
                    </button>
                    <button
                      onClick={() => handleToggleActive(professional)}
                      className={`p-3 rounded-xl transition-all border border-transparent min-h-[44px] min-w-[44px] flex items-center justify-center ${professional.is_active
                        ? 'text-gray-400 hover:text-red-600 hover:bg-red-50 hover:border-red-100'
                        : 'text-gray-400 hover:text-green-600 hover:bg-green-50 hover:border-green-100'
                        }`}
                      title={professional.is_active ? 'Desactivar' : 'Activar'}
                    >
                      {professional.is_active ? <XCircle size={18} /> : <CheckCircle size={18} />}
                    </button>
                  </div>
                </div>

                {/* Availability Sub-Card */}
                {professional.working_hours && getTotalSlots(professional.working_hours) > 0 && (
                  <div className="px-5 pb-5">
                    <button
                      onClick={() => {
                        const current = expandedDays[professional.id] || [];
                        setExpandedDays({
                          ...expandedDays,
                          [professional.id]: current.includes('toggle') ? [] : ['toggle']
                        });
                      }}
                      className="w-full flex items-center justify-between p-2.5 bg-gray-50 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-100 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-gray-400" />
                        <span>{t('professionals.view_schedules')}</span>
                      </div>
                      {(expandedDays[professional.id] || []).includes('toggle') ? (
                        <ChevronUp size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                    </button>
                    {(expandedDays[professional.id] || []).includes('toggle') && (
                      <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-2 duration-300">
                        {DAYS.map(day => {
                          const config = professional.working_hours?.[day.key];
                          if (config?.enabled && config.slots.length > 0) {
                            return (
                              <div key={day.key} className="flex items-start justify-between text-[11px] border-b border-gray-50 pb-1.5 last:border-0 last:pb-0">
                                <span className="font-bold text-gray-700">{day.label}</span>
                                <div className="text-right text-gray-500 font-medium">
                                  {config.slots.map((s, idx) => (
                                    <div key={idx} className="bg-white px-1.5 py-0.5 rounded border border-gray-100 mb-0.5 inline-block ml-1">
                                      {s.start} - {s.end}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal - Optimized for Mobile & Desktop */}
      {editingProfessional !== null && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center z-50 p-4 sm:p-6 lg:p-12 animate-in fade-in duration-300">
          <div className="bg-white rounded-3xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-bottom-8 duration-500">

            {/* Modal Header */}
            <div className="flex justify-between items-center p-6 border-b border-gray-100 bg-white sticky top-0 z-10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-primary/10 rounded-2xl flex items-center justify-center text-primary">
                  {editingProfessional.id ? <Edit size={24} /> : <Plus size={24} />}
                </div>
                <div>
                  <h2 className="text-xl font-black text-gray-900">
                    {editingProfessional.id ? t('professionals.edit_profile_medical') : t('professionals.new_team_member')}
                  </h2>
                  <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mt-0.5">
                    {editingProfessional.id ? `ID: PROF-${editingProfessional.id}` : t('professionals.register_new')}
                  </p>
                </div>
              </div>
              <button
                onClick={closeModal}
                className="p-2.5 hover:bg-gray-50 rounded-2xl transition-all text-gray-400 hover:text-gray-900 border border-transparent hover:border-gray-100"
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Content - Internal Scroll Isolation */}
            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8 bg-gray-50/50">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">

                {/* Column 1: Info */}
                <div className="lg:col-span-5 space-y-8">
                  <div className="bg-white p-6 rounded-3xl border border-gray-200/60 shadow-sm space-y-6">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] flex items-center gap-2 mb-2">
                      <ClipboardList size={16} className="text-primary" /> {t('professionals.profile_professional')}
                    </h3>

                    <div className="space-y-4">
                      {/* Sede/Clínica: selector al crear, solo lectura al editar */}
                      {editingProfessional.id ? (
                        <div className="group">
                          <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1">
                            {t('professionals.clinic_label')}
                          </label>
                          <div className="w-full px-4 py-3 bg-gray-100 border border-gray-200 rounded-2xl text-sm font-semibold text-gray-800">
                            {clinics.find((c) => c.id === (editingProfessional.tenant_id ?? formData.tenant_id))?.clinic_name ?? t('approvals.location_id').replace('{{id}}', String(editingProfessional.tenant_id ?? formData.tenant_id ?? '—'))}
                          </div>
                          <p className="text-[11px] text-gray-400 mt-1 ml-1">{t('professionals.profile_linked_hint')}</p>
                        </div>
                      ) : clinics.length > 0 && (
                        <div className="group">
                          <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                            {t('professionals.clinic_branch')} <span className="text-red-500">*</span>
                          </label>
                          <select
                            required
                            value={formData.tenant_id ?? ''}
                            onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value ? parseInt(e.target.value, 10) : null })}
                            className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800 appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2020%2020%22%3E%3Cpath%20stroke%3D%22%236b7280%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%221.5%22%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:1.25rem_1.25rem] bg-[right_0.75rem_center] bg-no-repeat"
                          >
                            <option value="">{t('professionals.select_clinic')}</option>
                            {clinics.map((c) => (
                              <option key={c.id} value={c.id}>{c.clinic_name}</option>
                            ))}
                          </select>
                          <p className="text-[11px] text-gray-400 mt-1 ml-1">{t('professionals.link_professional_hint')}</p>
                        </div>
                      )}

                      <div className="group">
                        <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                          {t('professionals.name_lastname')} <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800"
                          placeholder={t('professionals.placeholder_name')}
                        />
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="group">
                          <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                            {t('professionals.specialty')}
                          </label>
                          <select
                            value={formData.specialty}
                            onChange={(e) => setFormData({ ...formData, specialty: e.target.value })}
                            className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800 appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2020%2020%22%3E%3Cpath%20stroke%3D%22%236b7280%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%221.5%22%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:1.25rem_1.25rem] bg-[right_0.75rem_center] bg-no-repeat"
                          >
                            <option value="">{t('professionals.select')}</option>
                            {SPECIALTIES.map(s => (
                              <option key={s.value} value={s.value}>{t('approvals.' + s.key)}</option>
                            ))}
                          </select>
                        </div>

                        <div className="group">
                          <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                            {t('professionals.license_number')}
                          </label>
                          <input
                            type="text"
                            value={formData.license_number}
                            onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
                            className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800"
                            placeholder={t('professionals.placeholder_license')}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white p-6 rounded-3xl border border-gray-200/60 shadow-sm space-y-6">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] flex items-center gap-2 mb-2">
                      <Mail size={16} className="text-primary" /> {t('professionals.contact_official')}
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="group">
                        <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                          {t('professionals.email')}
                        </label>
                        <input
                          type="email"
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800"
                          placeholder="doc@clinica.com"
                        />
                      </div>

                      <div className="group">
                        <label className="block text-[11px] font-black text-gray-400 uppercase tracking-wider mb-1.5 ml-1 transition-colors group-focus-within:text-primary">
                          {t('professionals.whatsapp')}
                        </label>
                        <input
                          type="tel"
                          value={formData.phone}
                          onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none text-sm font-semibold text-gray-800"
                          placeholder="+54 9..."
                        />
                      </div>
                    </div>

                    <div className="pt-2 border-t border-gray-50">
                      <label className="flex items-center gap-3 p-4 bg-gray-50 rounded-2xl cursor-pointer hover:bg-white border border-transparent hover:border-primary/20 transition-all group">
                        <div className="relative">
                          <input
                            type="checkbox"
                            checked={formData.is_active}
                            onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-sm font-bold text-gray-800 group-hover:text-green-600 transition-colors">{t('professionals.active_staff')}</span>
                          <span className="text-[10px] text-gray-400 uppercase font-black">{t('professionals.enabled_global_agenda')}</span>
                        </div>
                      </label>
                    </div>
                  </div>
                </div>

                {/* Column 2: Working Hours */}
                <div className="lg:col-span-1 border-l border-gray-100 hidden lg:block"></div>

                <div className="lg:col-span-6 space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] flex items-center gap-2">
                        <Clock size={16} className="text-primary" /> {t('professionals.configure_calendars')}
                      </h3>
                      <p className="text-[10px] text-gray-400 font-bold uppercase mt-1 tracking-wider">{t('professionals.define_weekly')}</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {DAYS.map(day => {
                      const dayKey = day.key as keyof WorkingHours;
                      const config = formData.working_hours[dayKey];
                      const isExpanded = (expandedDays[-1] || []).includes(dayKey);

                      return (
                        <div
                          key={day.key}
                          className={`rounded-3xl border transition-all duration-300 overflow-hidden ${config.enabled
                            ? 'bg-white border-primary/20 shadow-sm'
                            : 'bg-white/40 border-gray-100 grayscale-[0.5]'
                            }`}
                        >
                          <div
                            className={`flex items-center justify-between p-4 cursor-pointer transition-colors ${isExpanded ? 'bg-primary/5' : 'hover:bg-gray-50'
                              }`}
                            onClick={() => config.enabled && toggleDayExpansion(dayKey)}
                          >
                            <div className="flex items-center gap-4">
                              <label
                                className="relative inline-flex items-center cursor-pointer"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <input
                                  type="checkbox"
                                  className="sr-only peer"
                                  checked={config.enabled}
                                  onChange={() => toggleDayEnabled(dayKey)}
                                />
                                <div className="w-10 h-5 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                              </label>
                              <span className={`text-sm font-black uppercase tracking-widest ${config.enabled ? 'text-gray-900' : 'text-gray-400'
                                }`}>
                                {t('approvals.day_' + day.key)}
                              </span>
                            </div>

                            <div className="flex items-center gap-4">
                              {config.enabled && (
                                <div className="flex -space-x-1">
                                  {config.slots.map((_, i) => (
                                    <div key={i} className="w-2.5 h-2.5 rounded-full border-2 border-white bg-primary shadow-sm"></div>
                                  ))}
                                </div>
                              )}
                              {config.enabled && (
                                <div className={`transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}>
                                  <ChevronDown size={20} className="text-gray-400" />
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Slots Container - Smooth expansion */}
                          {isExpanded && config.enabled && (
                            <div className="p-5 pt-2 space-y-3 bg-gradient-to-b from-primary/5 to-white animate-in slide-in-from-top-4 duration-300">
                              {config.slots.map((slot, index) => (
                                <div key={index} className="flex items-center gap-3 animate-in fade-in duration-500">
                                  <div className="flex-1 grid grid-cols-2 gap-px bg-gray-200 rounded-2xl overflow-hidden shadow-sm border border-gray-100">
                                    <div className="bg-white p-3 flex flex-col items-center">
                                      <span className="text-[9px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">{t('professionals.entrada')}</span>
                                      <input
                                        type="time"
                                        value={slot.start}
                                        onChange={(e) => updateTimeSlot(dayKey, index, 'start', e.target.value)}
                                        className="text-sm font-bold text-gray-800 outline-none w-full text-center hover:text-primary transition-colors"
                                      />
                                    </div>
                                    <div className="bg-white p-3 flex flex-col items-center border-l border-gray-50">
                                      <span className="text-[9px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">{t('professionals.salida')}</span>
                                      <input
                                        type="time"
                                        value={slot.end}
                                        onChange={(e) => updateTimeSlot(dayKey, index, 'end', e.target.value)}
                                        className="text-sm font-bold text-gray-800 outline-none w-full text-center hover:text-primary transition-colors"
                                      />
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => removeTimeSlot(dayKey, index)}
                                    className="p-3 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-all border border-transparent hover:border-red-100"
                                  >
                                    <X size={16} />
                                  </button>
                                </div>
                              ))}
                              <button
                                type="button"
                                onClick={() => addTimeSlot(dayKey)}
                                className="w-full py-3 bg-white border-2 border-dashed border-primary/20 rounded-2xl text-[11px] font-black uppercase tracking-widest text-primary/60 hover:text-primary hover:border-primary/40 hover:bg-primary/5 transition-all shadow-sm"
                              >
                                + {t('professionals.add_time_block')}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </form>

            {/* Modal Footer - Sticky Bottom on Mobile */}
            <div className="p-6 border-t border-gray-100 bg-white flex flex-col sm:flex-row justify-end gap-3 sticky bottom-0 z-10 shadow-[0_-4px_20px_-10px_rgba(0,0,0,0.1)]">
              <button
                type="button"
                onClick={closeModal}
                className="w-full sm:w-auto px-8 py-3.5 text-sm font-black uppercase tracking-widest text-gray-400 hover:text-gray-900 border border-transparent hover:border-gray-100 rounded-2xl transition-all min-h-[44px]"
              >
                {t('professionals.close')}
              </button>
              <button
                type="submit"
                onClick={handleSubmit}
                className="w-full sm:w-auto px-10 py-3.5 text-sm font-black uppercase tracking-widest text-white bg-primary hover:bg-primary-dark rounded-2xl shadow-xl shadow-primary/20 hover:shadow-primary/40 transform hover:-translate-y-1 active:scale-95 transition-all flex items-center justify-center gap-3 min-h-[44px]"
              >
                <Save size={20} />
                {editingProfessional?.id ? t('professionals.save_changes') : t('professionals.sign_medical_alta')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
