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
  { id: 'implante', category: 'preexistente', labelKey: 'odontogram.states.implante', defaultColor: '#9ca3af', symbol: 'Im', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'radiografia', category: 'preexistente', labelKey: 'odontogram.states.radiografia', defaultColor: '#f59e0b', symbol: 'Rx', printColor: { fill: '#fef3c7', stroke: '#d97706' } },
  { id: 'restauracion_resina', category: 'preexistente', labelKey: 'odontogram.states.restauracion_resina', defaultColor: '#f5d6b8', symbol: 'Rr', printColor: { fill: '#fef0e6', stroke: '#d4a373' } },
  { id: 'restauracion_amalgama', category: 'preexistente', labelKey: 'odontogram.states.restauracion_amalgama', defaultColor: '#6b7280', symbol: 'Ra', printColor: { fill: '#e5e7eb', stroke: '#374151' } },
  { id: 'restauracion_temporal', category: 'preexistente', labelKey: 'odontogram.states.restauracion_temporal', defaultColor: '#e8d5b7', symbol: 'Rt', printColor: { fill: '#f5efe6', stroke: '#c4a97d' } },
  { id: 'sellador_fisuras', category: 'preexistente', labelKey: 'odontogram.states.sellador_fisuras', defaultColor: '#e8d5b7', symbol: 'Sf', printColor: { fill: '#f5efe6', stroke: '#c4a97d' } },
  { id: 'carilla', category: 'preexistente', labelKey: 'odontogram.states.carilla', defaultColor: '#8b5cf6', symbol: 'Ca', printColor: { fill: '#ede9fe', stroke: '#6d28d9' } },
  { id: 'puente', category: 'preexistente', labelKey: 'odontogram.states.puente', defaultColor: '#9ca3af', symbol: 'Pu', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'corona_porcelana', category: 'preexistente', labelKey: 'odontogram.states.corona_porcelana', defaultColor: '#3b82f6', symbol: 'Cp', printColor: { fill: '#dbeafe', stroke: '#1d4ed8' } },
  { id: 'corona_resina', category: 'preexistente', labelKey: 'odontogram.states.corona_resina', defaultColor: '#f5bcb0', symbol: 'Cr', printColor: { fill: '#fef0ed', stroke: '#d49585' } },
  { id: 'corona_metalceramica', category: 'preexistente', labelKey: 'odontogram.states.corona_metalceramica', defaultColor: '#92400e', symbol: 'Cm', printColor: { fill: '#fef3c7', stroke: '#92400e' } },
  { id: 'corona_temporal', category: 'preexistente', labelKey: 'odontogram.states.corona_temporal', defaultColor: '#d4a574', symbol: 'Ct', printColor: { fill: '#f5efe6', stroke: '#b8926a' } },
  { id: 'incrustacion', category: 'preexistente', labelKey: 'odontogram.states.incrustacion', defaultColor: '#f5d6b8', symbol: 'In', printColor: { fill: '#fef0e6', stroke: '#d4a373' } },
  { id: 'onlay', category: 'preexistente', labelKey: 'odontogram.states.onlay', defaultColor: '#f5d6b8', symbol: 'On', printColor: { fill: '#fef0e6', stroke: '#d4a373' } },
  { id: 'poste', category: 'preexistente', labelKey: 'odontogram.states.poste', defaultColor: '#f97316', symbol: 'Po', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'perno', category: 'preexistente', labelKey: 'odontogram.states.perno', defaultColor: '#525252', symbol: 'Pe', printColor: { fill: '#d4d4d4', stroke: '#404040' } },
  { id: 'fibras_ribbond', category: 'preexistente', labelKey: 'odontogram.states.fibras_ribbond', defaultColor: '#9ca3af', symbol: 'FR', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'tratamiento_conducto', category: 'preexistente', labelKey: 'odontogram.states.tratamiento_conducto', defaultColor: '#6b7280', symbol: 'Tc', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'protesis_removible', category: 'preexistente', labelKey: 'odontogram.states.protesis_removible', defaultColor: '#9ca3af', symbol: 'Pr', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'diente_erupcion', category: 'preexistente', labelKey: 'odontogram.states.diente_erupcion', defaultColor: '#f97316', symbol: 'Ep', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'diente_no_erupcionado', category: 'preexistente', labelKey: 'odontogram.states.diente_no_erupcionado', defaultColor: '#f97316', symbol: 'NE', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'ausente', category: 'preexistente', labelKey: 'odontogram.states.ausente', defaultColor: '#d4d4d4', symbol: '--', printColor: { fill: '#fafafa', stroke: '#ced4da' } },
  { id: 'otra_preexistencia', category: 'preexistente', labelKey: 'odontogram.states.otra_preexistencia', defaultColor: '#f97316', symbol: 'OP', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'treatment_planned', category: 'preexistente', labelKey: 'odontogram.states.treatment_planned', defaultColor: '#f59e0b', symbol: 'Tp', printColor: { fill: '#fef08a', stroke: '#ca8a04' } },

  // ── LESIÓN (17) ──
  { id: 'mancha_blanca', category: 'lesion', labelKey: 'odontogram.states.mancha_blanca', defaultColor: '#fef3c7', symbol: 'MB', printColor: { fill: '#fffbeb', stroke: '#d97706' } },
  { id: 'surco_profundo', category: 'lesion', labelKey: 'odontogram.states.surco_profundo', defaultColor: '#6b7280', symbol: 'SP', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'caries', category: 'lesion', labelKey: 'odontogram.states.caries', defaultColor: '#78350f', symbol: 'C', printColor: { fill: '#fef3c7', stroke: '#78350f' } },
  { id: 'caries_penetrante', category: 'lesion', labelKey: 'odontogram.states.caries_penetrante', defaultColor: '#451a03', symbol: 'CP', printColor: { fill: '#fef3c7', stroke: '#451a03' } },
  { id: 'necrosis_pulpar', category: 'lesion', labelKey: 'odontogram.states.necrosis_pulpar', defaultColor: '#1f2937', symbol: 'Np', printColor: { fill: '#d1d5db', stroke: '#111827' } },
  { id: 'proceso_apical', category: 'lesion', labelKey: 'odontogram.states.proceso_apical', defaultColor: '#dc2626', symbol: 'PA', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'fistula', category: 'lesion', labelKey: 'odontogram.states.fistula', defaultColor: '#f97316', symbol: 'Fi', printColor: { fill: '#fed7aa', stroke: '#c2410c' } },
  { id: 'indicacion_extraccion', category: 'lesion', labelKey: 'odontogram.states.indicacion_extraccion', defaultColor: '#ef4444', symbol: 'Ex', printColor: { fill: '#f5f5f5', stroke: '#adb5bd' } },
  { id: 'abrasion', category: 'lesion', labelKey: 'odontogram.states.abrasion', defaultColor: '#d4d4d4', symbol: 'Ab', printColor: { fill: '#f5f5f5', stroke: '#737373' } },
  { id: 'abfraccion', category: 'lesion', labelKey: 'odontogram.states.abfraccion', defaultColor: '#d4d4d4', symbol: 'Af', printColor: { fill: '#f5f5f5', stroke: '#737373' } },
  { id: 'atricion', category: 'lesion', labelKey: 'odontogram.states.atricion', defaultColor: '#d4d4d4', symbol: 'At', printColor: { fill: '#f5f5f5', stroke: '#737373' } },
  { id: 'erosion', category: 'lesion', labelKey: 'odontogram.states.erosion', defaultColor: '#f97316', symbol: 'Er', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'fractura_horizontal', category: 'lesion', labelKey: 'odontogram.states.fractura_horizontal', defaultColor: '#6b7280', symbol: 'Fh', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'fractura_vertical', category: 'lesion', labelKey: 'odontogram.states.fractura_vertical', defaultColor: '#6b7280', symbol: 'Fv', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'movilidad', category: 'lesion', labelKey: 'odontogram.states.movilidad', defaultColor: '#d4d4d4', symbol: 'Mo', printColor: { fill: '#f5f5f5', stroke: '#737373' } },
  { id: 'hipomineralizacion_mih', category: 'lesion', labelKey: 'odontogram.states.hipomineralizacion_mih', defaultColor: '#d4d4d4', symbol: 'MH', printColor: { fill: '#f5f5f5', stroke: '#737373' } },
  { id: 'otra_lesion', category: 'lesion', labelKey: 'odontogram.states.otra_lesion', defaultColor: '#f97316', symbol: 'Ol', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
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
