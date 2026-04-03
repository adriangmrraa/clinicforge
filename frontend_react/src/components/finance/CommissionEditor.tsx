import { useState, useEffect } from 'react';
import { X, Plus, Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import type { ProfessionalCommission, CommissionOverride } from '../../types/finance';

interface CommissionEditorProps {
  professionalId: number;
  professionalName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CommissionEditor({ professionalId, professionalName, onClose, onSuccess }: CommissionEditorProps) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<ProfessionalCommission | null>(null);
  const [defaultPct, setDefaultPct] = useState<number>(30);
  const [overrides, setOverrides] = useState<CommissionOverride[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableTreatments, setAvailableTreatments] = useState<{ code: string; name: string }[]>([]);
  const [selectedTreatment, setSelectedTreatment] = useState('');

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [configRes, treatmentsRes] = await Promise.all([
          api.get(`/admin/professionals/${professionalId}/commissions`),
          api.get('/admin/treatment-types'),
        ]);
        setConfig(configRes.data);
        setDefaultPct(configRes.data.default_commission_pct ?? 30);
        setOverrides(configRes.data.per_treatment ?? []);
        setAvailableTreatments(treatmentsRes.data ?? []);
      } catch (err: any) {
        console.error('Error loading commission config:', err);
        setError(err.response?.data?.detail || 'Error al cargar configuración');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [professionalId]);

  const handleAddOverride = () => {
    if (!selectedTreatment) return;
    const treatment = availableTreatments.find((t) => t.code === selectedTreatment);
    if (!treatment) return;
    if (overrides.find((o) => o.treatment_code === selectedTreatment)) return;

    setOverrides([...overrides, { treatment_code: selectedTreatment, treatment_name: treatment.name, commission_pct: defaultPct }]);
    setSelectedTreatment('');
  };

  const handleRemoveOverride = (code: string) => {
    setOverrides(overrides.filter((o) => o.treatment_code !== code));
  };

  const handleOverridePctChange = (code: string, pct: number) => {
    setOverrides(overrides.map((o) => (o.treatment_code === code ? { ...o, commission_pct: pct } : o)));
  };

  const handleSave = async () => {
    // Validation
    if (defaultPct < 0 || defaultPct > 100) {
      setError(t('commissions.invalid_percentage'));
      return;
    }
    for (const o of overrides) {
      if (o.commission_pct < 0 || o.commission_pct > 100) {
        setError(t('commissions.invalid_percentage'));
        return;
      }
    }

    setSaving(true);
    setError(null);
    try {
      await api.put(`/admin/professionals/${professionalId}/commissions`, {
        default_commission_pct: defaultPct,
        per_treatment: overrides.map((o) => ({
          treatment_code: o.treatment_code,
          commission_pct: o.commission_pct,
        })),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Error saving commissions:', err);
      setError(err.response?.data?.detail || 'Error al guardar comisiones');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#12121a] border border-white/[0.08] rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-white">
            {t('commissions.title')} — {professionalName}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/[0.06] rounded-lg text-white/40 hover:text-white/70 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={24} className="animate-spin text-blue-400" />
          </div>
        ) : (
          <>
            {error && (
              <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-4">
                <AlertTriangle size={16} className="text-red-400 shrink-0" />
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            {/* Default Commission */}
            <div className="mb-6">
              <label className="text-xs text-white/50 font-medium mb-2 block">
                {t('commissions.default_commission')}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={defaultPct}
                  onChange={(e) => setDefaultPct(Number(e.target.value))}
                  className="w-24 bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500/40"
                />
                <span className="text-white/40">%</span>
              </div>
              {defaultPct === 0 && (
                <p className="text-xs text-amber-400/60 mt-1 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  {t('commissions.warning_zero')}
                </p>
              )}
            </div>

            {/* Per-Treatment Overrides */}
            <div className="mb-6">
              <label className="text-xs text-white/50 font-medium mb-2 block">
                {t('commissions.per_treatment')}
              </label>

              {/* Add row */}
              <div className="flex items-center gap-2 mb-3">
                <select
                  value={selectedTreatment}
                  onChange={(e) => setSelectedTreatment(e.target.value)}
                  className="flex-1 bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500/40"
                >
                  <option value="">{t('treatments.select')}</option>
                  {availableTreatments
                    .filter((tr) => !overrides.find((o) => o.treatment_code === tr.code))
                    .map((tr) => (
                      <option key={tr.code} value={tr.code}>
                        {tr.name} ({tr.code})
                      </option>
                    ))}
                </select>
                <button
                  onClick={handleAddOverride}
                  disabled={!selectedTreatment}
                  className="p-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors disabled:opacity-30"
                >
                  <Plus size={16} />
                </button>
              </div>

              {/* Overrides list */}
              {overrides.length > 0 ? (
                <div className="space-y-2">
                  {overrides.map((o) => (
                    <div
                      key={o.treatment_code}
                      className="flex items-center gap-3 bg-white/[0.02] border border-white/[0.04] rounded-xl px-3 py-2"
                    >
                      <span className="flex-1 text-sm text-white/70 truncate">
                        {o.treatment_name || o.treatment_code}
                      </span>
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={o.commission_pct}
                          onChange={(e) => handleOverridePctChange(o.treatment_code, Number(e.target.value))}
                          className="w-16 bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:border-blue-500/40"
                        />
                        <span className="text-white/40 text-xs">%</span>
                      </div>
                      <button
                        onClick={() => handleRemoveOverride(o.treatment_code)}
                        className="p-1.5 hover:bg-red-500/10 rounded-lg text-white/30 hover:text-red-400 transition-colors"
                        title={t('commissions.remove_treatment')}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-white/30 text-center py-4">{t('commissions.no_overrides', 'Sin overrides configurados')}</p>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3 justify-end pt-4 border-t border-white/[0.06]">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-white/[0.04] text-white/60 rounded-xl hover:bg-white/[0.06] transition-colors text-sm"
              >
                {t('commissions.cancel')}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 bg-primary text-white rounded-xl hover:bg-primary/80 transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {t('commissions.save')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
