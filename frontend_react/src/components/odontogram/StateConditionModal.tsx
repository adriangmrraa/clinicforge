import { useState } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { OdontogramState } from '../../constants/odontogramStates';
import { ChevronLeft, Check } from 'lucide-react';

export type DentalCondition = 'bueno' | 'malo' | 'indefinido';

interface StateConditionModalProps {
  isOpen: boolean;
  selectedState: OdontogramState | null;
  onBack: () => void;
  onApply: (condition: DentalCondition, color: string) => void;
}

const CONDITION_COLORS: Record<DentalCondition, string> = {
  bueno: 'bg-green-500/20 border-green-500/50 text-green-400',
  malo: 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400',
  indefinido: 'bg-gray-500/20 border-gray-500/50 text-gray-400',
};

const DENTAL_PRESETS = [
  '#ef4444', // red
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#14b8a6', // teal
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#6b7280', // gray
  '#f0f0f0', // white
];

export default function StateConditionModal({ 
  isOpen, 
  selectedState, 
  onBack, 
  onApply 
}: StateConditionModalProps) {
  const { t } = useTranslation();
  const [condition, setCondition] = useState<DentalCondition | null>(null);
  const [color, setColor] = useState<string>(selectedState?.defaultColor || '#f0f0f0');

  const handleApply = () => {
    if (condition) {
      onApply(condition, color);
    }
  };

  const handleBack = () => {
    setCondition(null);
    setColor(selectedState?.defaultColor || '#f0f0f0');
    onBack();
  };

  if (!isOpen || !selectedState) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleBack}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-gray-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-[fadeIn_0.2s_ease-out]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <button
            onClick={handleBack}
            className="flex items-center gap-1 p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <ChevronLeft className="w-5 h-5 text-white/60" />
            <span className="text-white/60">{t('odontogram.modal.back', 'Volver')}</span>
          </button>
          <h2 className="text-lg font-semibold text-white">
            {t('odontogram.modal.condition', 'Condición')}
          </h2>
          <div className="w-20" /> {/* Spacer for balance */}
        </div>

        {/* Selected State Preview */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl">
            <span 
              className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold"
              style={{ backgroundColor: color + '20', color: color }}
            >
              {selectedState.symbol}
            </span>
            <div>
              <p className="text-white font-medium">
                {t(selectedState.labelKey, selectedState.id)}
              </p>
              <p className="text-white/40 text-sm">
                {t(`odontogram.categories.${selectedState.category}`, selectedState.category)}
              </p>
            </div>
          </div>
        </div>

        {/* Condition Selection */}
        <div className="p-4">
          <h3 className="text-sm font-medium text-white/60 mb-3">
            {t('odontogram.modal.selectCondition', 'Seleccionar condición')}
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {(Object.keys(CONDITION_COLORS) as DentalCondition[]).map((cond) => (
              <button
                key={cond}
                onClick={() => setCondition(cond)}
                className={`p-4 rounded-xl border transition-all duration-200 ${
                  condition === cond
                    ? CONDITION_COLORS[cond]
                    : 'bg-white/5 border-white/10 hover:bg-white/10'
                }`}
              >
                <span className="text-white">{t(`odontogram.conditions.${cond}`, cond)}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Color Picker */}
        <div className="p-4 border-t border-white/10">
          <h3 className="text-sm font-medium text-white/60 mb-3">
            {t('odontogram.modal.selectColor', 'Seleccionar color')}
          </h3>
          
          {/* Preview */}
          <div className="flex items-center gap-3 mb-4">
            <div 
              className="w-12 h-12 rounded-xl border border-white/20"
              style={{ backgroundColor: color }}
            />
            <input
              type="text"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white font-mono focus:outline-none focus:border-blue-500/50"
              placeholder="#000000"
            />
          </div>

          {/* Presets */}
          <div className="grid grid-cols-5 gap-2">
            {DENTAL_PRESETS.map((preset) => (
              <button
                key={preset}
                onClick={() => setColor(preset)}
                className={`w-full aspect-square rounded-lg border-2 transition-all duration-200 ${
                  color === preset
                    ? 'border-white scale-110'
                    : 'border-transparent hover:border-white/30'
                }`}
                style={{ backgroundColor: preset }}
              />
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleApply}
            disabled={!condition}
            className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all duration-200 ${
              condition
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-white/10 text-white/40 cursor-not-allowed'
            }`}
          >
            <Check className="w-5 h-5" />
            {t('odontogram.modal.apply', 'Aplicar')}
          </button>
        </div>
      </div>
    </div>
  );
}
