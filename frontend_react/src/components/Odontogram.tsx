import { useState, useEffect } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Save, RotateCcw, AlertCircle } from 'lucide-react';
import api from '../api/axios';

type ToothStatus = 'healthy' | 'caries' | 'restoration' | 'extraction' | 'treatment_planned' | 'crown' | 'implant' | 'missing' | 'prosthesis' | 'root_canal';

interface ToothState {
  id: number;
  state: ToothStatus;
  surfaces?: {
    buccal?: string;
    lingual?: string;
    occlusal?: string;
    mesial?: string;
    distal?: string;
  };
  notes?: string;
}

interface OdontogramProps {
  patientId: number;
  recordId?: number;
  initialData?: any;
  onSave?: (data: any) => void;
  readOnly?: boolean;
}

// FDI standard quadrants
const UPPER_RIGHT: number[] = [18, 17, 16, 15, 14, 13, 12, 11];
const UPPER_LEFT: number[] = [21, 22, 23, 24, 25, 26, 27, 28];
const LOWER_RIGHT: number[] = [48, 47, 46, 45, 44, 43, 42, 41];
const LOWER_LEFT: number[] = [31, 32, 33, 34, 35, 36, 37, 38];

const ALL_TEETH = [...UPPER_RIGHT, ...UPPER_LEFT, ...LOWER_RIGHT, ...LOWER_LEFT];

// SVG fill colors per state
const STATE_FILLS: Record<ToothStatus, { fill: string; stroke: string }> = {
  healthy:           { fill: '#ffffff', stroke: '#94a3b8' },
  caries:            { fill: '#fecaca', stroke: '#dc2626' },
  restoration:       { fill: '#bfdbfe', stroke: '#2563eb' },
  root_canal:        { fill: '#fed7aa', stroke: '#ea580c' },
  crown:             { fill: '#ddd6fe', stroke: '#7c3aed' },
  implant:           { fill: '#c7d2fe', stroke: '#4f46e5' },
  prosthesis:        { fill: '#99f6e4', stroke: '#0d9488' },
  extraction:        { fill: '#e2e8f0', stroke: '#64748b' },
  missing:           { fill: '#f1f5f9', stroke: '#cbd5e1' },
  treatment_planned: { fill: '#fef08a', stroke: '#ca8a04' },
};

// Tailwind classes for state selector buttons
const STATE_BTN: Record<ToothStatus, string> = {
  healthy:           'bg-white border-slate-300 text-slate-600',
  caries:            'bg-red-100 border-red-400 text-red-700',
  restoration:       'bg-blue-100 border-blue-400 text-blue-700',
  root_canal:        'bg-orange-100 border-orange-400 text-orange-700',
  crown:             'bg-violet-100 border-violet-400 text-violet-700',
  implant:           'bg-indigo-100 border-indigo-400 text-indigo-700',
  prosthesis:        'bg-teal-100 border-teal-400 text-teal-700',
  extraction:        'bg-slate-200 border-slate-400 text-slate-600',
  missing:           'bg-slate-100 border-slate-300 text-slate-400',
  treatment_planned: 'bg-yellow-100 border-yellow-500 text-yellow-700',
};

const STATE_SYMBOLS: Record<ToothStatus, string> = {
  healthy: '○', caries: 'C', restoration: 'R', root_canal: 'Tc',
  crown: 'Co', implant: 'Im', prosthesis: 'Pr', extraction: '✕',
  missing: '—', treatment_planned: 'P',
};

// Format tooth ID to FDI display: 18 → "1.8", 21 → "2.1"
function fdiLabel(id: number): string {
  return `${Math.floor(id / 10)}.${id % 10}`;
}

// SVG paths for the 5 surfaces of the classic odontogram tooth diagram
// ViewBox: 0 0 40 40 — outer circle r=18, inner circle r=7, center (20,20)
const SURFACE_PATHS = {
  // Top surface (vestibular for upper, lingual for lower)
  top: 'M20,2 A18,18 0 0,1 38,20 L27,20 A7,7 0 0,0 20,13 Z',
  // Right surface
  right: 'M38,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z',
  // Bottom surface (lingual/palatal for upper, vestibular for lower)
  bottom: 'M20,38 A18,18 0 0,1 2,20 L13,20 A7,7 0 0,0 20,27 Z',
  // Left surface
  left: 'M2,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z',
};

// Render one tooth as SVG with 5 clickable surfaces
function ToothSVG({
  toothId,
  state,
  isSelected,
  readOnly,
  onClick,
}: {
  toothId: number;
  state: ToothStatus;
  isSelected: boolean;
  readOnly: boolean;
  onClick: () => void;
}) {
  const fills = STATE_FILLS[state] || STATE_FILLS.healthy;
  const isAbsent = state === 'missing' || state === 'extraction';

  return (
    <svg
      viewBox="0 0 40 40"
      className={`w-[38px] h-[38px] sm:w-[42px] sm:h-[42px] shrink-0 transition-transform duration-100 ${
        readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-110 active:scale-95'
      } ${isSelected ? 'scale-110 drop-shadow-md' : ''}`}
      onClick={readOnly ? undefined : onClick}
    >
      {/* Selection ring */}
      {isSelected && (
        <circle cx="20" cy="20" r="19.5" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeDasharray="3,2" />
      )}

      {/* 4 outer surfaces */}
      {(['top', 'right', 'bottom', 'left'] as const).map(surface => (
        <path
          key={surface}
          d={SURFACE_PATHS[surface]}
          fill={fills.fill}
          stroke={fills.stroke}
          strokeWidth="1"
          opacity={isAbsent ? 0.4 : 1}
        />
      ))}

      {/* Center circle (occlusal) */}
      <circle
        cx="20" cy="20" r="7"
        fill={fills.fill}
        stroke={fills.stroke}
        strokeWidth="1"
        opacity={isAbsent ? 0.4 : 1}
      />

      {/* Cross lines (structural) */}
      <line x1="20" y1="2" x2="20" y2="13" stroke={fills.stroke} strokeWidth="0.8" opacity={isAbsent ? 0.3 : 0.6} />
      <line x1="20" y1="27" x2="20" y2="38" stroke={fills.stroke} strokeWidth="0.8" opacity={isAbsent ? 0.3 : 0.6} />
      <line x1="2" y1="20" x2="13" y2="20" stroke={fills.stroke} strokeWidth="0.8" opacity={isAbsent ? 0.3 : 0.6} />
      <line x1="27" y1="20" x2="38" y2="20" stroke={fills.stroke} strokeWidth="0.8" opacity={isAbsent ? 0.3 : 0.6} />

      {/* X overlay for extraction */}
      {state === 'extraction' && (
        <>
          <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
          <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
        </>
      )}

      {/* Dash for missing */}
      {state === 'missing' && (
        <line x1="10" y1="20" x2="30" y2="20" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" />
      )}
    </svg>
  );
}

export default function Odontogram({ patientId, recordId, initialData, onSave, readOnly = false }: OdontogramProps) {
  const { t } = useTranslation();
  const [teeth, setTeeth] = useState<ToothState[]>([]);
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [selectedState, setSelectedState] = useState<ToothStatus>('healthy');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const availableStates: { id: ToothStatus; label: string }[] = [
    { id: 'healthy', label: t('odontogram.states.healthy') },
    { id: 'caries', label: t('odontogram.states.caries') },
    { id: 'restoration', label: t('odontogram.states.restoration') },
    { id: 'root_canal', label: t('odontogram.states.root_canal') },
    { id: 'crown', label: t('odontogram.states.crown') },
    { id: 'implant', label: t('odontogram.states.implant') },
    { id: 'prosthesis', label: t('odontogram.states.prosthesis') },
    { id: 'extraction', label: t('odontogram.states.extraction') },
    { id: 'missing', label: t('odontogram.states.missing') },
    { id: 'treatment_planned', label: t('odontogram.states.treatment_planned') },
  ];

  useEffect(() => {
    if (initialData && initialData.teeth) {
      setTeeth(initialData.teeth);
    } else {
      setTeeth(ALL_TEETH.map(id => ({ id, state: 'healthy' as ToothStatus, surfaces: {}, notes: '' })));
    }
  }, [initialData]);

  const handleToothClick = (toothId: number) => {
    if (readOnly) return;
    if (selectedTooth === toothId) {
      // Already selected → apply current state
      setTeeth(prev => prev.map(tooth =>
        tooth.id === toothId ? { ...tooth, state: selectedState } : tooth
      ));
    } else {
      setSelectedTooth(toothId);
      const tooth = teeth.find(t => t.id === toothId);
      if (tooth) setSelectedState(tooth.state);
    }
  };

  const handleStateChange = (state: ToothStatus) => {
    if (readOnly) return;
    setSelectedState(state);
    if (selectedTooth) {
      setTeeth(prev => prev.map(tooth =>
        tooth.id === selectedTooth ? { ...tooth, state } : tooth
      ));
    }
  };

  const handleSave = async () => {
    if (readOnly) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const odontogramData = { teeth, last_updated: new Date().toISOString(), version: '2.0' };
      if (recordId) {
        await api.put(`/admin/patients/${patientId}/records/${recordId}/odontogram`, { odontogram_data: odontogramData });
      } else {
        await api.post(`/admin/patients/${patientId}/records`, { content: t('odontogram.automatic_note'), odontogram_data: odontogramData });
      }
      setSuccess(t('odontogram.save_success'));
      if (onSave) onSave(odontogramData);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Error saving odontogram:', err);
      setError(err.response?.data?.detail || t('odontogram.save_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (readOnly) return;
    setTeeth(ALL_TEETH.map(id => ({ id, state: 'healthy' as ToothStatus, surfaces: {}, notes: '' })));
    setSelectedTooth(null);
    setSelectedState('healthy');
  };

  // Render a row of teeth with numbers
  const renderTeethRow = (ids: number[], numbersBelow: boolean) => (
    <div className="flex gap-[2px] sm:gap-1">
      {ids.map(id => {
        const tooth = teeth.find(t => t.id === id);
        const state = (tooth?.state || 'healthy') as ToothStatus;
        const isSelected = selectedTooth === id;
        const label = fdiLabel(id);
        return (
          <div key={id} className="flex flex-col items-center">
            {!numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mb-0.5 select-none ${isSelected ? 'text-blue-600' : 'text-slate-500'}`}>{label}</span>
            )}
            <ToothSVG
              toothId={id}
              state={state}
              isSelected={isSelected}
              readOnly={readOnly}
              onClick={() => handleToothClick(id)}
            />
            {numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mt-0.5 select-none ${isSelected ? 'text-blue-600' : 'text-slate-500'}`}>{label}</span>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-soft border border-white/40 p-4 sm:p-6 w-full max-w-full overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-5">
        <div>
          <h3 className="text-lg font-bold text-slate-800">{t('odontogram.title')}</h3>
          <p className="text-xs text-slate-500">{t('odontogram.subtitle')}</p>
        </div>
        {!readOnly && (
          <div className="flex items-center gap-2 w-full sm:w-auto self-end sm:self-auto">
            <button
              onClick={handleReset}
              disabled={saving}
              className="flex-1 sm:flex-none justify-center flex items-center gap-1.5 px-3 py-2 text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200 disabled:opacity-50 text-xs font-semibold transition-colors"
            >
              <RotateCcw size={14} />
              {t('odontogram.reset')}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 sm:flex-none justify-center flex items-center gap-1.5 px-4 py-2 text-white bg-medical-600 rounded-xl hover:bg-medical-700 disabled:opacity-50 text-xs font-semibold shadow-sm transition-colors"
            >
              <Save size={14} />
              {saving ? t('odontogram.saving') : t('odontogram.save')}
            </button>
          </div>
        )}
      </div>

      {/* Status messages */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl flex items-center gap-2 text-sm">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl text-sm">
          {success}
        </div>
      )}

      {/* State selector */}
      {!readOnly && (
        <div className="mb-5 p-3 bg-slate-50/80 rounded-2xl border border-slate-100">
          <div className="flex items-center gap-2 mb-2">
            {selectedTooth && (
              <>
                <span className="text-xs font-bold text-slate-500">{t('odontogram.selecting_tooth')}</span>
                <span className="text-sm font-black text-blue-600">{fdiLabel(selectedTooth)}</span>
                <span className="text-[10px] text-slate-400">—</span>
              </>
            )}
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              {selectedTooth ? t('odontogram.states.' + selectedState) : t('odontogram.select_state')}
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {availableStates.map(s => {
              const active = selectedState === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => handleStateChange(s.id)}
                  className={`
                    px-2.5 py-1.5 rounded-lg border-2 transition-all text-[10px] font-bold
                    ${active
                      ? `${STATE_BTN[s.id]} ring-2 ring-offset-1 ring-blue-400 scale-105 shadow-sm`
                      : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'
                    }
                  `}
                >
                  {STATE_SYMBOLS[s.id]} {s.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Odontogram chart — FDI layout */}
      <div className="mb-6 overflow-x-auto">
        <div className="min-w-max mx-auto flex flex-col items-center gap-0">

          {/* UPPER ARCH — circles on top, numbers below */}
          <div className="flex gap-0 items-end">
            {/* Q1: upper-right 1.8 → 1.1 */}
            <div className="pr-3 sm:pr-4 border-r-2 border-slate-400">
              {renderTeethRow(UPPER_RIGHT, true)}
            </div>
            {/* Q2: upper-left 2.1 → 2.8 */}
            <div className="pl-3 sm:pl-4">
              {renderTeethRow(UPPER_LEFT, true)}
            </div>
          </div>

          {/* Horizontal divider between arches */}
          <div className="w-full my-1.5">
            <div className="h-[2px] bg-slate-400 rounded-full"></div>
          </div>

          {/* LOWER ARCH — numbers on top, circles below */}
          <div className="flex gap-0 items-start">
            {/* Q4: lower-right 4.8 → 4.1 */}
            <div className="pr-3 sm:pr-4 border-r-2 border-slate-400">
              {renderTeethRow(LOWER_RIGHT, false)}
            </div>
            {/* Q3: lower-left 3.1 → 3.8 */}
            <div className="pl-3 sm:pl-4">
              {renderTeethRow(LOWER_LEFT, false)}
            </div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="border-t border-slate-100 pt-4">
        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">{t('odontogram.legend')}</h4>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {availableStates.map(s => {
            const fills = STATE_FILLS[s.id];
            return (
              <div key={s.id} className="flex items-center gap-2">
                <svg viewBox="0 0 40 40" className="w-5 h-5 shrink-0">
                  <circle cx="20" cy="20" r="17" fill={fills.fill} stroke={fills.stroke} strokeWidth="2" />
                  <line x1="20" y1="3" x2="20" y2="37" stroke={fills.stroke} strokeWidth="1" opacity="0.5" />
                  <line x1="3" y1="20" x2="37" y2="20" stroke={fills.stroke} strokeWidth="1" opacity="0.5" />
                  <circle cx="20" cy="20" r="7" fill={fills.fill} stroke={fills.stroke} strokeWidth="1" />
                  {s.id === 'extraction' && (
                    <>
                      <line x1="8" y1="8" x2="32" y2="32" stroke="#dc2626" strokeWidth="2.5" />
                      <line x1="32" y1="8" x2="8" y2="32" stroke="#dc2626" strokeWidth="2.5" />
                    </>
                  )}
                  {s.id === 'missing' && (
                    <line x1="10" y1="20" x2="30" y2="20" stroke="#94a3b8" strokeWidth="3" strokeLinecap="round" />
                  )}
                </svg>
                <span className="text-[11px] text-slate-600 font-medium">{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {readOnly && (
        <div className="mt-4 p-3 bg-sky-50 border border-sky-200 text-sky-700 rounded-xl text-xs font-medium">
          {t('odontogram.read_only_notice')}
        </div>
      )}
    </div>
  );
}
