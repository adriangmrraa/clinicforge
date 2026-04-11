import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { User, Mail, Calendar, Save, CheckCircle, AlertCircle, Loader2, Phone, Award, Clock, DollarSign } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

interface UserProfile {
  id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  created_at?: string;
  // Professional fields
  professional_id?: number;
  specialty?: string;
  phone_number?: string;
  registration_id?: string;
  google_calendar_id?: string;
  consultation_price?: number;
  working_hours?: Record<string, any>;
  is_active?: boolean;
  is_priority_professional?: boolean;
}

const SPECIALTIES = [
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

const DAYS = [
  { key: 'monday', label: 'Lunes' },
  { key: 'tuesday', label: 'Martes' },
  { key: 'wednesday', label: 'Miércoles' },
  { key: 'thursday', label: 'Jueves' },
  { key: 'friday', label: 'Viernes' },
  { key: 'saturday', label: 'Sábado' },
  { key: 'sunday', label: 'Domingo' },
];

const inputClass = "w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all outline-none text-white placeholder-white/30 text-sm";
const labelClass = "block text-xs font-semibold text-white/50 uppercase tracking-wider mb-1.5";

const ProfileView: React.FC = () => {
  const { user: authUser } = useAuth();
  const { t } = useTranslation();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    specialty: '',
    phone_number: '',
    registration_id: '',
    google_calendar_id: '',
    consultation_price: '',
    working_hours: {} as Record<string, any>,
  });

  useEffect(() => { fetchProfile(); }, []);

  const fetchProfile = async () => {
    try {
      const { data } = await api.get('/auth/profile');
      setProfile(data);
      setForm({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        email: data.email || '',
        specialty: data.specialty || '',
        phone_number: data.phone_number || '',
        registration_id: data.registration_id || '',
        google_calendar_id: data.google_calendar_id || '',
        consultation_price: data.consultation_price != null ? String(data.consultation_price) : '',
        working_hours: data.working_hours || {},
      });
    } catch {
      setError('No se pudo cargar el perfil.');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: Record<string, any> = {
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email,
      };
      if (authUser?.role === 'professional') {
        payload.specialty = form.specialty;
        payload.phone_number = form.phone_number;
        payload.registration_id = form.registration_id;
        payload.google_calendar_id = form.google_calendar_id;
        payload.consultation_price = form.consultation_price ? parseFloat(form.consultation_price) : null;
        payload.working_hours = form.working_hours;
      }
      await api.patch('/auth/profile', payload);
      setSuccess('Perfil actualizado correctamente.');
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al actualizar perfil.');
    } finally {
      setSaving(false);
    }
  };

  const updateWorkingDay = (dayKey: string, field: string, value: any) => {
    setForm(prev => ({
      ...prev,
      working_hours: {
        ...prev.working_hours,
        [dayKey]: { ...(prev.working_hours[dayKey] || {}), [field]: value },
      },
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-blue-400" size={40} />
      </div>
    );
  }

  const isProfessional = authUser?.role === 'professional';

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="shrink-0 p-4 sm:p-6 border-b border-white/[0.06]">
        <PageHeader
          title={t('profile.title')}
          subtitle={t('profile.subtitle')}
          icon={<User size={22} />}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-5xl mx-auto">
          <form onSubmit={handleSave}>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              {/* Left: Summary Card */}
              <div className="lg:col-span-1">
                <GlassCard image={CARD_IMAGES.profile}>
                  <div className="p-5 flex flex-col items-center text-center">
                    <div className="w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 font-bold text-2xl mb-3 border-4 border-white/[0.06]">
                      {form.first_name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <h2 className="text-lg font-bold text-white">{form.first_name} {form.last_name}</h2>
                    <p className="text-xs text-white/40 uppercase font-semibold tracking-wider mt-0.5">
                      {profile?.role === 'ceo' ? 'CEO' : profile?.role === 'secretary' ? 'Secretaria' : form.specialty || 'Profesional'}
                    </p>
                    <div className="mt-4 w-full pt-4 border-t border-white/[0.06] text-left space-y-2.5">
                      <div className="flex items-center gap-2 text-xs text-white/50">
                        <Mail size={14} className="text-blue-400 shrink-0" />
                        <span className="truncate">{form.email}</span>
                      </div>
                      {form.phone_number && (
                        <div className="flex items-center gap-2 text-xs text-white/50">
                          <Phone size={14} className="text-blue-400 shrink-0" />
                          <span>{form.phone_number}</span>
                        </div>
                      )}
                      {profile?.created_at && (
                        <div className="flex items-center gap-2 text-xs text-white/50">
                          <Calendar size={14} className="text-blue-400 shrink-0" />
                          <span>Registrado: {new Date(profile.created_at).toLocaleDateString('es-AR')}</span>
                        </div>
                      )}
                      {profile?.is_active !== undefined && (
                        <div className={`flex items-center gap-2 text-xs ${profile.is_active ? 'text-emerald-400' : 'text-red-400'}`}>
                          <CheckCircle size={14} className="shrink-0" />
                          <span>{profile.is_active ? 'Activo' : 'Inactivo'}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </GlassCard>
              </div>

              {/* Right: Form */}
              <div className="lg:col-span-2 space-y-5">

                {/* Section 1: Datos Personales */}
                <GlassCard hoverScale={false}>
                  <div className="p-5 space-y-4">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <User size={16} className="text-blue-400" /> Datos Personales
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className={labelClass}>{t('profile.first_name')}</label>
                        <input type="text" value={form.first_name} onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} className={inputClass} required />
                      </div>
                      <div>
                        <label className={labelClass}>{t('profile.last_name')}</label>
                        <input type="text" value={form.last_name} onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))} className={inputClass} />
                      </div>
                      <div>
                        <label className={labelClass}>Email</label>
                        <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className={inputClass} />
                      </div>
                      {isProfessional && (
                        <div>
                          <label className={labelClass}>Teléfono</label>
                          <input type="text" value={form.phone_number} onChange={e => setForm(f => ({ ...f, phone_number: e.target.value }))} className={inputClass} placeholder="+54 9 11 ..." />
                        </div>
                      )}
                    </div>
                  </div>
                </GlassCard>

                {/* Section 2: Professional Data (only for professionals) */}
                {isProfessional && (
                  <GlassCard hoverScale={false}>
                    <div className="p-5 space-y-4">
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <Award size={16} className="text-purple-400" /> Datos Profesionales
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className={labelClass}>Especialidad</label>
                          <select value={form.specialty} onChange={e => setForm(f => ({ ...f, specialty: e.target.value }))} className={inputClass}>
                            <option value="">— Seleccionar —</option>
                            {SPECIALTIES.map(s => <option key={s.value} value={s.value}>{s.value}</option>)}
                          </select>
                        </div>
                        <div>
                          <label className={labelClass}>Matrícula</label>
                          <input type="text" value={form.registration_id} onChange={e => setForm(f => ({ ...f, registration_id: e.target.value }))} className={inputClass} placeholder="MP 12345" />
                        </div>
                        <div>
                          <label className={labelClass}>Precio Consulta</label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-sm">$</span>
                            <input type="number" step="1" min="0" value={form.consultation_price} onChange={e => setForm(f => ({ ...f, consultation_price: e.target.value }))} className={`${inputClass} pl-7`} placeholder="0" />
                          </div>
                        </div>
                        <div>
                          <label className={labelClass}>Google Calendar ID</label>
                          <input type="text" value={form.google_calendar_id} onChange={e => setForm(f => ({ ...f, google_calendar_id: e.target.value }))} className={`${inputClass} font-mono text-xs`} placeholder="nombre@gmail.com" />
                        </div>
                      </div>
                    </div>
                  </GlassCard>
                )}

                {/* Section 3: Working Hours (only for professionals) */}
                {isProfessional && (
                  <GlassCard hoverScale={false}>
                    <div className="p-5 space-y-4">
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <Clock size={16} className="text-emerald-400" /> Horarios de Atención
                      </h3>
                      <p className="text-xs text-white/30">Configurá los días y horarios en los que atendés. Los cambios se reflejan en la agenda.</p>
                      <div className="space-y-2">
                        {DAYS.map(day => {
                          const dayData = form.working_hours[day.key] || {};
                          const enabled = dayData.enabled !== false && dayData.start;
                          return (
                            <div key={day.key} className={`flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3 p-2.5 rounded-xl border transition-all ${enabled ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-white/[0.01] border-white/[0.03]'}`}>
                              <label className="flex items-center gap-2 min-w-[110px] cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={!!enabled}
                                  onChange={e => {
                                    if (e.target.checked) {
                                      updateWorkingDay(day.key, 'enabled', true);
                                      if (!dayData.start) updateWorkingDay(day.key, 'start', '09:00');
                                      if (!dayData.end) updateWorkingDay(day.key, 'end', '18:00');
                                    } else {
                                      updateWorkingDay(day.key, 'enabled', false);
                                    }
                                  }}
                                  className="h-4 w-4 rounded border-white/[0.08] text-blue-500 focus:ring-blue-500"
                                />
                                <span className={`text-sm font-medium ${enabled ? 'text-white' : 'text-white/30'}`}>{day.label}</span>
                              </label>
                              {enabled && (
                                <div className="flex items-center gap-2">
                                  <input type="time" value={dayData.start || '09:00'} onChange={e => updateWorkingDay(day.key, 'start', e.target.value)} className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-white text-xs outline-none focus:border-blue-500/30" />
                                  <span className="text-white/20 text-xs">—</span>
                                  <input type="time" value={dayData.end || '18:00'} onChange={e => updateWorkingDay(day.key, 'end', e.target.value)} className="bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-white text-xs outline-none focus:border-blue-500/30" />
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </GlassCard>
                )}

                {/* Messages */}
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 text-sm">
                    <AlertCircle size={16} /> {error}
                  </div>
                )}
                {success && (
                  <div className="flex items-center gap-2 p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20 text-sm">
                    <CheckCircle size={16} /> {success}
                  </div>
                )}

                {/* Save Button */}
                <div className="flex justify-end">
                  <button type="submit" disabled={saving} className="flex items-center gap-2 px-8 py-3 bg-white text-[#0a0e1a] rounded-xl font-bold hover:bg-white/90 active:scale-[0.98] transition-all disabled:opacity-50">
                    {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
                    {t('common.save_changes')}
                  </button>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ProfileView;
