/**
 * odontogramStates.ts — Catálogo de estados del odontograma
 *
 * Define los 42 estados clínicos organizados en 2 categorías:
 * - PREEXISTENTE (25 estados): condiciones previas del diente
 * - LESIÓN (17 estados): patologías activas
 *
 * Espejo del catálogo Python: shared/odontogram_states.py
 * Ambos archivos DEBEN mantenerse sincronizados.
 */

export type OdontogramCategory = 'preexistente' | 'lesion';

export interface PrintColor {
  fill: string;
  stroke: string;
}

export interface OdontogramState {
  id: string;
  category: OdontogramCategory;
  labelKey: string;
  defaultColor: string;
  symbol: string;
  printColor: PrintColor;
}

// ── CATÁLOGO COMPLETO — 42 ESTADOS ──

export const ODONTOGRAM_STATES: OdontogramState[] = [
  // ── PREEXISTENTE (25) ──
  { id: 'healthy', category: 'preexistente', labelKey: 'odontogram.states.healthy', defaultColor: '#f0f0f0', symbol: '○', printColor: { fill: '#f5f5f5', stroke: '#9ca3af' } },
  { id: 'implante', category: 'preexistente', labelKey: 'odontogram.states.implante', defaultColor: '#6366f1', symbol: 'Im', printColor: { fill: '#e0e7ff', stroke: '#4338ca' } },
  { id: 'radiografia', category: 'preexistente', labelKey: 'odontogram.states.radiografia', defaultColor: '#f59e0b', symbol: 'Rx', printColor: { fill: '#fef3c7', stroke: '#d97706' } },
  { id: 'restauracion_resina', category: 'preexistente', labelKey: 'odontogram.states.restauracion_resina', defaultColor: '#3b82f6', symbol: 'Rr', printColor: { fill: '#dbeafe', stroke: '#1d4ed8' } },
  { id: 'restauracion_amalgama', category: 'preexistente', labelKey: 'odontogram.states.restauracion_amalgama', defaultColor: '#6b7280', symbol: 'Ra', printColor: { fill: '#e5e7eb', stroke: '#374151' } },
  { id: 'restauracion_temporal', category: 'preexistente', labelKey: 'odontogram.states.restauracion_temporal', defaultColor: '#a78bfa', symbol: 'Rt', printColor: { fill: '#ede9fe', stroke: '#7c3aed' } },
  { id: 'sellador_fisuras', category: 'preexistente', labelKey: 'odontogram.states.sellador_fisuras', defaultColor: '#10b981', symbol: 'Sf', printColor: { fill: '#d1fae5', stroke: '#065f46' } },
  { id: 'carilla', category: 'preexistente', labelKey: 'odontogram.states.carilla', defaultColor: '#ec4899', symbol: 'Ca', printColor: { fill: '#fce7f3', stroke: '#be185d' } },
  { id: 'puente', category: 'preexistente', labelKey: 'odontogram.states.puente', defaultColor: '#8b5cf6', symbol: 'Pu', printColor: { fill: '#ede9fe', stroke: '#6d28d9' } },
  { id: 'corona_porcelana', category: 'preexistente', labelKey: 'odontogram.states.corona_porcelana', defaultColor: '#d946ef', symbol: 'Cp', printColor: { fill: '#fae8ff', stroke: '#a21caf' } },
  { id: 'corona_resina', category: 'preexistente', labelKey: 'odontogram.states.corona_resina', defaultColor: '#a855f7', symbol: 'Cr', printColor: { fill: '#f3e8ff', stroke: '#7e22ce' } },
  { id: 'corona_metalceramica', category: 'preexistente', labelKey: 'odontogram.states.corona_metalceramica', defaultColor: '#7c3aed', symbol: 'Cm', printColor: { fill: '#ede9fe', stroke: '#5b21b6' } },
  { id: 'corona_temporal', category: 'preexistente', labelKey: 'odontogram.states.corona_temporal', defaultColor: '#d946ef', symbol: 'Ct', printColor: { fill: '#f5f3ff', stroke: '#9333ea' } },
  { id: 'incrustacion', category: 'preexistente', labelKey: 'odontogram.states.incrustacion', defaultColor: '#14b8a6', symbol: 'In', printColor: { fill: '#ccfbf1', stroke: '#0f766e' } },
  { id: 'onlay', category: 'preexistente', labelKey: 'odontogram.states.onlay', defaultColor: '#0d9488', symbol: 'On', printColor: { fill: '#99f6e4', stroke: '#115e59' } },
  { id: 'poste', category: 'preexistente', labelKey: 'odontogram.states.poste', defaultColor: '#f97316', symbol: 'Po', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'perno', category: 'preexistente', labelKey: 'odontogram.states.perno', defaultColor: '#ea580c', symbol: 'Pe', printColor: { fill: '#fed7aa', stroke: '#9a3412' } },
  { id: 'fibras_ribbond', category: 'preexistente', labelKey: 'odontogram.states.fibras_ribbond', defaultColor: '#84cc16', symbol: 'FR', printColor: { fill: '#ecfccb', stroke: '#4d7c0f' } },
  { id: 'tratamiento_conducto', category: 'preexistente', labelKey: 'odontogram.states.tratamiento_conducto', defaultColor: '#f97316', symbol: 'Tc', printColor: { fill: '#fed7aa', stroke: '#ea580c' } },
  { id: 'protesis_removible', category: 'preexistente', labelKey: 'odontogram.states.protesis_removible', defaultColor: '#14b8a6', symbol: 'Pr', printColor: { fill: '#99f6e4', stroke: '#0d9488' } },
  { id: 'diente_erupcion', category: 'preexistente', labelKey: 'odontogram.states.diente_erupcion', defaultColor: '#22c55e', symbol: 'Ep', printColor: { fill: '#dcfce7', stroke: '#16a34a' } },
  { id: 'diente_no_erupcionado', category: 'preexistente', labelKey: 'odontogram.states.diente_no_erupcionado', defaultColor: '#a3a3a3', symbol: 'NE', printColor: { fill: '#e5e5e5', stroke: '#737373' } },
  { id: 'ausente', category: 'preexistente', labelKey: 'odontogram.states.ausente', defaultColor: '#d4d4d4', symbol: '--', printColor: { fill: '#fafafa', stroke: '#ced4da' } },
  { id: 'otra_preexistencia', category: 'preexistente', labelKey: 'odontogram.states.otra_preexistencia', defaultColor: '#78716c', symbol: 'OP', printColor: { fill: '#e7e5e4', stroke: '#57534e' } },
  { id: 'treatment_planned', category: 'preexistente', labelKey: 'odontogram.states.treatment_planned', defaultColor: '#f59e0b', symbol: 'Tp', printColor: { fill: '#fef08a', stroke: '#ca8a04' } },

  // ── LESIÓN (17) ──
  { id: 'mancha_blanca', category: 'lesion', labelKey: 'odontogram.states.mancha_blanca', defaultColor: '#fef3c7', symbol: 'MB', printColor: { fill: '#fffbeb', stroke: '#d97706' } },
  { id: 'surco_profundo', category: 'lesion', labelKey: 'odontogram.states.surco_profundo', defaultColor: '#fbbf24', symbol: 'SP', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
  { id: 'caries', category: 'lesion', labelKey: 'odontogram.states.caries', defaultColor: '#ef4444', symbol: 'C', printColor: { fill: '#fecaca', stroke: '#dc2626' } },
  { id: 'caries_penetrante', category: 'lesion', labelKey: 'odontogram.states.caries_penetrante', defaultColor: '#b91c1c', symbol: 'CP', printColor: { fill: '#fca5a5', stroke: '#991b1b' } },
  { id: 'necrosis_pulpar', category: 'lesion', labelKey: 'odontogram.states.necrosis_pulpar', defaultColor: '#1f2937', symbol: 'Np', printColor: { fill: '#d1d5db', stroke: '#111827' } },
  { id: 'proceso_apical', category: 'lesion', labelKey: 'odontogram.states.proceso_apical', defaultColor: '#dc2626', symbol: 'PA', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'fistula', category: 'lesion', labelKey: 'odontogram.states.fistula', defaultColor: '#f97316', symbol: 'Fi', printColor: { fill: '#fed7aa', stroke: '#c2410c' } },
  { id: 'indicacion_extraccion', category: 'lesion', labelKey: 'odontogram.states.indicacion_extraccion', defaultColor: '#ef4444', symbol: 'Ex', printColor: { fill: '#f5f5f5', stroke: '#adb5bd' } },
  { id: 'abrasion', category: 'lesion', labelKey: 'odontogram.states.abrasion', defaultColor: '#fb923c', symbol: 'Ab', printColor: { fill: '#ffedd5', stroke: '#ea580c' } },
  { id: 'abfraccion', category: 'lesion', labelKey: 'odontogram.states.abfraccion', defaultColor: '#fcd34d', symbol: 'Af', printColor: { fill: '#fef9c3', stroke: '#ca8a04' } },
  { id: 'atricion', category: 'lesion', labelKey: 'odontogram.states.atricion', defaultColor: '#f59e0b', symbol: 'At', printColor: { fill: '#fef3c7', stroke: '#b45309' } },
  { id: 'erosion', category: 'lesion', labelKey: 'odontogram.states.erosion', defaultColor: '#fdba74', symbol: 'Er', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'fractura_horizontal', category: 'lesion', labelKey: 'odontogram.states.fractura_horizontal', defaultColor: '#ef4444', symbol: 'Fh', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'fractura_vertical', category: 'lesion', labelKey: 'odontogram.states.fractura_vertical', defaultColor: '#dc2626', symbol: 'Fv', printColor: { fill: '#fca5a5', stroke: '#991b1b' } },
  { id: 'movilidad', category: 'lesion', labelKey: 'odontogram.states.movilidad', defaultColor: '#fb7185', symbol: 'Mo', printColor: { fill: '#fecdd3', stroke: '#e11d48' } },
  { id: 'hipomineralizacion_mih', category: 'lesion', labelKey: 'odontogram.states.hipomineralizacion_mih', defaultColor: '#fbbf24', symbol: 'MH', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
  { id: 'otra_lesion', category: 'lesion', labelKey: 'odontogram.states.otra_lesion', defaultColor: '#78716c', symbol: 'Ol', printColor: { fill: '#e7e5e4', stroke: '#57534e' } },
];

// ── Lookups ──

const STATES_BY_ID = new Map<string, OdontogramState>(
  ODONTOGRAM_STATES.map(s => [s.id, s])
);

export const PREEXISTENTE_STATES = ODONTOGRAM_STATES.filter(s => s.category === 'preexistente');
export const LESION_STATES = ODONTOGRAM_STATES.filter(s => s.category === 'lesion');

export const VALID_STATE_IDS = new Set(ODONTOGRAM_STATES.map(s => s.id));

// ── Retrocompatibilidad ──

export const LEGACY_STATE_MAP: Record<string, string> = {
  healthy: 'healthy',
  caries: 'caries',
  restoration: 'restauracion_resina',
  root_canal: 'tratamiento_conducto',
  crown: 'corona_porcelana',
  implant: 'implante',
  prosthesis: 'protesis_removible',
  extraction: 'indicacion_extraccion',
  missing: 'ausente',
  treatment_planned: 'treatment_planned',
  treated: 'restauracion_resina',
  crowned: 'corona_porcelana',
  extracted: 'indicacion_extraccion',
};

// ── Funciones de lookup ──

export function getStateById(id: string): OdontogramState | undefined {
  return STATES_BY_ID.get(id);
}

export function getStatesByCategory(category: OdontogramCategory): OdontogramState[] {
  return ODONTOGRAM_STATES.filter(s => s.category === category);
}

export function normalizeLegacyStateId(oldId: string): string {
  return LEGACY_STATE_MAP[oldId] ?? oldId;
}

export function isValidState(stateId: string): boolean {
  return VALID_STATE_IDS.has(stateId);
}

/**
 * Busca estados por nombre (normaliza acentos para búsqueda fuzzy).
 */
export function searchStates(query: string): OdontogramState[] {
  if (!query.trim()) return ODONTOGRAM_STATES;
  const normalized = normalizeSearch(query.toLowerCase());
  return ODONTOGRAM_STATES.filter(s => {
    const label = normalizeSearch(s.labelKey.replace('odontogram.states.', '').replace(/_/g, ' '));
    return label.includes(normalized) || s.id.includes(normalized) || s.symbol.toLowerCase().includes(normalized);
  });
}

/**
 * Resuelve el color a usar: custom > default del estado > fallback healthy.
 */
export function resolveColor(stateId: string, customColor?: string | null): string {
  if (customColor) return customColor;
  const state = STATES_BY_ID.get(stateId);
  return state?.defaultColor ?? '#f0f0f0';
}

/**
 * Genera STATE_FILLS para el componente React (fill rgba, stroke, glow).
 */
export function buildStateFills(): Record<string, { fill: string; stroke: string; glow: string }> {
  const fills: Record<string, { fill: string; stroke: string; glow: string }> = {};
  for (const state of ODONTOGRAM_STATES) {
    const hex = state.defaultColor;
    if (state.id === 'healthy') {
      fills[state.id] = {
        fill: 'rgba(255,255,255,0.06)',
        stroke: 'rgba(255,255,255,0.20)',
        glow: '',
      };
    } else if (state.id === 'ausente' || state.id === 'indicacion_extraccion') {
      fills[state.id] = {
        fill: 'rgba(255,255,255,0.03)',
        stroke: 'rgba(255,255,255,0.15)',
        glow: '',
      };
    } else {
      fills[state.id] = {
        fill: `${hex}1F`,
        stroke: hex,
        glow: `drop-shadow(0 0 4px ${hex}4D)`,
      };
    }
  }
  return fills;
}

export const STATE_FILLS = buildStateFills();

// ── Utilidades internas ──

function normalizeSearch(str: string): string {
  return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}
