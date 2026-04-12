import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Zap, Filter } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import PlaybookCard from '../components/playbooks/PlaybookCard';
import PlaybookConfigModal from '../components/playbooks/PlaybookConfigModal';

interface Playbook {
  id: number;
  name: string;
  description?: string;
  icon?: string;
  category: string;
  trigger_type: string;
  is_active: boolean;
  is_system: boolean;
  stats_cache?: any;
  step_count?: number;
  active_executions?: number;
}

const CATEGORIES = [
  { value: 'all', label: 'Todos' },
  { value: 'retention', label: 'Retención' },
  { value: 'revenue', label: 'Ingresos' },
  { value: 'reputation', label: 'Reputación' },
  { value: 'clinical', label: 'Clínico' },
  { value: 'recovery', label: 'Recuperación' },
  { value: 'custom', label: 'Personalizado' },
];

export default function PlaybooksView() {
  const { t } = useTranslation();
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [configModal, setConfigModal] = useState<{ open: boolean; playbookId: number | null }>({ open: false, playbookId: null });

  const loadPlaybooks = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/playbooks');
      setPlaybooks(data.playbooks || []);
    } catch (e) {
      console.error('Error loading playbooks:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlaybooks();
  }, [loadPlaybooks]);

  const handleToggle = async (id: number) => {
    // Optimistic update
    setPlaybooks(prev => prev.map(p => p.id === id ? { ...p, is_active: !p.is_active } : p));
    try {
      const { data } = await api.patch(`/admin/playbooks/${id}/toggle`);
      // Refresh full list to get accurate state
      await loadPlaybooks();
    } catch (e: any) {
      console.error('Error toggling playbook:', e);
      // Rollback optimistic update
      setPlaybooks(prev => prev.map(p => p.id === id ? { ...p, is_active: !p.is_active } : p));
    }
  };

  const handleConfigure = (id: number) => {
    setConfigModal({ open: true, playbookId: id });
  };

  const handleStats = async (id: number) => {
    // Refresh stats for this playbook
    try {
      await api.get(`/admin/playbooks/${id}/stats`);
      await loadPlaybooks();
    } catch (e) {
      console.error('Error loading stats:', e);
    }
  };

  const filteredPlaybooks = categoryFilter === 'all'
    ? playbooks
    : playbooks.filter(p => p.category === categoryFilter);

  return (
    <div className="h-full overflow-y-auto bg-[#06060e]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Zap className="text-amber-400" size={24} />
              {t('playbooks.title')}
            </h1>
            <p className="text-sm text-white/50 mt-1">{t('playbooks.subtitle')}</p>
          </div>
          <button
            onClick={() => setConfigModal({ open: true, playbookId: null })}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 transition-colors shrink-0"
          >
            <Plus size={18} />
            {t('playbooks.create_new')}
          </button>
        </div>

        {/* Category filter tabs */}
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {CATEGORIES.map(cat => (
            <button
              key={cat.value}
              onClick={() => setCategoryFilter(cat.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors
                ${categoryFilter === cat.value
                  ? 'bg-white/[0.10] text-white border border-white/[0.12]'
                  : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
                }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Playbook grid */}
        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-5 animate-pulse h-48" />
            ))}
          </div>
        ) : filteredPlaybooks.length === 0 ? (
          <div className="text-center py-16">
            <Zap size={48} className="mx-auto text-white/10 mb-4" />
            <p className="text-white/40 text-lg font-medium">{t('playbooks.empty_title')}</p>
            <p className="text-white/30 text-sm mt-1">{t('playbooks.empty_subtitle')}</p>
            <button
              onClick={() => setConfigModal({ open: true, playbookId: null })}
              className="mt-4 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium inline-flex items-center gap-2"
            >
              <Plus size={16} />
              {t('playbooks.create_first')}
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredPlaybooks.map(pb => (
              <PlaybookCard
                key={pb.id}
                playbook={pb}
                onConfigure={handleConfigure}
                onToggle={handleToggle}
                onStats={handleStats}
              />
            ))}
          </div>
        )}
      </div>

      {/* Config Modal */}
      {configModal.open && (
        <PlaybookConfigModal
          playbookId={configModal.playbookId}
          onClose={() => setConfigModal({ open: false, playbookId: null })}
          onSaved={() => {
            setConfigModal({ open: false, playbookId: null });
            loadPlaybooks();
          }}
        />
      )}
    </div>
  );
}
