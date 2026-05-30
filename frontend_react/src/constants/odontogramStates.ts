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
  // ── PREEXISTENTE (25) — colores VIVOS, alto contraste sobre fondo oscuro ──
  { id: 'healthy', category: 'preexistente', labelKey: 'odontogram.states.healthy', defaultColor: '#f0f0f0', symbol: '○', printColor: { fill: '#f5f5f5', stroke: '#9ca3af' } },
  { id: 'implante', category: 'preexistente', labelKey: 'odontogram.states.implante', defaultColor: '#60a5fa', symbol: 'Im', printColor: { fill: '#dbeafe', stroke: '#2563eb' } },
  { id: 'radiografia', category: 'preexistente', labelKey: 'odontogram.states.radiografia', defaultColor: '#fbbf24', symbol: 'Rx', printColor: { fill: '#fef3c7', stroke: '#d97706' } },
  { id: 'restauracion_resina', category: 'preexistente', labelKey: 'odontogram.states.restauracion_resina', defaultColor: '#fbbf24', symbol: 'Rr', printColor: { fill: '#fef3c7', stroke: '#d97706' } },
  { id: 'restauracion_amalgama', category: 'preexistente', labelKey: 'odontogram.states.restauracion_amalgama', defaultColor: '#9ca3af', symbol: 'Ra', printColor: { fill: '#d1d5db', stroke: '#4b5563' } },
  { id: 'restauracion_temporal', category: 'preexistente', labelKey: 'odontogram.states.restauracion_temporal', defaultColor: '#fcd34d', symbol: 'Rt', printColor: { fill: '#fef9c3', stroke: '#b45309' } },
  { id: 'sellador_fisuras', category: 'preexistente', labelKey: 'odontogram.states.sellador_fisuras', defaultColor: '#fcd34d', symbol: 'Sf', printColor: { fill: '#fef9c3', stroke: '#b45309' } },
  { id: 'carilla', category: 'preexistente', labelKey: 'odontogram.states.carilla', defaultColor: '#a78bfa', symbol: 'Ca', printColor: { fill: '#ede9fe', stroke: '#7c3aed' } },
  { id: 'puente', category: 'preexistente', labelKey: 'odontogram.states.puente', defaultColor: '#60a5fa', symbol: 'Pu', printColor: { fill: '#dbeafe', stroke: '#2563eb' } },
  { id: 'corona_porcelana', category: 'preexistente', labelKey: 'odontogram.states.corona_porcelana', defaultColor: '#3b82f6', symbol: 'Cp', printColor: { fill: '#dbeafe', stroke: '#1d4ed8' } },
  { id: 'corona_resina', category: 'preexistente', labelKey: 'odontogram.states.corona_resina', defaultColor: '#fb7185', symbol: 'Cr', printColor: { fill: '#fce7f3', stroke: '#db2777' } },
  { id: 'corona_metalceramica', category: 'preexistente', labelKey: 'odontogram.states.corona_metalceramica', defaultColor: '#b45309', symbol: 'Cm', printColor: { fill: '#fef3c7', stroke: '#b45309' } },
  { id: 'corona_temporal', category: 'preexistente', labelKey: 'odontogram.states.corona_temporal', defaultColor: '#d97706', symbol: 'Ct', printColor: { fill: '#fef3c7', stroke: '#b45309' } },
  { id: 'incrustacion', category: 'preexistente', labelKey: 'odontogram.states.incrustacion', defaultColor: '#fbbf24', symbol: 'In', printColor: { fill: '#fef3c7', stroke: '#d97706' } },
  { id: 'onlay', category: 'preexistente', labelKey: 'odontogram.states.onlay', defaultColor: '#f59e0b', symbol: 'On', printColor: { fill: '#fef3c7', stroke: '#b45309' } },
  { id: 'poste', category: 'preexistente', labelKey: 'odontogram.states.poste', defaultColor: '#f97316', symbol: 'Po', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'perno', category: 'preexistente', labelKey: 'odontogram.states.perno', defaultColor: '#9ca3af', symbol: 'Pe', printColor: { fill: '#d1d5db', stroke: '#525252' } },
  { id: 'fibras_ribbond', category: 'preexistente', labelKey: 'odontogram.states.fibras_ribbond', defaultColor: '#a78bfa', symbol: 'FR', printColor: { fill: '#ede9fe', stroke: '#7c3aed' } },
  { id: 'tratamiento_conducto', category: 'preexistente', labelKey: 'odontogram.states.tratamiento_conducto', defaultColor: '#f97316', symbol: 'Tc', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'protesis_removible', category: 'preexistente', labelKey: 'odontogram.states.protesis_removible', defaultColor: '#60a5fa', symbol: 'Pr', printColor: { fill: '#dbeafe', stroke: '#2563eb' } },
  { id: 'diente_erupcion', category: 'preexistente', labelKey: 'odontogram.states.diente_erupcion', defaultColor: '#f97316', symbol: 'Ep', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'diente_no_erupcionado', category: 'preexistente', labelKey: 'odontogram.states.diente_no_erupcionado', defaultColor: '#f97316', symbol: 'NE', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'ausente', category: 'preexistente', labelKey: 'odontogram.states.ausente', defaultColor: '#6b7280', symbol: '--', printColor: { fill: '#e5e7eb', stroke: '#6b7280' } },
  { id: 'otra_preexistencia', category: 'preexistente', labelKey: 'odontogram.states.otra_preexistencia', defaultColor: '#f97316', symbol: 'OP', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'treatment_planned', category: 'preexistente', labelKey: 'odontogram.states.treatment_planned', defaultColor: '#f59e0b', symbol: 'Tp', printColor: { fill: '#fef08a', stroke: '#ca8a04' } },

  // ── LESIÓN (17) — colores VIVOS, alto contraste sobre fondo oscuro ──
  { id: 'mancha_blanca', category: 'lesion', labelKey: 'odontogram.states.mancha_blanca', defaultColor: '#fef3c7', symbol: 'MB', printColor: { fill: '#fffbeb', stroke: '#d97706' } },
  { id: 'surco_profundo', category: 'lesion', labelKey: 'odontogram.states.surco_profundo', defaultColor: '#f97316', symbol: 'SP', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'caries', category: 'lesion', labelKey: 'odontogram.states.caries', defaultColor: '#991b1b', symbol: 'C', printColor: { fill: '#fecaca', stroke: '#991b1b' } },
  { id: 'caries_penetrante', category: 'lesion', labelKey: 'odontogram.states.caries_penetrante', defaultColor: '#7f1d1d', symbol: 'CP', printColor: { fill: '#fecaca', stroke: '#7f1d1d' } },
  { id: 'necrosis_pulpar', category: 'lesion', labelKey: 'odontogram.states.necrosis_pulpar', defaultColor: '#374151', symbol: 'Np', printColor: { fill: '#d1d5db', stroke: '#111827' } },
  { id: 'proceso_apical', category: 'lesion', labelKey: 'odontogram.states.proceso_apical', defaultColor: '#dc2626', symbol: 'PA', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'fistula', category: 'lesion', labelKey: 'odontogram.states.fistula', defaultColor: '#ea580c', symbol: 'Fi', printColor: { fill: '#fed7aa', stroke: '#c2410c' } },
  { id: 'indicacion_extraccion', category: 'lesion', labelKey: 'odontogram.states.indicacion_extraccion', defaultColor: '#dc2626', symbol: 'Ex', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'abrasion', category: 'lesion', labelKey: 'odontogram.states.abrasion', defaultColor: '#ca8a04', symbol: 'Ab', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
  { id: 'abfraccion', category: 'lesion', labelKey: 'odontogram.states.abfraccion', defaultColor: '#ca8a04', symbol: 'Af', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
  { id: 'atricion', category: 'lesion', labelKey: 'odontogram.states.atricion', defaultColor: '#ca8a04', symbol: 'At', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
  { id: 'erosion', category: 'lesion', labelKey: 'odontogram.states.erosion', defaultColor: '#f97316', symbol: 'Er', printColor: { fill: '#ffedd5', stroke: '#c2410c' } },
  { id: 'fractura_horizontal', category: 'lesion', labelKey: 'odontogram.states.fractura_horizontal', defaultColor: '#f87171', symbol: 'Fh', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'fractura_vertical', category: 'lesion', labelKey: 'odontogram.states.fractura_vertical', defaultColor: '#f87171', symbol: 'Fv', printColor: { fill: '#fecaca', stroke: '#b91c1c' } },
  { id: 'movilidad', category: 'lesion', labelKey: 'odontogram.states.movilidad', defaultColor: '#fb7185', symbol: 'Mo', printColor: { fill: '#fce7f3', stroke: '#db2777' } },
  { id: 'hipomineralizacion_mih', category: 'lesion', labelKey: 'odontogram.states.hipomineralizacion_mih', defaultColor: '#fbbf24', symbol: 'MH', printColor: { fill: '#fef9c3', stroke: '#a16207' } },
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
        fill: `${hex}50`,
        stroke: hex,
        glow: `drop-shadow(0 0 6px ${hex}66)`,
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
