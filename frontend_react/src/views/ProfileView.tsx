import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { User, Mail, Calendar, Save, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
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
    google_calendar_id?: string;
}

const ProfileView: React.FC = () => {
    const { user: authUser } = useAuth();
    const { t } = useTranslation();
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Form State
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [calendarId, setCalendarId] = useState('');

    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = async () => {
        try {
            const response = await api.get('/auth/profile');
            const data = response.data;
            setProfile(data);
            setFirstName(data.first_name || '');
            setLastName(data.last_name || '');
            setCalendarId(data.google_calendar_id || '');
        } catch (err: any) {
            setError("No se pudo cargar el perfil.");
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
            await api.patch('/auth/profile', {
                first_name: firstName,
                last_name: lastName,
                google_calendar_id: authUser?.role === 'professional' ? calendarId : undefined
            });
            setSuccess("Perfil actualizado correctamente.");
            // Refresh local auth context or state if needed (optional)
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error al actualizar perfil.");
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="animate-spin text-medical-600" size={40} />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto animate-fadeIn p-4 lg:p-6">
            <PageHeader
                title={t('profile.title')}
                subtitle={t('profile.subtitle')}
                icon={<User size={22} />}
            />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Left: Summary Card */}
                <div className="md:col-span-1">
                    <GlassCard image={CARD_IMAGES.profile}>
                    <div className="p-6 flex flex-col items-center text-center">
                        <div className="w-24 h-24 rounded-full bg-medical-500/10 flex items-center justify-center text-medical-400 font-bold text-2xl sm:text-3xl mb-4 border-4 border-white/[0.06]">
                            {firstName?.[0]?.toUpperCase() || profile?.email?.[0]?.toUpperCase()}
                        </div>
                        <h2 className="text-xl font-bold text-white">{firstName} {lastName}</h2>
                        <p className="text-sm text-secondary uppercase font-semibold tracking-wider mt-1">{profile?.role}</p>
                        <div className="mt-6 w-full pt-6 border-t border-white/[0.06] text-left space-y-4">
                            <div className="flex items-center gap-3 text-sm text-white/60">
                                <Mail size={16} className="text-medical-400" />
                                <span className="truncate">{profile?.email}</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm text-white/60">
                                <Calendar size={16} className="text-medical-400" />
                                <span>{t('profile.registered_at')}: {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : new Date().toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>
                    </GlassCard>
                </div>

                {/* Right: Settings Form */}
                <div className="md:col-span-2 space-y-6">
                    <GlassCard image={CARD_IMAGES.tech} hoverScale={false}>
                    <div className="p-8">
                        <form onSubmit={handleSave} className="space-y-6">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                                <div>
                                    <label className="block text-sm font-medium text-white/60 mb-2">{t('profile.first_name')}</label>
                                    <input
                                        type="text"
                                        value={firstName}
                                        onChange={(e) => setFirstName(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:ring-2 focus:ring-medical-500 focus:bg-white/[0.06] transition-all outline-none text-white placeholder-white/30"
                                        placeholder={t('profile.placeholder_first_name')}
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-white/60 mb-2">{t('profile.last_name')}</label>
                                    <input
                                        type="text"
                                        value={lastName}
                                        onChange={(e) => setLastName(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:ring-2 focus:ring-medical-500 focus:bg-white/[0.06] transition-all outline-none text-white placeholder-white/30"
                                        placeholder={t('profile.placeholder_last_name')}
                                    />
                                </div>
                            </div>

                            {authUser?.role === 'professional' && (
                                <div className="pt-6 border-t border-white/[0.06]">
                                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                        <Calendar size={20} className="text-medical-400" />
                                        {t('profile.agenda_settings')}
                                    </h3>
                                    <div className="bg-blue-500/10 p-4 rounded-xl mb-4 text-sm text-blue-400 leading-relaxed border border-blue-500/20">
                                        <p>{t('profile.calendar_help')}</p>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-white/60 mb-2">{t('profile.calendar_id_label')}</label>
                                        <input
                                            type="text"
                                            value={calendarId}
                                            onChange={(e) => setCalendarId(e.target.value)}
                                            className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl focus:ring-2 focus:ring-medical-500 focus:bg-white/[0.06] transition-all font-mono text-sm outline-none text-white placeholder-white/30"
                                            placeholder={t('profile.calendar_id_placeholder')}
                                        />
                                    </div>
                                </div>
                            )}

                            {error && (
                                <div className="flex items-center gap-2 p-4 bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 text-sm animate-fadeIn">
                                    <AlertCircle size={18} />
                                    {error}
                                </div>
                            )}

                            {success && (
                                <div className="flex items-center gap-2 p-4 bg-green-500/10 text-green-400 rounded-xl border border-green-500/20 text-sm animate-fadeIn">
                                    <CheckCircle size={18} />
                                    {success}
                                </div>
                            )}

                            <div className="flex justify-end pt-4">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex items-center gap-2 px-8 py-3 bg-white text-[#0a0e1a] rounded-xl font-semibold hover:bg-white/90 active:transform active:scale-95 transition-all disabled:opacity-50"
                                >
                                    {saving ? <Loader2 className="animate-spin" size={20} /> : <Save size={20} />}
                                    {t('common.save_changes')}
                                </button>
                            </div>
                        </form>
                    </div>
                    </GlassCard>
                </div>
            </div>

            <style>{`
        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
        </div>
    );
};

export default ProfileView;
