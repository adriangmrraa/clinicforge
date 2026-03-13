import { useState, useEffect } from 'react';
import { AlertTriangle, Pill, Baby, HeartPulse, Cigarette, Scissors, Brain, Frown, CheckCircle, Edit2, Save, X } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

// ============================================================
// Tipos
// ============================================================
interface MedicalHistory {
  base_diseases?: string;
  habitual_medication?: string;
  allergies?: string;
  previous_surgeries?: string;
  is_smoker?: string;
  smoker_amount?: string;
  pregnancy_lactation?: string;
  negative_experiences?: string;
  specific_fears?: string;
  anamnesis_completed_at?: string;
  anamnesis_completed_via?: string;
  anamnesis_last_edited_by?: string;
  anamnesis_last_edited_at?: string;
}

interface AnamnesisField {
  key: keyof MedicalHistory;
  label: string;
  icon: React.ReactNode;
  alertLevel: 'none' | 'warning' | 'danger'; // badge visual si hay dato
}

interface AnamnesisпанelProps {
  /** Modo de carga: por ID de paciente o por teléfono */
  patientId?: number;
  phone?: string;
  /** Si se pasa directamente el objeto, no se hace fetch */
  medicalHistory?: MedicalHistory | null;
  /** El rol del usuario autenticado (para habilitar/deshabilitar edición) */
  userRole?: 'ceo' | 'secretary' | 'professional';
  /** Compacto = para panel lateral de ChatsView. Expandido = para PatientDetail tab */
  compact?: boolean;
  /** Callback tras guardar (para refrescar padre) */
  onSaved?: () => void;
}

// ============================================================
// Definición de campos
// ============================================================
const ANAMNESIS_FIELDS: AnamnesisField[] = [
  {
    key: 'base_diseases',
    label: 'Enfermedades de base',
    icon: <HeartPulse size={15} />,
    alertLevel: 'none',
  },
  {
    key: 'habitual_medication',
    label: 'Medicación habitual',
    icon: <Pill size={15} />,
    alertLevel: 'warning', // naranja si hay dato
  },
  {
    key: 'allergies',
    label: 'Alergias',
    icon: <AlertTriangle size={15} />,
    alertLevel: 'danger', // rojo si hay dato
  },
  {
    key: 'previous_surgeries',
    label: 'Cirugías previas',
    icon: <Scissors size={15} />,
    alertLevel: 'none',
  },
  {
    key: 'is_smoker',
    label: 'Fumador/a',
    icon: <Cigarette size={15} />,
    alertLevel: 'none',
  },
  {
    key: 'smoker_amount',
    label: 'Cantidad de cigarrillos',
    icon: <Cigarette size={15} />,
    alertLevel: 'none',
  },
  {
    key: 'pregnancy_lactation',
    label: 'Embarazo / Lactancia',
    icon: <Baby size={15} />,
    alertLevel: 'danger', // rojo si hay dato
  },
  {
    key: 'negative_experiences',
    label: 'Experiencias negativas',
    icon: <Frown size={15} />,
    alertLevel: 'none',
  },
  {
    key: 'specific_fears',
    label: 'Miedos específicos',
    icon: <Brain size={15} />,
    alertLevel: 'none',
  },
];

// ============================================================
// Helpers
// ============================================================
function isAlertValue(val?: string): boolean {
  if (!val) return false;
  const lower = val.toLowerCase().trim();
  return lower !== 'no' && lower !== 'ninguno' && lower !== 'ninguna' && lower !== '-' && lower !== '';
}

function alertClass(level: 'none' | 'warning' | 'danger', hasValue: boolean): string {
  if (!hasValue || level === 'none') return 'text-gray-500';
  if (level === 'danger') return 'text-red-500';
  return 'text-orange-500';
}

function badgeClass(level: 'none' | 'warning' | 'danger', hasValue: boolean): string {
  if (!hasValue || level === 'none') return '';
  if (level === 'danger') return 'inline-block ml-1 w-2 h-2 rounded-full bg-red-500';
  return 'inline-block ml-1 w-2 h-2 rounded-full bg-orange-400';
}

// ============================================================
// Componente principal
// ============================================================
export default function AnamnesisPanel({
  patientId,
  phone,
  medicalHistory: externalHistory,
  userRole = 'secretary',
  compact = false,
  onSaved,
}: AnamnesisпанelProps) {
  const { t } = useTranslation();
  const [history, setHistory] = useState<MedicalHistory | null>(externalHistory ?? null);
  const [resolvedPatientId, setResolvedPatientId] = useState<number | undefined>(patientId);
  const [loading, setLoading] = useState(!externalHistory && !!(patientId || phone));
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<MedicalHistory>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canEdit = userRole === 'ceo' || userRole === 'professional';

  // ---- Fetch si no se pasó medicalHistory directamente ----
  useEffect(() => {
    if (externalHistory !== undefined) {
      setHistory(externalHistory);
      setLoading(false);
      return;
    }
    if (!patientId && !phone) return;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        let res;
        if (patientId) {
          res = await api.get(`/admin/patients/${patientId}`);
        } else {
          res = await api.get(`/admin/patients/by-phone/${encodeURIComponent(phone!)}`);
          setResolvedPatientId(res.data?.id);
        }
        setHistory(res.data?.medical_history ?? null);
        if (!resolvedPatientId) setResolvedPatientId(res.data?.id);
      } catch (e: any) {
        setError(e?.response?.status === 404 ? 'Paciente no encontrado.' : 'Error al cargar anamnesis.');
      } finally {
        setLoading(false);
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId, phone]);

  // ---- Guardar ----
  const handleSave = async () => {
    if (!resolvedPatientId) return;
    setSaving(true);
    try {
      const res = await api.patch(`/admin/patients/${resolvedPatientId}/anamnesis`, editData);
      setHistory(res.data.medical_history);
      setEditing(false);
      onSaved?.();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Error al guardar.');
    } finally {
      setSaving(false);
    }
  };

  // ---- Render estados ----
  if (loading) {
    return (
      <div className="flex items-center justify-center py-6 text-gray-400 text-sm">
        <div className="animate-spin mr-2">◌</div> Cargando anamnesis...
      </div>
    );
  }

  if (error) {
    return <p className="text-red-500 text-xs py-2 px-3">{error}</p>;
  }

  if (!history || Object.keys(history).filter(k => !k.startsWith('anamnesis_')).length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center gap-2 ${compact ? 'py-4' : 'py-8'} text-gray-400`}>
        <HeartPulse size={compact ? 20 : 32} className="opacity-40" />
        <p className="text-xs text-center">Este paciente aún no<br/>completó la anamnesis.</p>
      </div>
    );
  }

  // ---- Render edición ----
  if (editing) {
    return (
      <div className="space-y-3 p-3">
        {ANAMNESIS_FIELDS.map(f => (
          <div key={f.key}>
            <label className="block text-xs font-medium text-gray-600 mb-1 flex items-center gap-1">
              <span className={alertClass(f.alertLevel, isAlertValue(history?.[f.key] ?? editData[f.key]))}>{f.icon}</span>
              {f.label}
            </label>
            <input
              className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              defaultValue={history?.[f.key] ?? ''}
              onChange={e => setEditData(prev => ({ ...prev, [f.key]: e.target.value }))}
            />
          </div>
        ))}
        {error && <p className="text-red-500 text-xs">{error}</p>}
        <div className="flex gap-2 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1 px-3 py-1.5 bg-primary text-white text-xs rounded hover:bg-primary-dark disabled:opacity-50"
          >
            <Save size={12} /> {saving ? 'Guardando...' : 'Guardar'}
          </button>
          <button
            onClick={() => { setEditing(false); setError(null); }}
            className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-600 text-xs rounded hover:bg-gray-200"
          >
            <X size={12} /> Cancelar
          </button>
        </div>
      </div>
    );
  }

  // ---- Render visualización ----
  // En modo compacto, mostramos solo lo que tiene valor (incluyendo "No")
  // Pero agrupamos smoker_amount con is_smoker
  const fieldsWithValues = ANAMNESIS_FIELDS.filter(f => {
    const val = history[f.key];
    if (f.key === 'smoker_amount') return false; // Se maneja dentro de is_smoker
    return val !== undefined && val !== null && val !== '';
  });

  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-3'}>
      {/* Header con botón de editar (Solo en modo expandido) */}
      {canEdit && !compact && (
        <div className="flex justify-end">
          <button
            onClick={() => { setEditing(true); setEditData({}); }}
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Edit2 size={12} /> Editar
          </button>
        </div>
      )}

      {/* Campos */}
      {fieldsWithValues.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-2">Sin datos cargados.</p>
      ) : (
        fieldsWithValues.map(f => {
          let val = history[f.key]!;
          const hasAlert = isAlertValue(val);
          
          // Especial: Combinar fumador
          if (f.key === 'is_smoker' && history.smoker_amount) {
            val = `${val} (${history.smoker_amount})`;
          }

          return (
            <div
              key={f.key}
              className={`flex items-start gap-2 ${compact ? 'text-xs' : 'text-sm'} ${hasAlert && f.alertLevel !== 'none' ? 'bg-red-50 border border-red-100 rounded p-1.5' : ''}`}
            >
              <span className={`mt-0.5 flex-shrink-0 ${alertClass(f.alertLevel, hasAlert)}`}>{f.icon}</span>
              <div className="min-w-0 flex-1">
                <p className={`font-medium text-gray-600 flex items-center gap-1 ${compact ? 'text-[10px]' : 'text-xs'} leading-none mb-0.5`}>
                  {f.label}
                  {hasAlert && f.alertLevel !== 'none' && <span className={badgeClass(f.alertLevel, hasAlert)} />}
                </p>
                <p className={`text-gray-800 break-words leading-tight ${compact ? 'text-[11px]' : ''}`}>
                  {val === 'No' || val === 'no' ? <span className="text-gray-400">No</span> : val}
                </p>
              </div>
            </div>
          );
        })
      )}

      {/* Fecha de completado */}
      {history.anamnesis_completed_at && (
        <div className={`flex items-center gap-1 text-gray-400 ${compact ? 'text-[10px]' : 'text-xs'} pt-1 border-t`}>
          <CheckCircle size={10} className="text-green-500" />
          Completado:{' '}
          {new Date(history.anamnesis_completed_at).toLocaleDateString('es-AR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
          })}
          {history.anamnesis_completed_via && ` vía ${history.anamnesis_completed_via}`}
        </div>
      )}

      {/* Botón editar en modo compact (al final) */}
      {canEdit && compact && (
        <button
          id="btn-edit-anamnesis-compact"
          onClick={() => { setEditing(true); setEditData({}); }}
          className="w-full flex items-center justify-center gap-1 py-1 px-2 border border-primary text-primary rounded text-[10px] font-bold hover:bg-primary/5 transition-colors mt-2"
        >
          <Edit2 size={10} /> {t('common.edit')} {t('chats.anamnesis')}
        </button>
      )}
    </div>
  );
}
