import { useState, useEffect } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Save, RotateCcw, AlertCircle } from 'lucide-react';
import api from '../api/axios';

interface ToothState {
  id: number;
  state: 'healthy' | 'caries' | 'restoration' | 'extraction' | 'treatment_planned' | 'crown' | 'implant' | 'missing';
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

const TOOTH_COUNT = 32;
const UPPER_TEETH = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
const LOWER_TEETH = [17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32];

const STATE_COLORS: Record<string, string> = {
  healthy: 'bg-green-100 border-green-300 text-green-800',
  caries: 'bg-red-100 border-red-300 text-red-800',
  restoration: 'bg-blue-100 border-blue-300 text-blue-800',
  extraction: 'bg-gray-100 border-gray-300 text-gray-800',
  treatment_planned: 'bg-yellow-100 border-yellow-300 text-yellow-800',
  crown: 'bg-purple-100 border-purple-300 text-purple-800',
  implant: 'bg-indigo-100 border-indigo-300 text-indigo-800',
  missing: 'bg-gray-200 border-gray-400 text-gray-600'
};

const STATE_ICONS: Record<string, string> = {
  healthy: '✓',
  caries: '🦷',
  restoration: '🔧',
  extraction: '❌',
  treatment_planned: '📅',
  crown: '👑',
  implant: '⚙️',
  missing: '○'
};

export default function Odontogram({ patientId, recordId, initialData, onSave, readOnly = false }: OdontogramProps) {
  const { t } = useTranslation();
  const [teeth, setTeeth] = useState<ToothState[]>([]);
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [selectedState, setSelectedState] = useState<string>('healthy');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Estados disponibles
  const availableStates = [
    { id: 'healthy', label: t('odontogram.states.healthy') },
    { id: 'caries', label: t('odontogram.states.caries') },
    { id: 'restoration', label: t('odontogram.states.restoration') },
    { id: 'extraction', label: t('odontogram.states.extraction') },
    { id: 'treatment_planned', label: t('odontogram.states.treatment_planned') },
    { id: 'crown', label: t('odontogram.states.crown') },
    { id: 'implant', label: t('odontogram.states.implant') },
    { id: 'missing', label: t('odontogram.states.missing') }
  ];

  // Inicializar dientes
  useEffect(() => {
    if (initialData && initialData.teeth) {
      setTeeth(initialData.teeth);
    } else {
      // Crear array inicial de dientes
      const initialTeeth: ToothState[] = [];
      for (let i = 1; i <= TOOTH_COUNT; i++) {
        initialTeeth.push({
          id: i,
          state: 'healthy',
          surfaces: {},
          notes: ''
        });
      }
      setTeeth(initialTeeth);
    }
  }, [initialData]);

  const handleToothClick = (toothId: number) => {
    if (readOnly) return;
    setSelectedTooth(toothId);
    const tooth = teeth.find(t => t.id === toothId);
    if (tooth) {
      setSelectedState(tooth.state);
    }
  };

  const handleStateChange = (state: string) => {
    if (readOnly || !selectedTooth) return;
    
    setSelectedState(state);
    setTeeth(prev => prev.map(tooth => 
      tooth.id === selectedTooth 
        ? { ...tooth, state: state as ToothState['state'] }
        : tooth
    ));
  };

  const handleSave = async () => {
    if (readOnly) return;
    
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const odontogramData = {
        teeth,
        last_updated: new Date().toISOString(),
        version: '1.0'
      };

      if (recordId) {
        // Actualizar odontograma existente
        await api.put(`/admin/patients/${patientId}/records/${recordId}/odontogram`, {
          odontogram_data: odontogramData
        });
      } else {
        // Crear nuevo registro clínico con odontograma
        await api.post(`/admin/patients/${patientId}/records`, {
          content: t('odontogram.automatic_note'),
          odontogram_data: odontogramData
        });
      }

      setSuccess(t('odontogram.save_success'));
      if (onSave) {
        onSave(odontogramData);
      }

      // Limpiar mensaje después de 3 segundos
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
    
    const resetTeeth: ToothState[] = [];
    for (let i = 1; i <= TOOTH_COUNT; i++) {
      resetTeeth.push({
        id: i,
        state: 'healthy',
        surfaces: {},
        notes: ''
      });
    }
    setTeeth(resetTeeth);
    setSelectedTooth(null);
    setSelectedState('healthy');
  };

  const getToothDisplay = (toothId: number) => {
    const tooth = teeth.find(t => t.id === toothId);
    if (!tooth) return '1';
    
    // Sistema FDI (Fédération Dentaire Internationale)
    if (toothId <= 16) {
      // Superior derecho: 11-18
      return toothId;
    } else {
      // Inferior izquierdo: 21-28, 31-38
      if (toothId <= 24) {
        return toothId - 4;
      } else {
        return toothId - 8;
      }
    }
  };

  const renderTooth = (toothId: number) => {
    const tooth = teeth.find(t => t.id === toothId);
    const isSelected = selectedTooth === toothId;
    const stateClass = tooth ? STATE_COLORS[tooth.state] || STATE_COLORS.healthy : STATE_COLORS.healthy;
    const stateIcon = tooth ? STATE_ICONS[tooth.state] || STATE_ICONS.healthy : STATE_ICONS.healthy;

    return (
      <button
        key={toothId}
        onClick={() => handleToothClick(toothId)}
        disabled={readOnly}
        className={`
          relative w-12 h-12 rounded-lg border-2 flex flex-col items-center justify-center
          transition-all duration-200 ${stateClass}
          ${isSelected ? 'ring-2 ring-primary ring-offset-1 scale-105' : ''}
          ${readOnly ? 'cursor-default' : 'cursor-pointer hover:scale-105 hover:shadow-md'}
        `}
      >
        <div className="text-xs font-semibold">{getToothDisplay(toothId)}</div>
        <div className="text-lg">{stateIcon}</div>
        {tooth?.state !== 'healthy' && (
          <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500"></div>
        )}
      </button>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-800">{t('odontogram.title')}</h3>
          <p className="text-sm text-gray-500">{t('odontogram.subtitle')}</p>
        </div>
        
        {!readOnly && (
          <div className="flex gap-2">
            <button
              onClick={handleReset}
              disabled={saving}
              className="flex items-center gap-2 px-3 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw size={16} />
              {t('odontogram.reset')}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-white bg-primary rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save size={16} />
              {saving ? t('odontogram.saving') : t('odontogram.save')}
            </button>
          </div>
        )}
      </div>

      {/* Mensajes de estado */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg flex items-center gap-2">
          <AlertCircle size={16} />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg">
          <span className="text-sm">{success}</span>
        </div>
      )}

      {/* Selector de estado */}
      {selectedTooth && !readOnly && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded bg-blue-100 border border-blue-300 flex items-center justify-center">
              <span className="font-semibold">{getToothDisplay(selectedTooth)}</span>
            </div>
            <span className="text-sm font-medium text-gray-700">
              {t('odontogram.selecting_tooth')} {getToothDisplay(selectedTooth)}
            </span>
          </div>
          
          <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
            {availableStates.map(state => (
              <button
                key={state.id}
                onClick={() => handleStateChange(state.id)}
                className={`
                  px-3 py-2 text-sm rounded-lg border transition-colors
                  ${selectedState === state.id 
                    ? `${STATE_COLORS[state.id]} border-2 border-primary` 
                    : 'bg-white border-gray-200 hover:bg-gray-50'
                  }
                `}
              >
                <div className="flex flex-col items-center">
                  <span className="text-lg mb-1">{STATE_ICONS[state.id]}</span>
                  <span className="text-xs">{state.label}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Odontograma visual */}
      <div className="mb-8">
        {/* Arco superior */}
        <div className="mb-2">
          <div className="text-center text-sm font-medium text-gray-600 mb-2">{t('odontogram.upper_arch')}</div>
          <div className="flex flex-wrap justify-center gap-2">
            {UPPER_TEETH.map(toothId => renderTooth(toothId))}
          </div>
        </div>

        {/* Separador */}
        <div className="h-px bg-gray-200 my-4"></div>

        {/* Arco inferior */}
        <div className="mt-2">
          <div className="text-center text-sm font-medium text-gray-600 mb-2">{t('odontogram.lower_arch')}</div>
          <div className="flex flex-wrap justify-center gap-2">
            {LOWER_TEETH.map(toothId => renderTooth(toothId))}
          </div>
        </div>
      </div>

      {/* Leyenda */}
      <div className="border-t pt-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">{t('odontogram.legend')}</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {availableStates.map(state => (
            <div key={state.id} className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded ${STATE_COLORS[state.id]} flex items-center justify-center`}>
                {STATE_ICONS[state.id]}
              </div>
              <span className="text-xs text-gray-600">{state.label}</span>
            </div>
          ))}
        </div>
      </div>

      {readOnly && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-700 rounded-lg text-sm">
          {t('odontogram.read_only_notice')}
        </div>
      )}
    </div>
  );
}