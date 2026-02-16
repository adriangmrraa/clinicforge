import { useState, useEffect } from 'react';
import { Building2, Plus, Edit, Trash2, Phone, Loader2, AlertCircle, CheckCircle2, Calendar } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

/** Clínica = Tenant en backend. Incluye config.calendar_provider: 'local' | 'google'. */
export interface Clinica {
    id: number;
    clinic_name: string;
    bot_phone_number: string;
    config?: { calendar_provider?: 'local' | 'google' };
    created_at: string;
    updated_at?: string;
}

const CALENDAR_PROVIDER_OPTIONS = (t: (k: string) => string) => [
    { value: 'local' as const, label: t('clinics.calendar_local') },
    { value: 'google' as const, label: t('clinics.calendar_google') },
];

export default function ClinicsView() {
    const { t } = useTranslation();
    const [clinicas, setClinicas] = useState<Clinica[]>([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingClinica, setEditingClinica] = useState<Clinica | null>(null);
    const [formData, setFormData] = useState({
        clinic_name: '',
        bot_phone_number: '',
        calendar_provider: 'local' as 'local' | 'google',
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        fetchClinicas();
    }, []);

    const fetchClinicas = async () => {
        try {
            setLoading(true);
            const resp = await api.get('/admin/tenants');
            setClinicas(resp.data);
        } catch (err) {
            console.error('Error cargando clínicas:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleOpenModal = (clinica: Clinica | null = null) => {
        if (clinica) {
            setEditingClinica(clinica);
            setFormData({
                clinic_name: clinica.clinic_name,
                bot_phone_number: clinica.bot_phone_number,
                calendar_provider: (clinica.config?.calendar_provider === 'google' ? 'google' : 'local') as 'local' | 'google',
            });
        } else {
            setEditingClinica(null);
            setFormData({ clinic_name: '', bot_phone_number: '', calendar_provider: 'local' });
        }
        setError(null);
        setIsModalOpen(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
            if (editingClinica) {
                await api.put(`/admin/tenants/${editingClinica.id}`, {
                    clinic_name: formData.clinic_name,
                    bot_phone_number: formData.bot_phone_number,
                    calendar_provider: formData.calendar_provider,
                });
                setSuccess(t('clinics.toast_updated'));
            } else {
                await api.post('/admin/tenants', {
                    clinic_name: formData.clinic_name,
                    bot_phone_number: formData.bot_phone_number,
                    calendar_provider: formData.calendar_provider,
                });
                setSuccess(t('clinics.toast_created'));
            }
            await fetchClinicas();
            setIsModalOpen(false);
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.response?.data?.detail || t('clinics.toast_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm(t('alerts.confirm_delete_clinic'))) return;
        try {
            await api.delete(`/admin/tenants/${id}`);
            fetchClinicas();
        } catch (err) {
            console.error('Error eliminando clínica:', err);
        }
    };

    const calendarProviderLabel = (cp: string) =>
        CALENDAR_PROVIDER_OPTIONS(t).find(o => o.value === cp)?.label ?? cp;

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 min-h-0 overflow-y-auto">
                <Loader2 className="animate-spin text-medical-600" size={32} />
                <p className="text-medical-800 font-medium">{t('common.loading')}</p>
            </div>
        );
    }

    return (
        <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6 min-h-0 overflow-y-auto">
            <PageHeader
                title={t('clinics.title')}
                subtitle={t('clinics.subtitle')}
                icon={<Building2 size={22} />}
                action={
                    <button
                        onClick={() => handleOpenModal()}
                        className="flex items-center justify-center gap-2 bg-medical-600 text-white px-4 py-2.5 rounded-xl hover:bg-medical-700 transition-all shadow-md font-medium text-sm sm:text-base active:scale-[0.98]"
                    >
                        <Plus size={20} /> {t('clinics.new_clinic')}
                    </button>
                }
            />

            {success && (
                <div className="bg-green-50 text-green-700 p-3 rounded-lg flex items-center gap-2 border border-green-200 animate-fade-in">
                    <CheckCircle2 size={18} /> {success}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {clinicas.map((clinica) => (
                    <div
                        key={clinica.id}
                        className="bg-white rounded-xl shadow-sm border border-medical-100 overflow-hidden hover:shadow-md transition-shadow group"
                    >
                        <div className="p-5 space-y-4">
                            <div className="flex justify-between items-start">
                                <div className="bg-medical-50 p-3 rounded-lg text-medical-600 group-hover:bg-medical-600 group-hover:text-white transition-colors">
                                    <Building2 size={24} />
                                </div>
                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={() => handleOpenModal(clinica)}
                                        className="p-2 text-medical-600 hover:bg-medical-50 rounded-lg transition-colors"
                                    >
                                        <Edit size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleDelete(clinica.id)}
                                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </div>

                            <div>
                                <h3 className="font-bold text-medical-900 text-lg">{clinica.clinic_name}</h3>
                                <div className="flex items-center gap-2 text-medical-600 mt-2 text-sm">
                                    <Phone size={14} className="shrink-0" />
                                    <span className="font-mono">{clinica.bot_phone_number}</span>
                                </div>
                                <div className="flex items-center gap-2 text-medical-500 mt-1 text-xs">
                                    <Calendar size={12} className="shrink-0" />
                                    <span>{calendarProviderLabel(clinica.config?.calendar_provider || 'local')}</span>
                                </div>
                            </div>

                            <div className="pt-4 border-t border-medical-50 flex justify-between items-center text-xs text-medical-400">
                                <span>ID: {clinica.id}</span>
                                <span>{t('common.since')}: {new Date(clinica.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {isModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-md animate-scale-in">
                        <div className="p-6 border-b">
                            <h2 className="text-xl font-bold flex items-center gap-2">
                                {editingClinica ? <Edit className="text-medical-600" /> : <Plus className="text-medical-600" />}
                                {editingClinica ? t('clinics.edit_clinic') : t('clinics.create_clinic')}
                            </h2>
                        </div>

                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            {error && (
                                <div className="bg-red-50 text-red-600 p-3 rounded-lg flex items-center gap-2 text-sm border border-red-100">
                                    <AlertCircle size={16} /> {error}
                                </div>
                            )}

                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-medical-700">{t('clinics.clinic_name_label')}</label>
                                <input
                                    required
                                    type="text"
                                    placeholder={t('clinics.clinic_name_placeholder')}
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-medical-500 outline-none transition-all"
                                    value={formData.clinic_name}
                                    onChange={(e) => setFormData({ ...formData, clinic_name: e.target.value })}
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-medical-700">{t('clinics.bot_phone_label')}</label>
                                <input
                                    required
                                    type="text"
                                    placeholder={t('clinics.bot_phone_placeholder')}
                                    className="w-full px-4 py-2 border rounded-lg font-mono focus:ring-2 focus:ring-medical-500 outline-none transition-all"
                                    value={formData.bot_phone_number}
                                    onChange={(e) => setFormData({ ...formData, bot_phone_number: e.target.value })}
                                />
                                <p className="text-[10px] text-medical-400 italic">
                                    {t('clinics.bot_phone_help')}
                                </p>
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-medical-700 flex items-center gap-2">
                                    <Calendar size={14} /> {t('clinics.calendar_provider_label')}
                                </label>
                                <select
                                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-medical-500 outline-none"
                                    value={formData.calendar_provider}
                                    onChange={(e) => setFormData({ ...formData, calendar_provider: e.target.value as 'local' | 'google' })}
                                >
                                    {CALENDAR_PROVIDER_OPTIONS(t).map((opt) => (
                                        <option key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                                <p className="text-[10px] text-medical-400 italic">
                                    {t('clinics.calendar_help')}
                                </p>
                            </div>

                            <div className="flex gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setIsModalOpen(false)}
                                    className="flex-1 py-2 text-medical-700 font-medium hover:bg-medical-50 rounded-lg transition-all"
                                >
                                    {t('common.cancel')}
                                </button>
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 py-2 bg-medical-600 text-white font-bold rounded-lg hover:bg-medical-700 transition-all shadow-md disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {saving ? <Loader2 className="animate-spin" size={20} /> : t('common.save')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
