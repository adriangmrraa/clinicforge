import React, { useState, useEffect, useCallback } from 'react';
import { Ban, Plus, Edit2, Trash2, Save, X, Mail, BellOff, MessageCircle } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface BlockedContact {
  id: number;
  phone_digits: string;
  phone_display?: string | null;
  label: string;
  behavior: 'SILENCIO' | 'MENSAJE';
  message_template?: string | null;
  notify_email: boolean;
  cooldown_hours: number;
  last_autoreply_at?: string | null;
  note?: string | null;
  is_active: boolean;
  created_at?: string;
}

const LABELS: { value: string; es: string }[] = [
  { value: 'laboratorio', es: 'Laboratorio' },
  { value: 'proveedor', es: 'Proveedor' },
  { value: 'profesional_clinica', es: 'Profesional de la clínica' },
  { value: 'inconveniente_ia', es: 'Inconveniente con la IA' },
  { value: 'otros', es: 'Otros' },
  { value: 'spam', es: 'Spam' },
];

interface FormState {
  id: number | null;
  phone: string;
  label: string;
  behavior: 'SILENCIO' | 'MENSAJE';
  message_template: string;
  notify_email: boolean;
  cooldown_hours: number;
  note: string;
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  id: null,
  phone: '',
  label: 'laboratorio',
  behavior: 'MENSAJE',
  message_template: '',
  notify_email: false,
  cooldown_hours: 24,
  note: '',
  is_active: true,
};

const inputCls =
  'w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-white/30 placeholder:text-white/30';

export default function BlockedContactsView() {
  const { t } = useTranslation();
  const [items, setItems] = useState<BlockedContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/admin/blocked-contacts');
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setError(t('blocked.errorLoad'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setForm(EMPTY_FORM);
    setError('');
    setShowForm(true);
  };

  const openEdit = (it: BlockedContact) => {
    setForm({
      id: it.id,
      phone: it.phone_display || it.phone_digits,
      label: it.label,
      behavior: it.behavior,
      message_template: it.message_template || '',
      notify_email: it.notify_email,
      cooldown_hours: it.cooldown_hours,
      note: it.note || '',
      is_active: it.is_active,
    });
    setError('');
    setShowForm(true);
  };

  const save = async () => {
    setError('');
    if (!form.phone.trim()) {
      setError(t('blocked.errorPhone'));
      return;
    }
    if (form.behavior === 'MENSAJE' && !form.message_template.trim()) {
      setError(t('blocked.errorMessage'));
      return;
    }
    setSaving(true);
    const payload = {
      phone: form.phone.trim(),
      label: form.label,
      behavior: form.behavior,
      message_template: form.behavior === 'MENSAJE' ? form.message_template.trim() : null,
      notify_email: form.notify_email,
      cooldown_hours: Number(form.cooldown_hours) || 24,
      note: form.note.trim() || null,
      is_active: form.is_active,
    };
    try {
      if (form.id) {
        await api.put(`/admin/blocked-contacts/${form.id}`, payload);
      } else {
        await api.post('/admin/blocked-contacts', payload);
      }
      setShowForm(false);
      await load();
    } catch (e: any) {
      setError(e?.response?.data?.detail || t('blocked.errorSave'));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it: BlockedContact) => {
    if (!window.confirm(t('blocked.confirmDelete'))) return;
    try {
      await api.delete(`/admin/blocked-contacts/${it.id}`);
      await load();
    } catch {
      setError(t('blocked.errorDelete'));
    }
  };

  const labelEs = (v: string) => LABELS.find((l) => l.value === v)?.es || v;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400">
            <Ban size={22} />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">{t('blocked.title')}</h1>
            <p className="text-sm text-white/50">{t('blocked.subtitle')}</p>
          </div>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-2 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg text-sm font-medium hover:bg-white/90 transition"
        >
          <Plus size={16} /> {t('blocked.add')}
        </button>
      </div>

      {error && !showForm && (
        <div className="mb-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* List */}
      {loading ? (
        <p className="text-white/40 text-sm">{t('blocked.loading')}</p>
      ) : items.length === 0 ? (
        <div className="text-center py-16 border border-white/[0.06] rounded-xl bg-white/[0.02]">
          <Ban size={32} className="mx-auto text-white/20 mb-3" />
          <p className="text-white/50 text-sm">{t('blocked.empty')}</p>
        </div>
      ) : (
        <div className="border border-white/[0.06] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-white/[0.03] text-white/50 text-left">
                <th className="px-4 py-3 font-medium">{t('blocked.colPhone')}</th>
                <th className="px-4 py-3 font-medium">{t('blocked.colLabel')}</th>
                <th className="px-4 py-3 font-medium">{t('blocked.colBehavior')}</th>
                <th className="px-4 py-3 font-medium">{t('blocked.colEmail')}</th>
                <th className="px-4 py-3 font-medium text-right">{t('blocked.colActions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className="border-t border-white/[0.06] hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-white">
                    {it.phone_display || it.phone_digits}
                    {!it.is_active && (
                      <span className="ml-2 text-xs text-white/30">({t('blocked.inactive')})</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-white/70">{labelEs(it.label)}</td>
                  <td className="px-4 py-3">
                    {it.behavior === 'SILENCIO' ? (
                      <span className="inline-flex items-center gap-1.5 text-xs bg-white/[0.06] text-white/60 px-2 py-1 rounded">
                        <BellOff size={13} /> {t('blocked.silence')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded">
                        <MessageCircle size={13} /> {t('blocked.message')}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {it.notify_email ? <Mail size={15} className="text-blue-400" /> : <span className="text-white/20">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => openEdit(it)} className="p-1.5 rounded text-white/50 hover:text-white hover:bg-white/[0.06]">
                        <Edit2 size={15} />
                      </button>
                      <button onClick={() => remove(it)} className="p-1.5 rounded text-white/50 hover:text-red-400 hover:bg-red-500/10">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setShowForm(false)}>
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">
                {form.id ? t('blocked.editTitle') : t('blocked.addTitle')}
              </h2>
              <button onClick={() => setShowForm(false)} className="text-white/40 hover:text-white">
                <X size={18} />
              </button>
            </div>

            {error && (
              <div className="mb-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-white/50 mb-1">{t('blocked.colPhone')}</label>
                <input
                  className={inputCls}
                  placeholder="+54 9 299 ..."
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-white/50 mb-1">{t('blocked.colLabel')}</label>
                  <select
                    className={inputCls}
                    value={form.label}
                    onChange={(e) => setForm({ ...form, label: e.target.value })}
                  >
                    {LABELS.map((l) => (
                      <option key={l.value} value={l.value} className="bg-[#0d1117]">
                        {l.es}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-white/50 mb-1">{t('blocked.colBehavior')}</label>
                  <select
                    className={inputCls}
                    value={form.behavior}
                    onChange={(e) => setForm({ ...form, behavior: e.target.value as 'SILENCIO' | 'MENSAJE' })}
                  >
                    <option value="MENSAJE" className="bg-[#0d1117]">{t('blocked.message')}</option>
                    <option value="SILENCIO" className="bg-[#0d1117]">{t('blocked.silence')}</option>
                  </select>
                </div>
              </div>

              {form.behavior === 'MENSAJE' && (
                <div>
                  <label className="block text-xs text-white/50 mb-1">{t('blocked.messageText')}</label>
                  <textarea
                    className={inputCls + ' h-24 resize-none'}
                    placeholder={t('blocked.messagePlaceholder')}
                    value={form.message_template}
                    onChange={(e) => setForm({ ...form, message_template: e.target.value })}
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-white/50 mb-1">{t('blocked.cooldown')}</label>
                  <input
                    type="number"
                    min={1}
                    className={inputCls}
                    value={form.cooldown_hours}
                    onChange={(e) => setForm({ ...form, cooldown_hours: Number(e.target.value) })}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-white/70 mt-6 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.notify_email}
                    onChange={(e) => setForm({ ...form, notify_email: e.target.checked })}
                  />
                  {t('blocked.notifyEmail')}
                </label>
              </div>

              <div>
                <label className="block text-xs text-white/50 mb-1">{t('blocked.note')}</label>
                <input
                  className={inputCls}
                  placeholder={t('blocked.notePlaceholder')}
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                {t('blocked.active')}
              </label>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-lg text-sm text-white/60 hover:text-white hover:bg-white/[0.06]"
              >
                {t('blocked.cancel')}
              </button>
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-2 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg text-sm font-medium hover:bg-white/90 disabled:opacity-50"
              >
                <Save size={15} /> {saving ? t('blocked.saving') : t('blocked.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
