import { useState, useEffect } from 'react';
import { X, Plus, Trash2, AlertTriangle, Loader2, Clock } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import type { ProfessionalCommission, CommissionOverride, CommissionHistoryEntry } from '../../types/finance';

interface CommissionEditorProps {
  professionalId: number;
  professionalName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CommissionEditor({ professionalId, professionalName, onClose, onSuccess }: CommissionEditorProps) {
  const { t } = useTranslation();
  const [config, setConfig] = useState<ProfessionalCommission | null>(null);
  const [defaultPct, setDefaultPct] = useState<number>(60);
  const [defaultClinicPct, setDefaultClinicPct] = useState<number>(40);
  const [overrides, setOverrides] = useState<CommissionOverride[]>([]);
  const [history, setHistory] = useState<CommissionHistoryEntry[]>([]);
  const [effectiveDate, setEffectiveDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [activeTab, setActiveTab] = useState<'config' | 'history'>('config');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableTreatments, setAvailableTreatments] = useState<{ code: string; name: string }[]>([]);
  const [selectedTreatment, setSelectedTreatment] = useState('');

  // Calculate sums
  const defaultSum = defaultPct + defaultClinicPct;
  const defaultSumOk = Math.abs(defaultSum - 100) < 0.01;

  const overrideSumsValid = overrides.every((o) => Math.abs((o.commission_pct || 0) + (o.clinic_pct || 0) - 100) < 0.01);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [configRes, treatmentsRes] = await Promise.all([
          api.get(`/admin/professionals/${professionalId}/commissions`),
          api.get('/admin/treatment-types'),
        ]);
        setConfig(configRes.data);
        setDefaultPct(configRes.data.default_commission_pct ?? 60);
        setDefaultClinicPct(configRes.data.default_clinic_pct ?? 40);
        setOverrides(
          (configRes.data.per_treatment ?? []).map((o: any) => ({
            treatment_code: o.treatment_code,
            treatment_name: o.treatment_name,
            commission_pct: o.commission_pct ?? 50,
            clinic_pct: o.clinic_pct ?? 50,
          }))
        );
        setHistory(configRes.data.history ?? []);
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

    setOverrides([
      ...overrides,
      {
        treatment_code: selectedTreatment,
        treatment_name: treatment.name,
        commission_pct: defaultPct,
        clinic_pct: defaultClinicPct,
      },
    ]);
    setSelectedTreatment('');
  };

  const handleRemoveOverride = (code: string) => {
    setOverrides(overrides.filter((o) => o.treatment_code !== code));
  };

  const handleOverrideChange = (code: string, field: 'commission_pct' | 'clinic_pct', value: number) => {
    setOverrides(
      overrides.map((o) =>
        o.treatment_code === code ? { ...o, [field]: value } : o
      )
    );
  };

  const handleSave = async () => {
    // Validate default sum = 100
    if (!defaultSumOk) {
      setError(t('commissions.must_sum_100') || 'Los porcentajes deben sumar 100%');
      return;
    }

    // Validate each override sum = 100
    for (const o of overrides) {
      if (Math.abs((o.commission_pct || 0) + (o.clinic_pct || 0) - 100) > 0.01) {
        setError(t('commissions.must_sum_100') || 'Los porcentajes deben sumar 100%');
        return;
      }
    }

    // Validate range
    for (const val of [defaultPct, defaultClinicPct, ...overrides.flatMap((o) => [o.commission_pct, o.clinic_pct])]) {
      if (val < 0 || val > 100) {
        setError(t('commissions.invalid_percentage'));
        return;
      }
    }

    setSaving(true);
    setError(null);
    try {
      await api.put(`/admin/professionals/${professionalId}/commissions`, {
        default_commission_pct: defaultPct,
        default_clinic_pct: defaultClinicPct,
        effective_date: effectiveDate || undefined,
        per_treatment: overrides.map((o) => ({
          treatment_code: o.treatment_code,
          commission_pct: o.commission_pct,
          clinic_pct: o.clinic_pct,
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
      <div className="bg-[#12121a] border border-white/[0.08] rounded-2xl p-6 max-w-2xl w-full mx-4 shadow-2xl max-h-[85vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
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

        {/* Tabs */}
        <div className="flex gap-1 mb-5 border-b border-white/[0.06]">
          <button
            onClick={() => setActiveTab('config')}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px] ${
              activeTab === 'config'
                ? 'text-blue-400 border-blue-400'
                : 'text-white/40 border-transparent hover:text-white/60'
            }`}
          >
            {t('commissions.title') || 'Configuración'}
          </button>
          <button
            onClick={() => { setError(null); setActiveTab('history'); }}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px] flex items-center gap-1.5 ${
              activeTab === 'history'
                ? 'text-blue-400 border-blue-400'
                : 'text-white/40 border-transparent hover:text-white/60'
            }`}
          >
            <Clock size={14} />
            {t('commissions.history_title') || 'Historial'}
            {history.length > 0 && (
              <span className="text-xs bg-white/[0.06] px-1.5 py-0.5 rounded-full">
                {history.length}
              </span>
            )}
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={24} className="animate-spin text-blue-400" />
          </div>
        ) : activeTab === 'history' ? (
          /* ===== HISTORY TAB ===== */
          <div>
            {history.length === 0 ? (
              <div className="text-center py-8">
                <Clock size={32} className="mx-auto text-white/20 mb-3" />
                <p className="text-sm text-white/30">{t('commissions.no_history') || 'Sin cambios registrados'}</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[50vh] overflow-y-auto">
                {history.map((entry) => (
                  <div
                    key={entry.id}
                    className="bg-white/[0.02] border border-white/[0.04] rounded-xl p-4"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <span className="text-sm font-medium text-white/70">
                          {entry.treatment_code
                            ? entry.treatment_name || entry.treatment_code
                            : 'Default'}
                        </span>
                        <span className="text-xs text-white/30 ml-2">
                          {entry.changed_by || '—'}
                        </span>
                      </div>
                      <span className="text-xs text-white/40 whitespace-nowrap">
                        {entry.effective_date}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-white/40">Prof:</span>
                      {entry.old_commission_pct !== null ? (
                        <>
                          <span className="text-white/40 line-through">{entry.old_commission_pct}%</span>
                          <span className="text-amber-400">→</span>
                        </>
                      ) : null}
                      <span className="text-green-400 font-medium">{entry.new_commission_pct}%</span>
                      <span className="text-white/20">|</span>
                      <span className="text-white/40">Clínica:</span>
                      {entry.old_clinic_pct !== null ? (
                        <>
                          <span className="text-white/40 line-through">{entry.old_clinic_pct}%</span>
                          <span className="text-amber-400">→</span>
                        </>
                      ) : null}
                      <span className="text-blue-400 font-medium">{entry.new_clinic_pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* ===== CONFIG TAB ===== */
          <>
            {error && (
              <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-4">
                <AlertTriangle size={16} className="text-red-400 shrink-0" />
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            {/* Effective Date */}
            <div className="mb-4">
              <label className="text-xs text-white/50 font-medium mb-2 block">
                {t('commissions.effective_date') || 'Fecha efectiva'}
              </label>
              <input
                type="date"
                value={effectiveDate}
                min={new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="w-44 bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500/40"
              />
              <p className="text-[10px] text-white/30 mt-1">
                {t('commissions.future_change', { date: effectiveDate }) || `Este cambio aplica a partir del ${effectiveDate}`}
              </p>
            </div>

            {/* Default Commission — Split */}
            <div className="mb-6">
              <label className="text-xs text-white/50 font-medium mb-2 block">
                {t('commissions.default_commission')}
              </label>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/40">{t('commissions.prof_share') || 'Profesional'}:</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={defaultPct}
                    onChange={(e) => setDefaultPct(Number(e.target.value))}
                    className="w-20 bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-3 py-2 text-sm text-center focus:outline-none focus:border-blue-500/40"
                  />
                  <span className="text-white/40 text-xs">%</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/40">{t('commissions.clinic_share') || 'Clínica'}:</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={defaultClinicPct}
                    onChange={(e) => setDefaultClinicPct(Number(e.target.value))}
                    className="w-20 bg-white/[0.04] border border-white/[0.08] text-white rounded-xl px-3 py-2 text-sm text-center focus:outline-none focus:border-blue-500/40"
                  />
                  <span className="text-white/40 text-xs">%</span>
                </div>
                <div className="flex items-center gap-1.5 ml-2">
                  <span className="text-xs text-white/30">Suma:</span>
                  <span
                    className={`text-sm font-bold ${
                      defaultSumOk ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {defaultSum}%
                  </span>
                  {defaultSumOk ? (
                    <span className="text-green-400/60 text-xs">✅</span>
                  ) : (
                    <span className="text-red-400/60 text-xs">❌</span>
                  )}
                </div>
              </div>
              {!defaultSumOk && (
                <p className="text-xs text-red-400/80 mt-1 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  {t('commissions.must_sum_100') || 'Los porcentajes deben sumar 100%'}
                </p>
              )}
              {defaultPct === 0 && defaultSumOk && (
                <p className="text-xs text-amber-400/60 mt-1 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  {t('commissions.warning_zero')}
                </p>
              )}
            </div>

            {/* Per-Treatment Overrides — Split */}
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
                  {overrides.map((o) => {
                    const sum = (o.commission_pct || 0) + (o.clinic_pct || 0);
                    const sumOk = Math.abs(sum - 100) < 0.01;
                    return (
                      <div
                        key={o.treatment_code}
                        className="flex items-center gap-2 bg-white/[0.02] border border-white/[0.04] rounded-xl px-3 py-2"
                      >
                        <span className="w-28 text-sm text-white/70 truncate">
                          {o.treatment_name || o.treatment_code}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-white/30">Prof:</span>
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={o.commission_pct}
                            onChange={(e) =>
                              handleOverrideChange(o.treatment_code, 'commission_pct', Number(e.target.value))
                            }
                            className="w-14 bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-1.5 py-1 text-xs text-center focus:outline-none focus:border-blue-500/40"
                          />
                          <span className="text-white/30 text-[10px]">%</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-white/30">Cli:</span>
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={o.clinic_pct}
                            onChange={(e) =>
                              handleOverrideChange(o.treatment_code, 'clinic_pct', Number(e.target.value))
                            }
                            className="w-14 bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-1.5 py-1 text-xs text-center focus:outline-none focus:border-blue-500/40"
                          />
                          <span className="text-white/30 text-[10px]">%</span>
                        </div>
                        <span
                          className={`text-[10px] font-bold ${
                            sumOk ? 'text-green-400/60' : 'text-red-400/60'
                          }`}
                        >
                          {sum}%
                        </span>
                        <button
                          onClick={() => handleRemoveOverride(o.treatment_code)}
                          className="p-1 hover:bg-red-500/10 rounded-lg text-white/30 hover:text-red-400 transition-colors"
                          title={t('commissions.remove_treatment')}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-white/30 text-center py-4">
                  {t('commissions.no_overrides', 'Sin overrides configurados')}
                </p>
              )}

              {!overrideSumsValid && overrides.length > 0 && (
                <p className="text-xs text-red-400/80 mt-2 flex items-center gap-1">
                  <AlertTriangle size={12} />
                  {t('commissions.must_sum_100') || 'Todos los overrides deben sumar 100%'}
                </p>
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
                disabled={saving || !defaultSumOk || !overrideSumsValid}
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
