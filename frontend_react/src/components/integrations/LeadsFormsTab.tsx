import React, { useState, useEffect } from 'react';
import { Copy, CheckCircle2, ExternalLink, AlertCircle, Settings, Link, MessageSquare, Users } from 'lucide-react';
import api from '../../api/axios';
import { useTranslation } from '../../context/LanguageContext';

interface WebhookConfig {
  webhook_url: string;
  verify_token: string;
  instructions: string;
}

interface LeadsStats {
  total_leads: number;
  converted_leads: number;
  conversion_rate: number;
  active_leads: number;
}

export default function LeadsFormsTab() {
  const { t } = useTranslation();
  const [webhookConfig, setWebhookConfig] = useState<WebhookConfig | null>(null);
  const [leadsStats, setLeadsStats] = useState<LeadsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    loadWebhookConfig();
    loadLeadsStats();
  }, []);

  const loadWebhookConfig = async () => {
    try {
      const { data } = await api.get('/admin/leads/webhook/url');
      setWebhookConfig(data);
    } catch (err) {
      console.error('Error loading webhook config:', err);
      setError(t('leads.errors.load_config'));
    } finally {
      setLoading(false);
    }
  };

  const loadLeadsStats = async () => {
    try {
      const { data } = await api.get('/admin/leads/stats/summary');
      setLeadsStats(data.totals);
    } catch (err) {
      console.error('Error loading leads stats:', err);
      // Don't set error for stats, it's optional
    }
  };

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const openMetaAdsConfig = () => {
    window.open('https://business.facebook.com/ads/manager/webhooks/', '_blank');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <AlertCircle className="w-6 h-6 text-red-500" />
          <h3 className="text-lg font-bold text-red-800">{t('common.error')}</h3>
        </div>
        <p className="text-red-700">{error}</p>
        <button
          onClick={loadWebhookConfig}
          className="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg font-bold hover:bg-red-200 transition-colors"
        >
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header with Stats */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-black text-gray-900 flex items-center gap-3">
              <MessageSquare className="w-8 h-8 text-blue-600" />
              {t('leads.title')}
            </h2>
            <p className="text-gray-600 mt-2">
              {t('leads.subtitle')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-gray-400" />
            <span className="text-sm text-gray-500">{t('leads.integration')}</span>
          </div>
        </div>

        {/* Stats Cards */}
        {leadsStats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.total')}</p>
                  <p className="text-2xl font-black text-gray-900">{leadsStats.total_leads}</p>
                </div>
                <Users className="w-8 h-8 text-blue-500" />
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.converted')}</p>
                  <p className="text-2xl font-black text-green-600">{leadsStats.converted_leads}</p>
                </div>
                <CheckCircle2 className="w-8 h-8 text-green-500" />
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.conversion_rate')}</p>
                  <p className="text-2xl font-black text-indigo-600">{leadsStats.conversion_rate}%</p>
                </div>
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                  <span className="text-indigo-600 font-bold">%</span>
                </div>
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.active')}</p>
                  <p className="text-2xl font-black text-amber-600">{leadsStats.active_leads}</p>
                </div>
                <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                  <span className="text-amber-600 font-bold">!</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-blue-100 border border-blue-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-white text-xs font-bold">i</span>
            </div>
            <div>
              <p className="text-blue-800 font-medium">
                {t('leads.info')}
              </p>
              <p className="text-blue-700 text-sm mt-1">
                {t('leads.info_detail')}
              </p>
              <div className="mt-2 p-2 bg-blue-200 rounded-lg">
                <p className="text-blue-900 text-xs font-bold">
                  ⚠️ IMPORTANTE: Para ver nombres de anuncios/campañas (no solo IDs)
                </p>
                <p className="text-blue-800 text-xs">
                  Configura un token de Meta en la pestaña "Chatwoot (Meta)"
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Webhook Configuration */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-3">
            <Link className="w-5 h-5 text-blue-600" />
            {t('leads.webhook_configuration')}
          </h3>
          <p className="text-gray-600 mt-1">
            {t('leads.webhook_description')}
          </p>
        </div>

        <div className="p-6 space-y-6">
          {/* Webhook URL */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-gray-700">
                {t('leads.webhook_url')}
              </label>
              <button
                onClick={() => webhookConfig && copyToClipboard(webhookConfig.webhook_url, 'url')}
                className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                {copied === 'url' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    {t('common.copied')}
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    {t('common.copy')}
                  </>
                )}
              </button>
            </div>
            <div className="bg-gray-50 border border-gray-300 rounded-lg p-3 font-mono text-sm text-gray-800 overflow-x-auto">
              {webhookConfig?.webhook_url || t('leads.loading_url')}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {t('leads.webhook_url_instructions')}
            </p>
          </div>

          {/* Verify Token */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-bold text-gray-700">
                {t('leads.verify_token')}
              </label>
              <button
                onClick={() => webhookConfig && copyToClipboard(webhookConfig.verify_token, 'token')}
                className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                {copied === 'token' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    {t('common.copied')}
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    {t('common.copy')}
                  </>
                )}
              </button>
            </div>
            <div className="bg-gray-50 border border-gray-300 rounded-lg p-3 font-mono text-sm text-gray-800 overflow-x-auto">
              {webhookConfig?.verify_token || t('leads.loading_token')}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {t('leads.verify_token_instructions')}
            </p>
          </div>

          {/* Configuration Instructions */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <h4 className="font-bold text-amber-800 mb-2 flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {t('leads.configuration_steps')}
            </h4>
            <ol className="list-decimal list-inside space-y-2 text-amber-700 text-sm">
              <li>{t('leads.step_1')}</li>
              <li>{t('leads.step_2')}</li>
              <li>{t('leads.step_3')}</li>
              <li>{t('leads.step_4')}</li>
              <li>{t('leads.step_5')}</li>
            </ol>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 pt-4">
            <button
              onClick={openMetaAdsConfig}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              {t('leads.open_meta_config')}
            </button>
            
            <button
              onClick={loadWebhookConfig}
              className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-bold hover:bg-gray-200 transition-colors"
            >
              {t('leads.refresh_config')}
            </button>
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <a
          href="/leads"
          className="bg-white border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center group-hover:bg-blue-200 transition-colors">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <h4 className="font-bold text-gray-900">{t('leads.view_leads')}</h4>
          </div>
          <p className="text-sm text-gray-600">
            {t('leads.view_leads_description')}
          </p>
        </a>
        
        <a
          href="/marketing"
          className="bg-white border border-gray-200 rounded-xl p-5 hover:border-green-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center group-hover:bg-green-200 transition-colors">
              <MessageSquare className="w-5 h-5 text-green-600" />
            </div>
            <h4 className="font-bold text-gray-900">{t('leads.marketing_hub')}</h4>
          </div>
          <p className="text-sm text-gray-600">
            {t('leads.marketing_hub_description')}
          </p>
        </a>
        
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-indigo-600" />
            </div>
            <h4 className="font-bold text-gray-900">{t('leads.automatic_attribution')}</h4>
          </div>
          <p className="text-sm text-gray-600">
            {t('leads.automatic_attribution_description')}
          </p>
          <ul className="mt-3 space-y-1 text-xs text-gray-500">
            <li>• {t('leads.attribution_feature_1')}</li>
            <li>• {t('leads.attribution_feature_2')}</li>
            <li>• {t('leads.attribution_feature_3')}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}