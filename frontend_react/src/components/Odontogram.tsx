import { useState, useEffect, useRef } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Save, RotateCcw, AlertCircle, Check } from 'lucide-react';
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

// SVG fill colors per state — dark theme with subtle glow
const STATE_FILLS: Record<ToothStatus, { fill: string; stroke: string; glow: string }> = {
  healthy:           { fill: 'rgba(255,255,255,0.06)', stroke: 'rgba(255,255,255,0.20)', glow: '' },
  caries:            { fill: 'rgba(239,68,68,0.12)', stroke: '#ef4444', glow: 'drop-shadow(0 0 4px rgba(239,68,68,0.3))' },
  restoration:       { fill: 'rgba(59,130,246,0.12)', stroke: '#3b82f6', glow: 'drop-shadow(0 0 4px rgba(59,130,246,0.3))' },
  root_canal:        { fill: 'rgba(249,115,22,0.12)', stroke: '#f97316', glow: 'drop-shadow(0 0 4px rgba(249,115,22,0.3))' },
  crown:             { fill: 'rgba(139,92,246,0.12)', stroke: '#8b5cf6', glow: 'drop-shadow(0 0 4px rgba(139,92,246,0.3))' },
  implant:           { fill: 'rgba(99,102,241,0.12)', stroke: '#6366f1', glow: 'drop-shadow(0 0 4px rgba(99,102,241,0.3))' },
  prosthesis:        { fill: 'rgba(20,184,166,0.12)', stroke: '#14b8a6', glow: 'drop-shadow(0 0 4px rgba(20,184,166,0.3))' },
  extraction:        { fill: 'rgba(255,255,255,0.03)', stroke: 'rgba(255,255,255,0.15)', glow: '' },
  missing:           { fill: 'rgba(255,255,255,0.02)', stroke: 'rgba(255,255,255,0.10)', glow: '' },
  treatment_planned: { fill: 'rgba(234,179,8,0.12)', stroke: '#eab308', glow: 'drop-shadow(0 0 4px rgba(234,179,8,0.3))' },
};

// Tailwind classes for state selector buttons
const STATE_BTN: Record<ToothStatus, string> = {
  healthy:           'bg-white/[0.06] border-white/[0.15] text-white/60',
  caries:            'bg-red-500/10 border-red-500/30 text-red-400',
  restoration:       'bg-blue-500/10 border-blue-500/30 text-blue-400',
  root_canal:        'bg-orange-500/10 border-orange-500/30 text-orange-400',
  crown:             'bg-violet-500/10 border-violet-500/30 text-violet-400',
  implant:           'bg-indigo-500/10 border-indigo-500/30 text-indigo-400',
  prosthesis:        'bg-teal-500/10 border-teal-500/30 text-teal-400',
  extraction:        'bg-white/[0.04] border-white/[0.12] text-white/40',
  missing:           'bg-white/[0.02] border-white/[0.08] text-white/30',
  treatment_planned: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
};

const STATE_SYMBOLS: Record<ToothStatus, string> = {
  healthy: '○', caries: 'C', restoration: 'R', root_canal: 'Tc',
  crown: 'Co', implant: 'Im', prosthesis: 'Pr', extraction: '✕',
  missing: '—', treatment_planned: 'P',
};

function fdiLabel(id: number): string {
  return `${Math.floor(id / 10)}.${id % 10}`;
}

// SVG paths for 4 surfaces + center
const SURFACE_PATHS = {
  top: 'M20,2 A18,18 0 0,1 38,20 L27,20 A7,7 0 0,0 20,13 Z',
  right: 'M38,20 A18,18 0 0,1 20,38 L20,27 A7,7 0 0,0 27,20 Z',
  bottom: 'M20,38 A18,18 0 0,1 2,20 L13,20 A7,7 0 0,0 20,27 Z',
  left: 'M2,20 A18,18 0 0,1 20,2 L20,13 A7,7 0 0,0 13,20 Z',
};

// Animated tooth SVG
function ToothSVG({
  toothId,
  state,
  isSelected,
  readOnly,
  onClick,
  justChanged,
}: {
  toothId: number;
  state: ToothStatus;
  isSelected: boolean;
  readOnly: boolean;
  onClick: () => void;
  justChanged: boolean;
}) {
  const fills = STATE_FILLS[state] || STATE_FILLS.healthy;
  const isAbsent = state === 'missing' || state === 'extraction';

  return (
    <svg
      viewBox="0 0 40 40"
      className={`w-[40px] h-[40px] sm:w-[44px] sm:h-[44px] shrink-0
        transition-all duration-300 ease-out
        ${readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-110 active:scale-90'}
        ${isSelected ? 'scale-115 z-10' : ''}
        ${justChanged ? 'animate-[toothPop_0.4s_ease-out]' : ''}
      `}
      style={{ filter: fills.glow || undefined }}
      onClick={readOnly ? undefined : onClick}
    >
      {/* Selection ring — animated dash rotation */}
      {isSelected && (
        <circle
          cx="20" cy="20" r="19.5"
          fill="none" stroke="#3b82f6" strokeWidth="1.5"
          strokeDasharray="4,3"
          className="animate-[spin_8s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />
      )}

      {/* 4 outer surfaces with transitions */}
      {(['top', 'right', 'bottom', 'left'] as const).map(surface => (
        <path
          key={surface}
          d={SURFACE_PATHS[surface]}
          fill={fills.fill}
          stroke={fills.stroke}
          strokeWidth="1"
          opacity={isAbsent ? 0.35 : 0.9}
          className="transition-all duration-500"
        />
      ))}

      {/* Center circle (occlusal) */}
      <circle
        cx="20" cy="20" r="7"
        fill={fills.fill}
        stroke={fills.stroke}
        strokeWidth="1"
        opacity={isAbsent ? 0.35 : 0.9}
        className="transition-all duration-500"
      />

      {/* Cross lines */}
      <line x1="20" y1="2" x2="20" y2="13" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="20" y1="27" x2="20" y2="38" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="2" y1="20" x2="13" y2="20" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />
      <line x1="27" y1="20" x2="38" y2="20" stroke={fills.stroke} strokeWidth="0.6" opacity={isAbsent ? 0.2 : 0.4} className="transition-all duration-500" />

      {/* X overlay for extraction — animated */}
      {state === 'extraction' && (
        <g className="animate-[fadeIn_0.3s_ease-out]">
          <line x1="6" y1="6" x2="34" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
          <line x1="34" y1="6" x2="6" y2="34" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" />
        </g>
      )}

      {/* Dash for missing */}
      {state === 'missing' && (
        <line x1="10" y1="20" x2="30" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="2.5" strokeLinecap="round" className="animate-[fadeIn_0.3s_ease-out]" />
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
  const [changedTeeth, setChangedTeeth] = useState<Set<number>>(new Set());
  const [hasChanges, setHasChanges] = useState(false);
  const initialTeethRef = useRef<string>('');

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
    const initial = initialData?.teeth
      ? initialData.teeth
      : ALL_TEETH.map(id => ({ id, state: 'healthy' as ToothStatus, surfaces: {}, notes: '' }));
    setTeeth(initial);
    initialTeethRef.current = JSON.stringify(initial);
  }, [initialData]);

  // Track changes
  useEffect(() => {
    if (initialTeethRef.current) {
      setHasChanges(JSON.stringify(teeth) !== initialTeethRef.current);
    }
  }, [teeth]);

  const handleToothClick = (toothId: number) => {
    if (readOnly) return;
    if (selectedTooth === toothId) {
      setTeeth(prev => prev.map(tooth =>
        tooth.id === toothId ? { ...tooth, state: selectedState } : tooth
      ));
      setChangedTeeth(prev => new Set(prev).add(toothId));
      setTimeout(() => {
        setChangedTeeth(prev => {
          const next = new Set(prev);
          next.delete(toothId);
          return next;
        });
      }, 500);
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
      setChangedTeeth(prev => new Set(prev).add(selectedTooth));
      setTimeout(() => {
        setChangedTeeth(prev => {
          const next = new Set(prev);
          next.delete(selectedTooth!);
          return next;
        });
      }, 500);
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
      initialTeethRef.current = JSON.stringify(teeth);
      setHasChanges(false);
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
              <span className={`text-[9px] sm:text-[10px] font-bold mb-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>{label}</span>
            )}
            <ToothSVG
              toothId={id}
              state={state}
              isSelected={isSelected}
              readOnly={readOnly}
              onClick={() => handleToothClick(id)}
              justChanged={changedTeeth.has(id)}
            />
            {numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mt-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>{label}</span>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="bg-white/[0.03] backdrop-blur-sm rounded-2xl border border-white/[0.06] p-4 sm:p-6 w-full max-w-full overflow-hidden relative pb-20">
      {/* Keyframes */}
      <style>{`
        @keyframes toothPop {
          0% { transform: scale(1); }
          30% { transform: scale(1.3); }
          60% { transform: scale(0.95); }
          100% { transform: scale(1); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); }
          50% { box-shadow: 0 0 12px 4px rgba(59,130,246,0.15); }
        }
      `}</style>

      {/* Header — title only, buttons moved to floating */}
      <div className="mb-5">
        <h3 className="text-lg font-bold text-white">{t('odontogram.title')}</h3>
        <p className="text-xs text-white/40">{t('odontogram.subtitle')}</p>
      </div>

      {/* Status messages */}
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl flex items-center gap-2 text-sm animate-[slideUp_0.3s_ease-out]">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-sm flex items-center gap-2 animate-[slideUp_0.3s_ease-out]">
          <Check size={16} />
          {success}
        </div>
      )}

      {/* State selector */}
      {!readOnly && (
        <div className="mb-5 p-3 bg-white/[0.03] rounded-2xl border border-white/[0.06]">
          <div className="flex items-center gap-2 mb-2">
            {selectedTooth && (
              <>
                <span className="text-xs font-bold text-white/50">{t('odontogram.selecting_tooth')}</span>
                <span className="text-sm font-black text-blue-400 animate-[fadeIn_0.2s_ease-out]">{fdiLabel(selectedTooth)}</span>
                <span className="text-[10px] text-white/30">—</span>
              </>
            )}
            <span className="text-[10px] font-bold text-white/30 uppercase tracking-wider">
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
                    px-2.5 py-1.5 rounded-lg border-2 text-[10px] font-bold
                    transition-all duration-200 ease-out
                    active:scale-90
                    ${active
                      ? `${STATE_BTN[s.id]} ring-2 ring-offset-1 ring-offset-[#06060e] ring-blue-400 scale-105`
                      : 'bg-white/[0.04] border-white/[0.10] text-white/50 hover:border-white/[0.20] hover:bg-white/[0.06]'
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
          {/* Upper jaw */}
          <div className="flex gap-1 sm:gap-2">
            {renderTeethRow(UPPER_RIGHT, false)}
            <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
            {renderTeethRow(UPPER_LEFT, false)}
          </div>

          {/* Jaw separator */}
          <div className="w-full max-w-md my-2">
            <div className="h-[2px] bg-white/[0.10] rounded-full" />
          </div>

          {/* Lower jaw */}
          <div className="flex gap-1 sm:gap-2">
            {renderTeethRow(LOWER_RIGHT, true)}
            <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
            {renderTeethRow(LOWER_LEFT, true)}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-white/[0.06]">
        <h4 className="text-[10px] font-bold text-white/30 uppercase tracking-widest mb-3">{t('odontogram.legend')}</h4>
        <div className="flex flex-wrap gap-2">
          {availableStates.map(s => {
            const fills = STATE_FILLS[s.id];
            return (
              <div key={s.id} className="flex items-center gap-1.5">
                <svg viewBox="0 0 12 12" className="w-3 h-3">
                  <circle cx="6" cy="6" r="5" fill={fills.fill} stroke={fills.stroke} strokeWidth="1" />
                </svg>
                <span className="text-[11px] text-white/50 font-medium">{s.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating action buttons — always visible at bottom */}
      {!readOnly && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 animate-[slideUp_0.4s_ease-out]">
          <button
            onClick={handleReset}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2.5 text-white/60 bg-[#0d1117]/90 backdrop-blur-xl border border-white/[0.10] rounded-full hover:bg-white/[0.08] disabled:opacity-50 text-xs font-semibold transition-all duration-200 shadow-lg shadow-black/30 active:scale-95"
          >
            <RotateCcw size={14} />
            {t('odontogram.reset')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className={`flex items-center gap-1.5 px-5 py-2.5 text-white rounded-full text-xs font-semibold transition-all duration-200 shadow-lg active:scale-95
              ${hasChanges
                ? 'bg-blue-600 hover:bg-blue-500 shadow-blue-600/30'
                : 'bg-white/[0.06] text-white/30 shadow-black/20 cursor-not-allowed'
              }
              ${saving ? 'animate-pulse' : ''}
            `}
            style={hasChanges ? { animation: 'pulseGlow 2s ease-in-out infinite' } : undefined}
          >
            {saving ? (
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save size={14} />
            )}
            {saving ? t('odontogram.saving') : hasChanges ? t('odontogram.save') : t('odontogram.save')}
          </button>
        </div>
      )}
    </div>
  );
}
