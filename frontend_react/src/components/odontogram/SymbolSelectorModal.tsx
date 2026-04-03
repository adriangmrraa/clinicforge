import { useState, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { ODONTOGRAM_STATES, OdontogramState, OdontogramCategory } from '../../constants/odontogramStates';
import { Search, X, Check, ChevronLeft } from 'lucide-react';

interface SymbolSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (state: OdontogramState) => void;
  currentStateId?: string;
  surfaceName?: string;
}

const CATEGORY_BADGE: Record<OdontogramCategory, string> = {
  preexistente: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  lesion: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function normalizeAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export default function SymbolSelectorModal({ isOpen, onClose, onSelect, currentStateId, surfaceName }: SymbolSelectorModalProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  // Focus search on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => searchRef.current?.focus(), 300);
    } else {
      setSearch('');
    }
  }, [isOpen]);

  const filteredStates = useMemo(() => {
    const states = ODONTOGRAM_STATES.filter(s => s.id !== 'healthy');
    if (!search.trim()) return states;
    const q = normalizeAccents(search.toLowerCase());
    return states.filter(state => {
      const label = normalizeAccents(t(state.labelKey, state.id).toLowerCase());
      return label.includes(q) || state.id.includes(q) || state.symbol.toLowerCase().includes(q);
    });
  }, [search, t]);

  const grouped = useMemo(() => ({
    preexistente: filteredStates.filter(s => s.category === 'preexistente'),
    lesion: filteredStates.filter(s => s.category === 'lesion'),
  }), [filteredStates]);

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
          {category === 'preexistente' ? 'PREEXISTENTE' : 'LESIÓN'}
        </span>
        <div className="grid grid-cols-3 sm:grid-cols-3 gap-1.5">
          {states.map(state => {
            const isActive = currentStateId === state.id;
            return (
              <button
                key={state.id}
                onClick={() => handleSelect(state)}
                className={`relative flex flex-col items-center gap-1 p-2.5 rounded-xl border
                  transition-all duration-150 touch-manipulation active:scale-95 ${
                  isActive
                    ? 'bg-blue-500/20 border-blue-500/50 ring-1 ring-blue-500/30'
                    : 'bg-white/[0.03] border-white/[0.08] active:bg-white/[0.08]'
                }`}
              >
                {isActive && (
                  <div className="absolute top-1.5 right-1.5">
                    <Check className="w-3 h-3 text-blue-400" />
                  </div>
                )}
                <span
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold"
                  style={{ backgroundColor: state.defaultColor + '25', color: state.defaultColor }}
                >
                  {state.symbol}
                </span>
                <span className="text-[10px] text-white/70 text-center leading-tight line-clamp-2">
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
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center">
      {/* Backdrop — click to close */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal — bottom sheet on mobile, centered on desktop */}
      <div className="relative w-full sm:max-w-md sm:mx-4
        bg-[#0d1117] border border-white/10
        rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden
        animate-[slideUp_0.2s_ease-out]
        max-h-[85vh] sm:max-h-[75vh] flex flex-col">

        {/* Drag handle — mobile only */}
        <div className="flex justify-center pt-2 pb-0.5 sm:hidden">
          <div className="w-10 h-1 bg-white/20 rounded-full" />
        </div>

        {/* Sticky header with close button + search */}
        <div className="shrink-0 border-b border-white/[0.06]">
          {/* Title row */}
          <div className="flex items-center justify-between px-4 pt-2 sm:pt-3 pb-2">
            <div className="flex items-center gap-2 min-w-0">
              <button
                onClick={handleClose}
                className="p-1.5 -ml-1.5 rounded-lg active:bg-white/10 transition-colors touch-manipulation sm:hidden"
              >
                <ChevronLeft className="w-5 h-5 text-white/50" />
              </button>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-white truncate">
                  {t('odontogram.modal.selectState', 'Seleccionar estado')}
                </h2>
                {surfaceName && (
                  <p className="text-[10px] text-blue-400/70 mt-0.5">{surfaceName}</p>
                )}
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-2 -mr-1 rounded-xl hover:bg-white/10 active:bg-white/10 transition-colors touch-manipulation"
            >
              <X className="w-5 h-5 text-white/50" />
            </button>
          </div>

          {/* Search — always visible */}
          <div className="px-4 pb-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
              <input
                ref={searchRef}
                type="text"
                placeholder={t('odontogram.modal.searchPlaceholder', 'Buscar símbolo...')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-white placeholder-white/30 focus:outline-none focus:border-blue-500/40 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* States Grid — scrollable */}
        <div className="flex-1 overflow-y-auto px-4 pt-3 pb-4 min-h-0 overscroll-contain">
          {renderCategory('preexistente', grouped.preexistente)}
          {renderCategory('lesion', grouped.lesion)}

          {filteredStates.length === 0 && (
            <p className="text-center text-white/30 py-8 text-sm">
              {t('odontogram.modal.noResults', 'No se encontraron estados')}
            </p>
          )}
        </div>

        {/* Reset to healthy + close — safe area */}
        <div className="shrink-0 px-4 pt-2 pb-3 border-t border-white/[0.06] flex gap-2"
          style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}>
          <button
            onClick={handleClose}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-white/[0.04] text-white/50 border border-white/[0.08] active:bg-white/[0.08] transition-all touch-manipulation"
          >
            {t('odontogram.modal.cancel', 'Cancelar')}
          </button>
          <button
            onClick={() => handleSelect(ODONTOGRAM_STATES[0])}
            className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all touch-manipulation ${
              currentStateId === 'healthy'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-white/[0.04] text-white/60 border border-white/[0.08] active:bg-white/[0.08]'
            }`}
          >
            ○ {t('odontogram.states.healthy', 'Sano')}
          </button>
        </div>
      </div>
    </div>
  );
}
