import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Save, RotateCcw, AlertCircle, Check } from 'lucide-react';
import api from '../api/axios';
import { ToothSVG, type SurfaceName } from './odontogram/ToothSVG';
import { OdontogramLegend } from './odontogram/OdontogramLegend';
import { OdontogramTabs, type DentitionType } from './odontogram/OdontogramTabs';
import { MobileToothZoom } from './odontogram/MobileToothZoom';
import SymbolSelectorModal from './odontogram/SymbolSelectorModal';
import { OdontogramState, normalizeLegacyStateId, getStateById } from '../constants/odontogramStates';

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

function buildDefaultTeeth(ids: number[]): ToothState[] {
  return ids.map(id => ({ id, state: 'healthy', surfaces: { ...DEFAULT_SURFACES }, notes: '' }));
}

function fdiLabel(id: number): string {
  return `${Math.floor(id / 10)}.${id % 10}`;
}

function computeToothState(surfaces: SurfaceStates): string {
  const nonHealthy = new Set(
    Object.values(surfaces).filter(s => s !== 'healthy')
  );
  if (nonHealthy.size === 1) return [...nonHealthy][0];
  return 'healthy';
}

/** Normalize legacy tooth data from API into current format */
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
      for (const sk of Object.keys(DEFAULT_SURFACES) as SurfaceName[]) {
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
      // No surface data → all surfaces inherit tooth state
      for (const sk of Object.keys(DEFAULT_SURFACES) as SurfaceName[]) {
        tooth.surfaces[sk] = state;
      }
    }
  }

  return Array.from(teethMap.values());
}

// ── Component ──

export default function Odontogram({ patientId, recordId, initialData, onSave, readOnly = false }: OdontogramProps) {
  const { t } = useTranslation();

  // Data
  const [permanentTeeth, setPermanentTeeth] = useState<ToothState[]>(() => buildDefaultTeeth(ALL_PERMANENT));
  const [deciduousTeeth, setDeciduousTeeth] = useState<ToothState[]>(() => buildDefaultTeeth(ALL_DECIDUOUS));
  const [activeDentition, setActiveDentition] = useState<DentitionType>('permanent');
  const initialRef = useRef<string>('');

  // Selection
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [selectedSurface, setSelectedSurface] = useState<SurfaceName | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [showMobileZoom, setShowMobileZoom] = useState(false);

  // UI state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [changedTeeth, setChangedTeeth] = useState<Set<number>>(new Set());
  const [hasChanges, setHasChanges] = useState(false);

  // Detect mobile
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;

  const teeth = activeDentition === 'permanent' ? permanentTeeth : deciduousTeeth;
  const setTeeth = activeDentition === 'permanent' ? setPermanentTeeth : setDeciduousTeeth;

  const hasDecidData = deciduousTeeth.some(t => t.state !== 'healthy');

  // ── Initialize from API data ──
  useEffect(() => {
    if (initialData) {
      // v3 format has permanent/deciduous objects
      if (initialData.permanent) {
        setPermanentTeeth(normalizeToothData(initialData.permanent, ALL_PERMANENT));
      } else if (initialData.teeth) {
        // v2 format — all teeth in one array, assume permanent
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

  // Track changes
  useEffect(() => {
    if (initialRef.current) {
      const current = JSON.stringify({ permanentTeeth, deciduousTeeth });
      setHasChanges(current !== initialRef.current);
    }
  }, [permanentTeeth, deciduousTeeth]);

  // Collect used states for legend
  const usedStates = new Set<string>();
  [...permanentTeeth, ...deciduousTeeth].forEach(tooth => {
    if (tooth.state !== 'healthy') usedStates.add(tooth.state);
    Object.values(tooth.surfaces).forEach(s => {
      if (s !== 'healthy') usedStates.add(s);
    });
  });

  // ── Handlers ──

  const markChanged = useCallback((toothId: number) => {
    setChangedTeeth(prev => new Set(prev).add(toothId));
    setTimeout(() => {
      setChangedTeeth(prev => {
        const next = new Set(prev);
        next.delete(toothId);
        return next;
      });
    }, 500);
  }, []);

  const handleToothClick = (toothId: number) => {
    if (readOnly) return;

    if (selectedTooth === toothId) {
      // Already selected → on mobile show zoom, on desktop open modal for the tooth-level state
      if (isMobile) {
        setShowMobileZoom(true);
      } else {
        setSelectedSurface(null);
        setShowModal(true);
      }
    } else {
      setSelectedTooth(toothId);
      setSelectedSurface(null);
      setShowMobileZoom(false);
    }
  };

  const handleSurfaceClick = (toothId: number, surface: SurfaceName) => {
    if (readOnly) return;
    setSelectedTooth(toothId);
    setSelectedSurface(surface);
    setShowModal(true);
  };

  const handleStateSelect = (odState: OdontogramState) => {
    if (!selectedTooth) return;

    setTeeth(prev => prev.map(tooth => {
      if (tooth.id !== selectedTooth) return tooth;

      const newSurfaces = { ...tooth.surfaces };

      if (selectedSurface) {
        // Apply to specific surface
        newSurfaces[selectedSurface] = odState.id;
      } else {
        // Apply to ALL surfaces (whole tooth)
        for (const sk of Object.keys(DEFAULT_SURFACES) as SurfaceName[]) {
          newSurfaces[sk] = odState.id;
        }
      }

      return {
        ...tooth,
        state: computeToothState(newSurfaces),
        surfaces: newSurfaces,
      };
    }));

    markChanged(selectedTooth);
    setShowModal(false);
    setSelectedSurface(null);
  };

  const handleSave = async () => {
    if (readOnly) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const odontogramData = {
        version: '3.0',
        last_updated: new Date().toISOString(),
        active_dentition: activeDentition,
        permanent: { teeth: permanentTeeth },
        deciduous: { teeth: deciduousTeeth },
      };
      if (recordId) {
        await api.put(`/admin/patients/${patientId}/records/${recordId}/odontogram`, { odontogram_data: odontogramData });
      } else {
        await api.post(`/admin/patients/${patientId}/records`, { content: t('odontogram.automatic_note'), odontogram_data: odontogramData });
      }
      setSuccess(t('odontogram.save_success'));
      initialRef.current = JSON.stringify({ permanentTeeth, deciduousTeeth });
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
    if (activeDentition === 'permanent') {
      setPermanentTeeth(buildDefaultTeeth(ALL_PERMANENT));
    } else {
      setDeciduousTeeth(buildDefaultTeeth(ALL_DECIDUOUS));
    }
    setSelectedTooth(null);
    setSelectedSurface(null);
  };

  // ── Render helpers ──

  const selectedToothData = selectedTooth ? teeth.find(t => t.id === selectedTooth) : null;

  const renderTeethRow = (ids: number[], numbersBelow: boolean) => (
    <div className="flex gap-[2px] sm:gap-1">
      {ids.map(id => {
        const tooth = teeth.find(t => t.id === id);
        if (!tooth) return null;
        const isSelected = selectedTooth === id;
        return (
          <div key={id} className="flex flex-col items-center">
            {!numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mb-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>
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
              selectedSurface={isSelected ? selectedSurface : null}
              onSurfaceClick={(surface) => handleSurfaceClick(id, surface)}
            />
            {numbersBelow && (
              <span className={`text-[9px] sm:text-[10px] font-bold mt-0.5 select-none transition-colors duration-200 ${isSelected ? 'text-blue-400' : 'text-white/40'}`}>
                {fdiLabel(id)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );

  const upperRight = activeDentition === 'permanent' ? PERM_UPPER_RIGHT : DECID_UPPER_RIGHT;
  const upperLeft = activeDentition === 'permanent' ? PERM_UPPER_LEFT : DECID_UPPER_LEFT;
  const lowerRight = activeDentition === 'permanent' ? PERM_LOWER_RIGHT : DECID_LOWER_RIGHT;
  const lowerLeft = activeDentition === 'permanent' ? PERM_LOWER_LEFT : DECID_LOWER_LEFT;

  // Current surface state for the modal
  const currentSurfaceState = selectedToothData && selectedSurface
    ? selectedToothData.surfaces[selectedSurface]
    : selectedToothData?.state || 'healthy';

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

      {/* Header */}
      <div className="mb-5">
        <h3 className="text-lg font-bold text-white">{t('odontogram.title')}</h3>
        <p className="text-xs text-white/40">{t('odontogram.subtitle')}</p>
      </div>

      {/* Dentition Tabs */}
      <div className="mb-4">
        <OdontogramTabs
          activeDentition={activeDentition}
          onChange={(d) => {
            setActiveDentition(d);
            setSelectedTooth(null);
            setSelectedSurface(null);
          }}
          hasDecidData={hasDecidData}
        />
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

      {/* Selected tooth info bar */}
      {!readOnly && selectedToothData && (
        <div className="mb-4 p-3 bg-white/[0.03] rounded-xl border border-white/[0.06] animate-[fadeIn_0.2s_ease-out]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white/50">{t('odontogram.piece')}</span>
              <span className="text-lg font-black text-blue-400">{fdiLabel(selectedTooth!)}</span>
            </div>
            <span className="text-[10px] text-white/30">—</span>
            <span className="text-xs text-white/50">
              {t(`odontogram.states.${selectedToothData.state}`, selectedToothData.state)}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => { setSelectedSurface(null); setShowModal(true); }}
                className="px-3 py-1.5 text-[10px] font-bold bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-colors"
              >
                {t('odontogram.change_state', 'Cambiar estado')}
              </button>
              <button
                onClick={() => { setSelectedTooth(null); setSelectedSurface(null); }}
                className="px-2 py-1.5 text-[10px] text-white/40 hover:text-white/60 transition-colors"
              >
                ✕
              </button>
            </div>
          </div>
          {/* Surface states summary */}
          <div className="flex gap-1 mt-2">
            {(Object.keys(DEFAULT_SURFACES) as SurfaceName[]).map(sk => {
              const surfState = selectedToothData.surfaces[sk];
              const stateInfo = getStateById(surfState);
              const isActiveSurf = selectedSurface === sk;
              return (
                <button
                  key={sk}
                  onClick={() => handleSurfaceClick(selectedTooth!, sk)}
                  className={`flex-1 px-1 py-1 rounded text-center text-[9px] border transition-all ${
                    isActiveSurf
                      ? 'bg-blue-500/20 border-blue-500/40 text-blue-300'
                      : surfState !== 'healthy'
                        ? 'border-white/10 text-white/60'
                        : 'bg-white/[0.02] border-white/[0.06] text-white/30'
                  }`}
                  style={surfState !== 'healthy' && stateInfo ? { borderColor: stateInfo.defaultColor + '40' } : undefined}
                >
                  <div className="font-bold">{stateInfo?.symbol || '○'}</div>
                  <div className="truncate">{t(`odontogram.surfaces.${sk}`, sk)}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Instruction hint when no tooth is selected */}
      {!readOnly && !selectedToothData && (
        <div className="mb-4 text-center text-xs text-white/30 py-2">
          {t('odontogram.hint_select', 'Tocá un diente para editarlo, o una sección específica')}
        </div>
      )}

      {/* Odontogram chart */}
      <div className="mb-6 overflow-x-auto">
        <div className="min-w-max mx-auto flex flex-col items-center gap-0">
          {/* Upper jaw */}
          <div className="flex gap-1 sm:gap-2">
            {renderTeethRow(upperRight, false)}
            <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
            {renderTeethRow(upperLeft, false)}
          </div>

          {/* Jaw separator */}
          <div className="w-full max-w-md my-2">
            <div className="h-[2px] bg-white/[0.10] rounded-full" />
          </div>

          {/* Lower jaw */}
          <div className="flex gap-1 sm:gap-2">
            {renderTeethRow(lowerRight, true)}
            <div className="w-px bg-white/[0.08] mx-1 self-stretch" />
            {renderTeethRow(lowerLeft, true)}
          </div>
        </div>
      </div>

      {/* Legend */}
      <OdontogramLegend usedStates={usedStates} />

      {/* Floating action buttons */}
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
            {saving ? t('odontogram.saving') : t('odontogram.save')}
          </button>
        </div>
      )}

      {/* State selector modal */}
      <SymbolSelectorModal
        isOpen={showModal}
        onClose={() => { setShowModal(false); setSelectedSurface(null); }}
        onSelect={handleStateSelect}
        currentStateId={currentSurfaceState}
      />

      {/* Mobile tooth zoom */}
      {showMobileZoom && selectedToothData && (
        <div className="fixed inset-0 z-40 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowMobileZoom(false)} />
          <div className="relative z-50">
            <MobileToothZoom
              toothId={selectedTooth!}
              toothState={selectedToothData.state}
              surfaceStates={selectedToothData.surfaces as Record<SurfaceName, string>}
              selectedSurface={selectedSurface}
              onSurfaceClick={(surface) => {
                setSelectedSurface(surface);
                setShowMobileZoom(false);
                setShowModal(true);
              }}
              onClose={() => setShowMobileZoom(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
