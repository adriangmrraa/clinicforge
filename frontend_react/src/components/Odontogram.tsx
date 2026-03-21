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

// FDI standard: Quadrant 1 (upper-right) 18→11, Q2 (upper-left) 21→28, Q3 (lower-left) 31→38, Q4 (lower-right) 48→41
const UPPER_RIGHT: number[] = [18, 17, 16, 15, 14, 13, 12, 11]; // Q1 - patient's upper right
const UPPER_LEFT: number[] = [21, 22, 23, 24, 25, 26, 27, 28];  // Q2 - patient's upper left
const LOWER_LEFT: number[] = [31, 32, 33, 34, 35, 36, 37, 38];  // Q3 - patient's lower left
const LOWER_RIGHT: number[] = [48, 47, 46, 45, 44, 43, 42, 41]; // Q4 - patient's lower right

const ALL_TEETH = [...UPPER_RIGHT, ...UPPER_LEFT, ...LOWER_LEFT, ...LOWER_RIGHT];

// Colors: filled circle bg + border + text for each state
const STATE_STYLES: Record<ToothStatus, { bg: string; border: string; text: string; ring: string }> = {
  healthy:           { bg: 'bg-emerald-50',  border: 'border-emerald-300', text: 'text-emerald-700', ring: 'ring-emerald-400' },
  caries:            { bg: 'bg-red-100',     border: 'border-red-400',     text: 'text-red-700',     ring: 'ring-red-400' },
  restoration:       { bg: 'bg-sky-100',     border: 'border-sky-400',     text: 'text-sky-700',     ring: 'ring-sky-400' },
  extraction:        { bg: 'bg-slate-200',   border: 'border-slate-400',   text: 'text-slate-500',   ring: 'ring-slate-400' },
  treatment_planned: { bg: 'bg-amber-100',   border: 'border-amber-400',   text: 'text-amber-700',   ring: 'ring-amber-400' },
  crown:             { bg: 'bg-violet-100',  border: 'border-violet-400',  text: 'text-violet-700',  ring: 'ring-violet-400' },
  implant:           { bg: 'bg-indigo-100',  border: 'border-indigo-400',  text: 'text-indigo-700',  ring: 'ring-indigo-400' },
  missing:           { bg: 'bg-slate-100',   border: 'border-dashed border-slate-300', text: 'text-slate-400', ring: 'ring-slate-300' },
  prosthesis:        { bg: 'bg-teal-100',    border: 'border-teal-400',    text: 'text-teal-700',    ring: 'ring-teal-400' },
  root_canal:        { bg: 'bg-orange-100',  border: 'border-orange-400',  text: 'text-orange-700',  ring: 'ring-orange-400' },
};

const STATE_SYMBOLS: Record<ToothStatus, string> = {
  healthy: '',
  caries: 'C',
  restoration: 'R',
  extraction: '✕',
  treatment_planned: 'P',
  crown: 'Co',
  implant: 'Im',
  missing: '—',
  prosthesis: 'Pr',
  root_canal: 'Tc',
};

export default function Odontogram({ patientId, recordId, initialData, onSave, readOnly = false }: OdontogramProps) {
  const { t } = useTranslation();
  const [teeth, setTeeth] = useState<ToothState[]>([]);
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [selectedState, setSelectedState] = useState<string>('healthy');
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
    setSelectedTooth(toothId);
    const tooth = teeth.find(t => t.id === toothId);
    if (tooth) setSelectedState(tooth.state);
  };

  const handleStateChange = (state: string) => {
    if (readOnly || !selectedTooth) return;
    setSelectedState(state);
    setTeeth(prev => prev.map(tooth =>
      tooth.id === selectedTooth ? { ...tooth, state: state as ToothStatus } : tooth
    ));
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

  const renderTooth = (toothId: number) => {
    const tooth = teeth.find(t => t.id === toothId);
    const state = (tooth?.state || 'healthy') as ToothStatus;
    const isSelected = selectedTooth === toothId;
    const style = STATE_STYLES[state] || STATE_STYLES.healthy;
    const symbol = STATE_SYMBOLS[state] || '';
    const hasIssue = state !== 'healthy';

    return (
      <button
        key={toothId}
        onClick={() => handleToothClick(toothId)}
        disabled={readOnly}
        className={`
          relative w-11 h-11 sm:w-12 sm:h-12 rounded-full border-2 flex flex-col items-center justify-center
          transition-all duration-150 shrink-0
          ${style.bg} ${style.border} ${style.text}
          ${isSelected ? `ring-2 ${style.ring} ring-offset-1 scale-110 shadow-md` : ''}
          ${readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-110 hover:shadow-md active:scale-95'}
        `}
        title={`${toothId} - ${tooth ? t('odontogram.states.' + state) : ''}`}
      >
        {/* Tooth number */}
        <span className={`text-[10px] font-bold leading-none ${hasIssue ? '' : 'text-slate-500'}`}>{toothId}</span>
        {/* State symbol */}
        {symbol && <span className="text-[9px] font-black leading-none mt-0.5">{symbol}</span>}
        {/* Dot indicator for non-healthy */}
        {hasIssue && state !== 'missing' && (
          <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-red-500 border border-white"></div>
        )}
      </button>
    );
  };

  const renderQuadrant = (teeth: number[], label: string) => (
    <div className="flex gap-1 sm:gap-1.5">
      {teeth.map(id => renderTooth(id))}
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

      {/* State selector panel */}
      {selectedTooth && !readOnly && (
        <div className="mb-5 p-4 bg-slate-50/80 rounded-2xl border border-slate-100">
          <div className="flex items-center gap-2.5 mb-3">
            <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm ${STATE_STYLES[(teeth.find(t => t.id === selectedTooth)?.state || 'healthy') as ToothStatus].bg} ${STATE_STYLES[(teeth.find(t => t.id === selectedTooth)?.state || 'healthy') as ToothStatus].border} border-2`}>
              {selectedTooth}
            </div>
            <span className="text-sm font-semibold text-slate-700">
              {t('odontogram.selecting_tooth')} {selectedTooth}
            </span>
          </div>
          <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5">
            {availableStates.map(s => {
              const sty = STATE_STYLES[s.id];
              const active = selectedState === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => handleStateChange(s.id)}
                  className={`
                    px-1 py-2 rounded-xl border-2 transition-all text-center
                    ${active
                      ? `${sty.bg} ${sty.border} ${sty.text} shadow-sm scale-105`
                      : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300 hover:bg-slate-50'
                    }
                  `}
                >
                  <div className="text-xs font-black">{STATE_SYMBOLS[s.id] || '○'}</div>
                  <div className="text-[9px] font-semibold mt-0.5 leading-tight truncate">{s.label}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Dental chart — FDI layout */}
      <div className="mb-6">
        {/* Upper arch */}
        <div className="mb-1">
          <div className="text-center text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">{t('odontogram.upper_arch')}</div>
          <div className="overflow-x-auto pb-1">
            <div className="flex justify-center gap-0 min-w-max mx-auto">
              {/* Q1: upper-right (18→11) */}
              <div className="flex gap-1 sm:gap-1.5 pr-2 sm:pr-3 border-r-2 border-slate-300">
                {UPPER_RIGHT.map(id => renderTooth(id))}
              </div>
              {/* Q2: upper-left (21→28) */}
              <div className="flex gap-1 sm:gap-1.5 pl-2 sm:pl-3">
                {UPPER_LEFT.map(id => renderTooth(id))}
              </div>
            </div>
          </div>
        </div>

        {/* Midline separator */}
        <div className="flex items-center gap-2 my-2 px-4">
          <div className="flex-1 h-px bg-slate-200"></div>
          <span className="text-[9px] font-bold text-slate-300 uppercase tracking-widest">R / L</span>
          <div className="flex-1 h-px bg-slate-200"></div>
        </div>

        {/* Lower arch */}
        <div className="mt-1">
          <div className="overflow-x-auto pb-1">
            <div className="flex justify-center gap-0 min-w-max mx-auto">
              {/* Q4: lower-right (48→41) */}
              <div className="flex gap-1 sm:gap-1.5 pr-2 sm:pr-3 border-r-2 border-slate-300">
                {LOWER_RIGHT.map(id => renderTooth(id))}
              </div>
              {/* Q3: lower-left (31→38) */}
              <div className="flex gap-1 sm:gap-1.5 pl-2 sm:pl-3">
                {LOWER_LEFT.map(id => renderTooth(id))}
              </div>
            </div>
          </div>
          <div className="text-center text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-2">{t('odontogram.lower_arch')}</div>
        </div>
      </div>

      {/* Legend */}
      <div className="border-t border-slate-100 pt-4">
        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">{t('odontogram.legend')}</h4>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {availableStates.map(s => {
            const sty = STATE_STYLES[s.id];
            return (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-[8px] font-black shrink-0 ${sty.bg} ${sty.border} ${sty.text}`}>
                  {STATE_SYMBOLS[s.id] || '○'}
                </div>
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
