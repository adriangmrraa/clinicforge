import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Save, RotateCcw, AlertCircle, Check } from 'lucide-react';
import { io, Socket } from 'socket.io-client';
import { WS_URL } from '../api/axios';
import api from '../api/axios';
import { ToothSVG, SURFACE_PATHS, type SurfaceName } from './odontogram/ToothSVG';
import { SurfacePath } from './odontogram/SurfacePath';
import { OdontogramLegend } from './odontogram/OdontogramLegend';
import { OdontogramTabs, type DentitionType } from './odontogram/OdontogramTabs';
import SymbolSelectorModal from './odontogram/SymbolSelectorModal';
import { OdontogramState, normalizeLegacyStateId, getStateById, STATE_FILLS } from '../constants/odontogramStates';

// ── Types ──

interface SurfaceStates {
  occlusal: string;
  vestibular: string;
  lingual: string;
  mesial: string;
  distal: string;
}

interface ToothState {
  id: number;
  state: string;
  surfaces: SurfaceStates;
  notes: string;
}

interface OdontogramProps {
  patientId: number;
  recordId?: number;
  initialData?: any;
  onSave?: (data: any) => void;
  readOnly?: boolean;
}

// ── FDI quadrants ──

const PERM_UPPER_RIGHT = [18, 17, 16, 15, 14, 13, 12, 11];
const PERM_UPPER_LEFT  = [21, 22, 23, 24, 25, 26, 27, 28];
const PERM_LOWER_RIGHT = [48, 47, 46, 45, 44, 43, 42, 41];
const PERM_LOWER_LEFT  = [31, 32, 33, 34, 35, 36, 37, 38];

const DECID_UPPER_RIGHT = [55, 54, 53, 52, 51];
const DECID_UPPER_LEFT  = [61, 62, 63, 64, 65];
const DECID_LOWER_RIGHT = [85, 84, 83, 82, 81];
const DECID_LOWER_LEFT  = [71, 72, 73, 74, 75];

const ALL_PERMANENT = [...PERM_UPPER_RIGHT, ...PERM_UPPER_LEFT, ...PERM_LOWER_RIGHT, ...PERM_LOWER_LEFT];
const ALL_DECIDUOUS = [...DECID_UPPER_RIGHT, ...DECID_UPPER_LEFT, ...DECID_LOWER_RIGHT, ...DECID_LOWER_LEFT];

const DEFAULT_SURFACES: SurfaceStates = {
  occlusal: 'healthy', vestibular: 'healthy', lingual: 'healthy', mesial: 'healthy', distal: 'healthy',
};

const SURFACE_KEYS: SurfaceName[] = ['occlusal', 'vestibular', 'lingual', 'mesial', 'distal'];

function buildDefaultTeeth(ids: number[]): ToothState[] {
  return ids.map(id => ({ id, state: 'healthy', surfaces: { ...DEFAULT_SURFACES }, notes: '' }));
}

function fdiLabel(id: number): string {
  return `${Math.floor(id / 10)}.${id % 10}`;
}

function computeToothState(surfaces: SurfaceStates): string {
  const nonHealthy = new Set(Object.values(surfaces).filter(s => s !== 'healthy'));
  if (nonHealthy.size === 1) return [...nonHealthy][0];
  return 'healthy';
}

function normalizeToothData(raw: any, allIds: number[]): ToothState[] {
  if (!raw?.teeth || !Array.isArray(raw.teeth)) return buildDefaultTeeth(allIds);

  const teethMap = new Map<number, ToothState>();
  for (const id of allIds) {
    teethMap.set(id, { id, state: 'healthy', surfaces: { ...DEFAULT_SURFACES }, notes: '' });
  }

  for (const t of raw.teeth) {
    if (!t?.id || !teethMap.has(t.id)) continue;
    const tooth = teethMap.get(t.id)!;
    const state = normalizeLegacyStateId(t.state || 'healthy');
    tooth.state = state;
    tooth.notes = t.notes || '';

    if (t.surfaces && typeof t.surfaces === 'object') {
      for (const sk of SURFACE_KEYS) {
        const sv = t.surfaces[sk];
        if (sv && typeof sv === 'object' && sv.state) {
          tooth.surfaces[sk] = normalizeLegacyStateId(sv.state);
        } else if (sv && typeof sv === 'string') {
          tooth.surfaces[sk] = normalizeLegacyStateId(sv);
        } else {
          tooth.surfaces[sk] = state;
        }
      }
    } else {
      for (const sk of SURFACE_KEYS) {
        tooth.surfaces[sk] = state;
      }
    }
  }

  return Array.from(teethMap.values());
}

/**
 * 3x scaled paths for the zoomed inline tooth (120x120 viewBox).
 */
const ZOOM_PATHS: Record<SurfaceName, string> = {
  occlusal:   'M 60,39 A 21,21 0 1,0 60,81 A 21,21 0 1,0 60,39 Z',
  vestibular: 'M 22,22 A 54,54 0 0,1 98,22 L 75,45 A 21,21 0 0,0 45,45 Z',
  distal:     'M 98,22 A 54,54 0 0,1 98,98 L 75,75 A 21,21 0 0,0 75,45 Z',
  lingual:    'M 98,98 A 54,54 0 0,1 22,98 L 45,75 A 21,21 0 0,0 75,75 Z',
  mesial:     'M 22,98 A 54,54 0 0,1 22,22 L 45,45 A 21,21 0 0,0 45,75 Z',
};

// ── Component ──

export default function Odontogram({ patientId, recordId, initialData, onSave, readOnly = false }: OdontogramProps) {
  const { t } = useTranslation();

  const [permanentTeeth, setPermanentTeeth] = useState<ToothState[]>(() => buildDefaultTeeth(ALL_PERMANENT));
  const [deciduousTeeth, setDeciduousTeeth] = useState<ToothState[]>(() => buildDefaultTeeth(ALL_DECIDUOUS));
  const [activeDentition, setActiveDentition] = useState<DentitionType>('permanent');
  const initialRef = useRef<string>('');

  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [selectedSurface, setSelectedSurface] = useState<SurfaceName | null>(null);
  const [showModal, setShowModal] = useState(false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [changedTeeth, setChangedTeeth] = useState<Set<number>>(new Set());
  const [hasChanges, setHasChanges] = useState(false);
  const [novaUpdate, setNovaUpdate] = useState<string | null>(null);

  const teeth = activeDentition === 'permanent' ? permanentTeeth : deciduousTeeth;
  const setTeeth = activeDentition === 'permanent' ? setPermanentTeeth : setDeciduousTeeth;
  const hasDecidData = deciduousTeeth.some(t => t.state !== 'healthy');

  // ── Initialize ──
  useEffect(() => {
    if (initialData) {
      if (initialData.permanent) {
        setPermanentTeeth(normalizeToothData(initialData.permanent, ALL_PERMANENT));
      } else if (initialData.teeth) {
        setPermanentTeeth(normalizeToothData(initialData, ALL_PERMANENT));
      }
      if (initialData.deciduous) {
        setDeciduousTeeth(normalizeToothData(initialData.deciduous, ALL_DECIDUOUS));
      }
      if (initialData.active_dentition) {
        setActiveDentition(initialData.active_dentition);
      }
    }
    initialRef.current = JSON.stringify({ permanentTeeth, deciduousTeeth });
  }, [initialData]);

  useEffect(() => {
    if (initialRef.current) {
      setHasChanges(JSON.stringify({ permanentTeeth, deciduousTeeth }) !== initialRef.current);
    }
  }, [permanentTeeth, deciduousTeeth]);

  // ── WebSocket ──
  useEffect(() => {
    const jwt = localStorage.getItem('access_token');
    const socket: Socket = io(WS_URL, { transports: ['websocket', 'polling'], auth: { token: jwt || '' } });

    socket.on('ODONTOGRAM_UPDATED', (payload: { patient_id?: number; odontogram_data?: any }) => {
      if (payload.patient_id !== patientId || !payload.odontogram_data) return;
      const data = payload.odontogram_data;

      const animateUpdate = (newTeeth: ToothState[], setter: typeof setPermanentTeeth) => {
        setter(prev => {
          const changed = new Set<number>();
          for (const nt of newTeeth) {
            const old = prev.find(p => p.id === nt.id);
            if (old && JSON.stringify(old) !== JSON.stringify(nt)) changed.add(nt.id);
          }
          if (changed.size > 0) {
            setChangedTeeth(p => new Set([...p, ...changed]));
            setTimeout(() => setChangedTeeth(p => { const n = new Set(p); changed.forEach(id => n.delete(id)); return n; }), 800);
          }
          return newTeeth;
        });
      };

      if (data.permanent) animateUpdate(normalizeToothData(data.permanent, ALL_PERMANENT), setPermanentTeeth);
      if (data.deciduous) animateUpdate(normalizeToothData(data.deciduous, ALL_DECIDUOUS), setDeciduousTeeth);

      setNovaUpdate(t('odontogram.nova_updated', 'Nova actualizó el odontograma'));
      setTimeout(() => setNovaUpdate(null), 3000);
      setTimeout(() => { initialRef.current = JSON.stringify({ permanentTeeth, deciduousTeeth }); setHasChanges(false); }, 100);
    });

    return () => { socket.disconnect(); };
  }, [patientId]);

  // Used states for legend
  const usedStates = new Set<string>();
  [...permanentTeeth, ...deciduousTeeth].forEach(tooth => {
    if (tooth.state !== 'healthy') usedStates.add(tooth.state);
    Object.values(tooth.surfaces).forEach(s => { if (s !== 'healthy') usedStates.add(s); });
  });

  // ── Handlers ──

  const markChanged = useCallback((id: number) => {
    setChangedTeeth(p => new Set(p).add(id));
    setTimeout(() => setChangedTeeth(p => { const n = new Set(p); n.delete(id); return n; }), 500);
  }, []);

  const handleToothClick = (toothId: number) => {
    if (readOnly) return;
    if (selectedTooth === toothId) {
      setSelectedTooth(null);
      setSelectedSurface(null);
    } else {
      setSelectedTooth(toothId);
      setSelectedSurface(null);
    }
  };

  const handleSurfaceSelect = (surface: SurfaceName) => {
    setSelectedSurface(surface);
    setShowModal(true);
  };

  const handleStateSelect = (odState: OdontogramState) => {
    if (!selectedTooth || !selectedSurface) return;

    setTeeth(prev => prev.map(tooth => {
      if (tooth.id !== selectedTooth) return tooth;
      const newSurfaces = { ...tooth.surfaces };
      newSurfaces[selectedSurface!] = odState.id;
      return { ...tooth, state: computeToothState(newSurfaces), surfaces: newSurfaces };
    }));

    markChanged(selectedTooth);
    setShowModal(false);
    setSelectedSurface(null);
  };

  const handleSave = async () => {
    if (readOnly) return;
    setSaving(true); setError(null); setSuccess(null);
    try {
      const data = {
        version: '3.0', last_updated: new Date().toISOString(), active_dentition: activeDentition,
        permanent: { teeth: permanentTeeth }, deciduous: { teeth: deciduousTeeth },
      };
      if (recordId) {
        await api.put(`/admin/patients/${patientId}/records/${recordId}/odontogram`, { odontogram_data: data });
      } else {
        await api.post(`/admin/patients/${patientId}/records`, { content: t('odontogram.automatic_note'), odontogram_data: data });
      }
      setSuccess(t('odontogram.save_success'));
      initialRef.current = JSON.stringify({ permanentTeeth, deciduousTeeth });
      setHasChanges(false);
      if (onSave) onSave(data);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('odontogram.save_error'));
    } finally { setSaving(false); }
  };

  const handleReset = () => {
    if (readOnly) return;
    if (activeDentition === 'permanent') setPermanentTeeth(buildDefaultTeeth(ALL_PERMANENT));
    else setDeciduousTeeth(buildDefaultTeeth(ALL_DECIDUOUS));
    setSelectedTooth(null); setSelectedSurface(null);
  };

  // ── Render ──

  const selectedToothData = selectedTooth ? teeth.find(t => t.id === selectedTooth) : null;
  const upperRight = activeDentition === 'permanent' ? PERM_UPPER_RIGHT : DECID_UPPER_RIGHT;
  const upperLeft = activeDentition === 'permanent' ? PERM_UPPER_LEFT : DECID_UPPER_LEFT;
  const lowerRight = activeDentition === 'permanent' ? PERM_LOWER_RIGHT : DECID_LOWER_RIGHT;
  const lowerLeft = activeDentition === 'permanent' ? PERM_LOWER_LEFT : DECID_LOWER_LEFT;

  const currentSurfaceState = selectedToothData && selectedSurface
    ? selectedToothData.surfaces[selectedSurface] : 'healthy';

  const renderTeethRow = (ids: number[], numbersBelow: boolean) => (
    <div className="flex gap-px sm:gap-1">
      {ids.map(id => {
        const tooth = teeth.find(t => t.id === id);
        if (!tooth) return null;
        const isSelected = selectedTooth === id;
        return (
          <div key={id} className="flex flex-col items-center">
            {!numbersBelow && (
              <span className={`text-[8px] sm:text-[10px] font-bold mb-px select-none transition-colors ${isSelected ? 'text-blue-400' : 'text-white/35'}`}>
                {fdiLabel(id)}
              </span>
            )}
            <ToothSVG
              toothId={id}
              state={tooth.state}
              isSelected={isSelected}
              readOnly={readOnly}
              onClick={() => handleToothClick(id)}
              justChanged={changedTeeth.has(id)}
              surfaceStates={tooth.surfaces as Record<SurfaceName, string>}
            />
            {numbersBelow && (
              <span className={`text-[8px] sm:text-[10px] font-bold mt-px select-none transition-colors ${isSelected ? 'text-blue-400' : 'text-white/35'}`}>
                {fdiLabel(id)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );

  // Zoomed tooth inline component — shows an enlarged interactive tooth
  const renderZoomedTooth = () => {
    if (!selectedToothData) return null;
    const toothFills = STATE_FILLS[selectedToothData.state] || STATE_FILLS['healthy'];

    return (
      <div className="mb-4 animate-[fadeIn_0.2s_ease-out]">
        <div className="p-3 sm:p-4 bg-white/[0.03] rounded-xl border border-blue-500/20">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-black text-blue-400">{fdiLabel(selectedTooth!)}</span>
              <span className="text-[10px] text-white/30">—</span>
              <span className="text-[11px] text-white/50">
                {t(`odontogram.states.${selectedToothData.state}`, selectedToothData.state)}
              </span>
            </div>
            <button
              onClick={() => { setSelectedTooth(null); setSelectedSurface(null); }}
              className="w-7 h-7 rounded-full bg-white/5 text-white/30 flex items-center justify-center active:bg-white/10 transition-all touch-manipulation"
            >
              <span className="text-sm">✕</span>
            </button>
          </div>

          {/* Zoomed tooth + surface labels side by side */}
          <div className="flex items-center gap-3">
            {/* Big interactive tooth */}
            <div className="shrink-0">
              <svg viewBox="0 0 120 120" className="w-24 h-24 sm:w-28 sm:h-28">
                {SURFACE_KEYS.map(sk => (
                  <SurfacePath
                    key={sk}
                    pathD={ZOOM_PATHS[sk]}
                    surfaceName={sk}
                    state={selectedToothData.surfaces[sk]}
                    isSelected={false}
                    onClick={() => handleSurfaceSelect(sk)}
                  />
                ))}
                {/* Dividers */}
                <line x1="22" y1="22" x2="45" y2="45" stroke="#06060e" strokeWidth="2.5" opacity="0.9" />
                <line x1="98" y1="22" x2="75" y2="45" stroke="#06060e" strokeWidth="2.5" opacity="0.9" />
                <line x1="98" y1="98" x2="75" y2="75" stroke="#06060e" strokeWidth="2.5" opacity="0.9" />
                <line x1="22" y1="98" x2="45" y2="75" stroke="#06060e" strokeWidth="2.5" opacity="0.9" />
                <circle cx="60" cy="60" r="21" fill="none" stroke="#06060e" strokeWidth="2" opacity="0.85" />
                <circle cx="60" cy="60" r="54" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
              </svg>
            </div>

            {/* Surface buttons */}
            <div className="flex-1 grid grid-cols-1 gap-1.5">
              {SURFACE_KEYS.map(sk => {
                const surfState = selectedToothData.surfaces[sk];
                const info = getStateById(surfState);
                const isHealthy = surfState === 'healthy';
                return (
                  <button
                    key={sk}
                    onClick={() => handleSurfaceSelect(sk)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all duration-150
                      touch-manipulation active:scale-[0.97] ${
                      isHealthy
                        ? 'bg-white/[0.02] border-white/[0.06] active:bg-white/[0.05]'
                        : 'active:brightness-125'
                    }`}
                    style={!isHealthy && info ? {
                      backgroundColor: info.defaultColor + '10',
                      borderColor: info.defaultColor + '25',
                    } : undefined}
                  >
                    <span
                      className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold ${isHealthy ? 'text-white/20 bg-white/[0.04]' : ''}`}
                      style={!isHealthy && info ? { backgroundColor: info.defaultColor + '25', color: info.defaultColor } : undefined}
                    >
                      {info?.symbol || '○'}
                    </span>
                    <span className="text-[11px] text-white/60 font-medium">
                      {t(`odontogram.surfaces.${sk}`, sk)}
                    </span>
                    {!isHealthy && (
                      <span className="text-[9px] text-white/30 ml-auto truncate max-w-[80px]">
                        {t(`odontogram.states.${surfState}`, surfState)}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <p className="text-[9px] text-white/20 text-center mt-2">
            {t('odontogram.hint_surface_card', 'Tocá una superficie para cambiar su estado')}
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white/[0.03] backdrop-blur-sm rounded-2xl border border-white/[0.06] p-3 sm:p-6 w-full max-w-full overflow-hidden relative pb-20">
      <style>{`
        @keyframes toothPop { 0% { transform: scale(1); } 30% { transform: scale(1.3); } 60% { transform: scale(0.95); } 100% { transform: scale(1); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @keyframes pulseGlow { 0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); } 50% { box-shadow: 0 0 12px 4px rgba(59,130,246,0.15); } }
        @keyframes novaGlow { 0%, 100% { box-shadow: 0 0 0 0 rgba(168,85,247,0.4); } 50% { box-shadow: 0 0 16px 6px rgba(168,85,247,0.2); } }
      `}</style>

      {/* Header */}
      <div className="mb-4">
        <h3 className="text-base sm:text-lg font-bold text-white">{t('odontogram.title')}</h3>
        <p className="text-[11px] text-white/40">{t('odontogram.subtitle')}</p>
      </div>

      {/* Tabs */}
      <div className="mb-3">
        <OdontogramTabs
          activeDentition={activeDentition}
          onChange={(d) => { setActiveDentition(d); setSelectedTooth(null); setSelectedSurface(null); }}
          hasDecidData={hasDecidData}
        />
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-3 p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl flex items-center gap-2 text-xs animate-[fadeIn_0.3s]">
          <AlertCircle size={14} /> <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="mb-3 p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs flex items-center gap-2 animate-[fadeIn_0.3s]">
          <Check size={14} /> {success}
        </div>
      )}
      {novaUpdate && (
        <div className="mb-3 p-2.5 bg-purple-500/10 border border-purple-500/20 text-purple-300 rounded-xl text-xs flex items-center gap-2 animate-[fadeIn_0.3s]" style={{ animation: 'novaGlow 2s ease-in-out infinite, fadeIn 0.3s ease-out' }}>
          <span>✦</span> {novaUpdate}
        </div>
      )}

      {/* Zoomed tooth panel — appears when a tooth is selected */}
      {!readOnly && renderZoomedTooth()}

      {/* Hint */}
      {!readOnly && !selectedToothData && (
        <div className="mb-3 text-center text-[11px] text-white/20 py-1">
          {t('odontogram.hint_select', 'Tocá un diente para editarlo')}
        </div>
      )}

      {/* Chart */}
      <div className="mb-5 overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
        <div className="min-w-max mx-auto flex flex-col items-center gap-0">
          <div className="flex gap-0 sm:gap-1">
            {renderTeethRow(upperRight, false)}
            <div className="w-px bg-white/[0.08] mx-0.5 sm:mx-1 self-stretch" />
            {renderTeethRow(upperLeft, false)}
          </div>
          <div className="w-full max-w-xs sm:max-w-md my-1.5 sm:my-2">
            <div className="h-[1.5px] bg-white/[0.08] rounded-full" />
          </div>
          <div className="flex gap-0 sm:gap-1">
            {renderTeethRow(lowerRight, true)}
            <div className="w-px bg-white/[0.08] mx-0.5 sm:mx-1 self-stretch" />
            {renderTeethRow(lowerLeft, true)}
          </div>
        </div>
      </div>

      {/* Legend */}
      <OdontogramLegend usedStates={usedStates} />

      {/* Floating buttons */}
      {!readOnly && (
        <div className="fixed bottom-4 sm:bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 animate-[slideUp_0.4s]"
          style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        >
          <button
            onClick={handleReset}
            disabled={saving}
            className="flex items-center gap-1.5 px-3.5 py-2.5 text-white/60 bg-[#0d1117]/90 backdrop-blur-xl border border-white/[0.10] rounded-full text-[11px] font-semibold transition-all shadow-lg shadow-black/30 active:scale-95 touch-manipulation"
          >
            <RotateCcw size={13} /> {t('odontogram.reset')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-white rounded-full text-[11px] font-semibold transition-all shadow-lg active:scale-95 touch-manipulation
              ${hasChanges ? 'bg-blue-600 shadow-blue-600/30' : 'bg-white/[0.06] text-white/30 cursor-not-allowed'}
              ${saving ? 'animate-pulse' : ''}`}
            style={hasChanges ? { animation: 'pulseGlow 2s ease-in-out infinite' } : undefined}
          >
            {saving ? <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Save size={13} />}
            {saving ? t('odontogram.saving') : t('odontogram.save')}
          </button>
        </div>
      )}

      {/* Modal */}
      <SymbolSelectorModal
        isOpen={showModal}
        onClose={() => { setShowModal(false); setSelectedSurface(null); }}
        onSelect={handleStateSelect}
        currentStateId={currentSurfaceState}
        surfaceName={selectedSurface ? t(`odontogram.surfaces.${selectedSurface}`, selectedSurface) : undefined}
      />
    </div>
  );
}
