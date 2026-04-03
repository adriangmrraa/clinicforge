import { useState, useMemo } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { ODONTOGRAM_STATES, OdontogramState, OdontogramCategory } from '../../constants/odontogramStates';
import { Search, X, ChevronRight } from 'lucide-react';

interface SymbolSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (state: OdontogramState) => void;
  onNext?: () => void;
}

const CATEGORY_COLORS: Record<OdontogramCategory, string> = {
  preexisting: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  lesion: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function normalizeAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export default function SymbolSelectorModal({ isOpen, onClose, onSelect, onNext }: SymbolSelectorModalProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [selectedState, setSelectedState] = useState<OdontogramState | null>(null);

  const filteredStates = useMemo(() => {
    if (!search.trim()) return ODONTOGRAM_STATES;
    
    const normalizedSearch = normalizeAccents(search.toLowerCase());
    
    return ODONTOGRAM_STATES.filter(state => {
      const label = t(state.labelKey).toLowerCase();
      const normalizedLabel = normalizeAccents(label);
      return normalizedLabel.includes(normalizedSearch) || 
             state.id.toLowerCase().includes(normalizedSearch);
    });
  }, [search, t]);

  const groupedStates = useMemo(() => {
    const groups: Record<OdontogramCategory, OdontogramState[]> = {
      preexisting: [],
      lesion: [],
    };
    
    filteredStates.forEach(state => {
      groups[state.category].push(state);
    });
    
    return groups;
  }, [filteredStates]);

  const handleSelect = (state: OdontogramState) => {
    setSelectedState(state);
    onSelect(state);
  };

  const handleNext = () => {
    if (selectedState && onNext) {
      onNext();
    }
  };

  const handleClose = () => {
    setSearch('');
    setSelectedState(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-gray-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-[fadeIn_0.2s_ease-out]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">
            {t('odontogram.modal.selectState', 'Seleccionar Estado')}
          </h2>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5 text-white/60" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-white/10">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder={t('odontogram.modal.searchPlaceholder', 'Buscar estado...')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/40 focus:outline-none focus:border-blue-500/50 transition-colors"
              autoFocus
            />
          </div>
        </div>

        {/* States Grid */}
        <div className="max-h-[60vh] overflow-y-auto p-4">
          {Object.entries(groupedStates).map(([category, states]) => (
            states.length > 0 && (
              <div key={category} className="mb-4">
                <h3 className={`inline-block px-3 py-1 rounded-full text-xs font-medium border ${CATEGORY_COLORS[category as OdontogramCategory]}`}>
                  {t(`odontogram.categories.${category}`, category === 'preexistente' ? 'Preexistente' : 'Lesión')}
                </h3>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {states.map(state => (
                    <button
                      key={state.id}
                      onClick={() => handleSelect(state)}
                      className={`flex items-center gap-2 p-3 rounded-xl border transition-all duration-200 ${
                        selectedState?.id === state.id
                          ? 'bg-blue-500/20 border-blue-500/50'
                          : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                      }`}
                    >
                      <span 
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
                        style={{ backgroundColor: state.defaultColor + '20', color: state.defaultColor }}
                      >
                        {state.symbol}
                      </span>
                      <span className="text-sm text-white/80 truncate">
                        {t(state.labelKey, state.id)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )
          ))}
          
          {filteredStates.length === 0 && (
            <p className="text-center text-white/40 py-8">
              {t('odontogram.modal.noResults', 'No se encontraron estados')}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleNext}
            disabled={!selectedState}
            className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all duration-200 ${
              selectedState
                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                : 'bg-white/10 text-white/40 cursor-not-allowed'
            }`}
          >
            {t('odontogram.modal.next', 'Siguiente')}
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
