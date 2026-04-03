import { useState, useMemo } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { ODONTOGRAM_STATES, OdontogramState, OdontogramCategory } from '../../constants/odontogramStates';
import { Search, X, Check } from 'lucide-react';

interface SymbolSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (state: OdontogramState) => void;
  currentStateId?: string;
}

const CATEGORY_BADGE: Record<OdontogramCategory, string> = {
  preexistente: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  lesion: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const CATEGORY_LABEL: Record<OdontogramCategory, string> = {
  preexistente: 'PREEXISTENTE',
  lesion: 'LESION',
};

function normalizeAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export default function SymbolSelectorModal({ isOpen, onClose, onSelect, currentStateId }: SymbolSelectorModalProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');

  const filteredStates = useMemo(() => {
    const states = ODONTOGRAM_STATES.filter(s => s.id !== 'healthy');
    if (!search.trim()) return states;
    const q = normalizeAccents(search.toLowerCase());
    return states.filter(state => {
      const label = normalizeAccents(t(state.labelKey, state.id).toLowerCase());
      return label.includes(q) || state.id.includes(q) || state.symbol.toLowerCase().includes(q);
    });
  }, [search, t]);

  const grouped = useMemo(() => {
    const preexistente = filteredStates.filter(s => s.category === 'preexistente');
    const lesion = filteredStates.filter(s => s.category === 'lesion');
    return { preexistente, lesion };
  }, [filteredStates]);

  const handleSelect = (state: OdontogramState) => {
    setSearch('');
    onSelect(state);
  };

  const handleClose = () => {
    setSearch('');
    onClose();
  };

  if (!isOpen) return null;

  const renderCategory = (category: OdontogramCategory, states: OdontogramState[]) => {
    if (states.length === 0) return null;
    return (
      <div key={category} className="mb-5">
        <span className={`inline-block px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border mb-3 ${CATEGORY_BADGE[category]}`}>
          {CATEGORY_LABEL[category]}
        </span>
        <div className="grid grid-cols-2 gap-2">
          {states.map(state => {
            const isActive = currentStateId === state.id;
            return (
              <button
                key={state.id}
                onClick={() => handleSelect(state)}
                className={`relative flex flex-col items-center gap-1.5 p-3 rounded-xl border transition-all duration-200 ${
                  isActive
                    ? 'bg-blue-500/20 border-blue-500/50 ring-1 ring-blue-500/30'
                    : 'bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.06] hover:border-white/[0.15]'
                }`}
              >
                {isActive && (
                  <div className="absolute top-2 right-2">
                    <Check className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                )}
                <span
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-base font-bold"
                  style={{ backgroundColor: state.defaultColor + '25', color: state.defaultColor }}
                >
                  {state.symbol}
                </span>
                <span className="text-xs text-white/70 text-center leading-tight">
                  {t(state.labelKey, state.id)}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />

      <div className="relative w-full max-w-lg sm:mx-4 bg-[#0d1117] border border-white/10 rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden animate-[slideUp_0.25s_ease-out] max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-white/[0.06] shrink-0">
          <h2 className="text-base font-semibold text-white">
            {t('odontogram.modal.selectState', 'Seleccionar estado')}
          </h2>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors">
            <X className="w-5 h-5 text-white/50" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-3 shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="text"
              placeholder={t('odontogram.modal.searchPlaceholder', 'Buscar símbolo...')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-white placeholder-white/30 focus:outline-none focus:border-blue-500/40 transition-colors"
              autoFocus
            />
          </div>
        </div>

        {/* States Grid — scrollable */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
          {renderCategory('preexistente', grouped.preexistente)}
          {renderCategory('lesion', grouped.lesion)}

          {filteredStates.length === 0 && (
            <p className="text-center text-white/30 py-8 text-sm">
              {t('odontogram.modal.noResults', 'No se encontraron estados')}
            </p>
          )}
        </div>

        {/* Sano button at bottom */}
        <div className="px-4 py-3 border-t border-white/[0.06] shrink-0">
          <button
            onClick={() => handleSelect(ODONTOGRAM_STATES[0])}
            className={`w-full py-2.5 rounded-xl text-sm font-medium transition-all ${
              currentStateId === 'healthy'
                ? 'bg-white/10 text-white border border-white/20'
                : 'bg-white/[0.04] text-white/60 border border-white/[0.08] hover:bg-white/[0.08]'
            }`}
          >
            {t('odontogram.states.healthy', 'Sano')} (reset)
          </button>
        </div>
      </div>
    </div>
  );
}
