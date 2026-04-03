import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BarChart3, FileText, Scale, Loader2, AlertTriangle } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import PageHeader from '../components/PageHeader';
import GlassCard from '../components/GlassCard';
import FinancialDashboard from '../components/finance/FinancialDashboard';
import LiquidationManager from '../components/finance/LiquidationManager';
import ReconciliationView from '../components/finance/ReconciliationView';
import type { DashboardData } from '../types/finance';

function getDefaultPeriod() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0],
  };
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
  }).format(amount);
}

type TabKey = 'dashboard' | 'liquidaciones' | 'conciliacion';

export default function FinancialCommandCenterView() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get('tab') as TabKey) || 'dashboard';

  const switchTab = (tab: TabKey) => {
    setSearchParams((prev) => {
      prev.set('tab', tab);
      return prev;
    }, { replace: true });
  };

  const defaultPeriod = getDefaultPeriod();
  const [periodStart, setPeriodStart] = useState(defaultPeriod.start);
  const [periodEnd, setPeriodEnd] = useState(defaultPeriod.end);

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        period_start: periodStart,
        period_end: periodEnd,
      });
      const res = await api.get(`/admin/financial-dashboard?${params}`);
      setDashboardData(res.data);
    } catch (err: any) {
      console.error('Error fetching financial dashboard:', err);
      setError(err.response?.data?.detail || 'Error al cargar datos financieros');
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd]);

  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchDashboardData();
    }
  }, [activeTab, fetchDashboardData]);

  const tabs: { key: TabKey; label: string; icon: JSX.Element }[] = [
    { key: 'dashboard', label: t('finance.tab_dashboard'), icon: <BarChart3 size={16} /> },
    { key: 'liquidaciones', label: t('finance.tab_liquidations'), icon: <FileText size={16} /> },
    { key: 'conciliacion', label: t('finance.tab_reconciliation'), icon: <Scale size={16} /> },
  ];

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-4 sm:p-6 shrink-0 bg-white/[0.02] backdrop-blur-sm border-b border-white/[0.06]">
        <PageHeader
          title={t('finance.title')}
          subtitle={t('finance.subtitle')}
          icon={<BarChart3 size={22} />}
        />

        {/* Period Selector */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-white/40">{t('common.since')}</label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500/40"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-white/40">{t('common.until')}</label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500/40"
            />
          </div>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 mt-4 border-b border-white/[0.06] overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => switchTab(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors relative whitespace-nowrap ${
                activeTab === tab.key
                  ? 'text-white'
                  : 'text-white/40 hover:text-white/60'
              }`}
            >
              {tab.icon}
              {tab.label}
              {activeTab === tab.key && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white rounded-full" />
              )}
            </button>
          ))}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 min-h-0 overflow-y-auto p-4 lg:p-6 scroll-smooth">
        {error && activeTab === 'dashboard' && (
          <GlassCard>
            <div className="p-6 text-center">
              <AlertTriangle size={32} className="text-amber-400 mx-auto mb-3" />
              <p className="text-white/60 mb-4">{error}</p>
              <button
                onClick={fetchDashboardData}
                className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors text-sm font-medium"
              >
                {t('finance.retry')}
              </button>
            </div>
          </GlassCard>
        )}

        {activeTab === 'dashboard' && (
          <FinancialDashboard
            data={dashboardData}
            loading={loading}
            formatCurrency={formatCurrency}
          />
        )}

        {activeTab === 'liquidaciones' && (
          <LiquidationManager
            periodStart={periodStart}
            periodEnd={periodEnd}
            formatCurrency={formatCurrency}
          />
        )}

        {activeTab === 'conciliacion' && (
          <ReconciliationView
            periodStart={periodStart}
            periodEnd={periodEnd}
            formatCurrency={formatCurrency}
          />
        )}
      </main>
    </div>
  );
}
