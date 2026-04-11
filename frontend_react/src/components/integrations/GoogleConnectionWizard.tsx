import React, { useState, useEffect } from 'react';
import { Globe, CheckCircle, AlertCircle, RefreshCw, ExternalLink, X } from 'lucide-react';
import api from '../../api/axios';
import { useTranslation } from '../../context/LanguageContext';
import { getCurrentTenantId } from '../../api/axios';

interface GoogleConnectionWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onConnected?: () => void;
}

type WizardStep = 'welcome' | 'configure' | 'authorize' | 'complete' | 'error';

const GoogleConnectionWizard: React.FC<GoogleConnectionWizardProps> = ({
  isOpen,
  onClose,
  onConnected
}) => {
  const { t } = useTranslation();
  const [currentStep, setCurrentStep] = useState<WizardStep>('welcome');
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<any>(null);
  const [configStatus, setConfigStatus] = useState<any>(null);

  useEffect(() => {
    if (isOpen) {
      loadConfigStatus();
    }
  }, [isOpen]);

  const loadConfigStatus = async () => {
    try {
      const { data } = await api.get('/admin/marketing/google/debug/config');
      setConfigStatus(data.config);
    } catch (error) {
      console.error('Failed to load Google config status:', error);
    }
  };

  const handleStartConnection = async () => {
    setIsConnecting(true);
    setConnectionError(null);

    try {
      const tenantId = getCurrentTenantId();
      const { data } = await api.get(`/admin/auth/google/ads/url?state=tenant_${tenantId}_ads`);
      
      if (data?.url) {
        // Open Google OAuth in new window
        window.open(data.url, '_blank', 'noopener,noreferrer,width=600,height=700');
        
        // Poll for connection status
        pollConnectionStatus();
        setCurrentStep('authorize');
      } else {
        throw new Error(t('marketing.google.errors.no_auth_url'));
      }
    } catch (error: any) {
      console.error('Google connection error:', error);
      setConnectionError(error.response?.data?.detail || error.message || t('common.error'));
      setCurrentStep('error');
    } finally {
      setIsConnecting(false);
    }
  };

  const pollConnectionStatus = () => {
    const checkInterval = setInterval(async () => {
      try {
        const { data } = await api.get('/admin/auth/google/ads/test-connection');
        
        if (data?.status?.connected) {
          clearInterval(checkInterval);
          setConnectionStatus(data.status);
          setCurrentStep('complete');
          
          // Notify parent component
          if (onConnected) {
            onConnected();
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000); // Check every 2 seconds

    // Stop polling after 2 minutes
    setTimeout(() => {
      clearInterval(checkInterval);
    }, 120000);
  };

  const handleTestConnection = async () => {
    setIsConnecting(true);
    setConnectionError(null);

    try {
      const { data } = await api.get('/admin/marketing/google/connection-status');
      setConnectionStatus(data.connection_status);
      
      if (data.connection_status.success) {
        setCurrentStep('complete');
        if (onConnected) {
          onConnected();
        }
      } else {
        setCurrentStep('error');
        setConnectionError(data.connection_status.message);
      }
    } catch (error: any) {
      console.error('Connection test error:', error);
      setConnectionError(error.response?.data?.detail || error.message || t('common.error'));
      setCurrentStep('error');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleConfigureManually = () => {
    setCurrentStep('configure');
  };

  const handleRetry = () => {
    setCurrentStep('welcome');
    setConnectionError(null);
    setConnectionStatus(null);
  };

  const handleComplete = () => {
    onClose();
    if (onConnected) {
      onConnected();
    }
  };

  if (!isOpen) return null;

  const renderStep = () => {
    switch (currentStep) {
      case 'welcome':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                <Globe className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">
                {t('marketing_google.wizard.welcome.title')}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {t('marketing_google.wizard.welcome.description')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h4 className="font-medium text-gray-900">
                  {t('marketing_google.wizard.welcome.benefits.title')}
                </h4>
                <ul className="mt-2 space-y-2 text-sm text-gray-600">
                  <li className="flex items-start">
                    <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                    {t('marketing_google.wizard.welcome.benefits.campaign_tracking')}
                  </li>
                  <li className="flex items-start">
                    <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                    {t('marketing_google.wizard.welcome.benefits.roi_analytics')}
                  </li>
                  <li className="flex items-start">
                    <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                    {t('marketing_google.wizard.welcome.benefits.combined_dashboard')}
                  </li>
                  <li className="flex items-start">
                    <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                    {t('marketing_google.wizard.welcome.benefits.automatic_sync')}
                  </li>
                </ul>
              </div>

              {configStatus && (
                <div className="rounded-lg border border-gray-200 bg-blue-50 p-4">
                  <h4 className="font-medium text-gray-900">
                    {t('marketing_google.wizard.welcome.config_status')}
                  </h4>
                  <div className="mt-2 space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Google Client ID:</span>
                      <span className={configStatus.google_client_id ? 'text-green-600 font-medium' : 'text-red-600'}>
                        {configStatus.google_client_id ? '✓ Configurado' : '✗ Faltante'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Developer Token:</span>
                      <span className={configStatus.google_developer_token ? 'text-green-600 font-medium' : 'text-red-600'}>
                        {configStatus.google_developer_token ? '✓ Configurado' : '✗ Faltante'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleStartConnection}
                disabled={isConnecting}
                className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
              >
                {isConnecting ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin inline" />
                    {t('common.connecting')}
                  </>
                ) : (
                  t('marketing_google.wizard.welcome.connect_button')
                )}
              </button>
              <button
                type="button"
                onClick={handleConfigureManually}
                className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              >
                {t('marketing_google.wizard.welcome.configure_manually')}
              </button>
            </div>
          </div>
        );

      case 'configure':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-yellow-100">
                <AlertCircle className="h-6 w-6 text-yellow-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">
                {t('marketing_google.wizard.configure.title')}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {t('marketing_google.wizard.configure.description')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-gray-200 bg-yellow-50 p-4">
                <h4 className="font-medium text-gray-900">
                  {t('marketing_google.wizard.configure.requirements.title')}
                </h4>
                <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-gray-600">
                  <li>{t('marketing_google.wizard.configure.requirements.google_cloud_project')}</li>
                  <li>{t('marketing_google.wizard.configure.requirements.enable_apis')}</li>
                  <li>{t('marketing_google.wizard.configure.requirements.oauth_credentials')}</li>
                  <li>{t('marketing_google.wizard.configure.requirements.developer_token')}</li>
                  <li>{t('marketing_google.wizard.configure.requirements.configure_redirect')}</li>
                </ol>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h4 className="font-medium text-gray-900">
                  {t('marketing_google.wizard.configure.variables.title')}
                </h4>
                <div className="mt-2 space-y-2">
                  <div className="text-sm">
                    <code className="block rounded bg-gray-100 p-2 text-xs">
                      GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
                    </code>
                    <p className="mt-1 text-gray-600">
                      {t('marketing_google.wizard.configure.variables.client_id_desc')}
                    </p>
                  </div>
                  <div className="text-sm">
                    <code className="block rounded bg-gray-100 p-2 text-xs">
                      GOOGLE_CLIENT_SECRET=your-client-secret
                    </code>
                    <p className="mt-1 text-gray-600">
                      {t('marketing_google.wizard.configure.variables.client_secret_desc')}
                    </p>
                  </div>
                  <div className="text-sm">
                    <code className="block rounded bg-gray-100 p-2 text-xs">
                      GOOGLE_DEVELOPER_TOKEN=your-developer-token
                    </code>
                    <p className="mt-1 text-gray-600">
                      {t('marketing_google.wizard.configure.variables.developer_token_desc')}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isConnecting}
                className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
              >
                {isConnecting ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin inline" />
                    {t('common.testing')}
                  </>
                ) : (
                  t('marketing_google.wizard.configure.test_connection')
                )}
              </button>
              <button
                type="button"
                onClick={handleRetry}
                className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              >
                {t('common.back')}
              </button>
            </div>
          </div>
        );

      case 'authorize':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                <RefreshCw className="h-6 w-6 animate-spin text-blue-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">
                {t('marketing_google.wizard.authorize.title')}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {t('marketing_google.wizard.authorize.description')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-gray-200 bg-blue-50 p-4">
                <h4 className="font-medium text-gray-900">
                  {t('marketing_google.wizard.authorize.instructions.title')}
                </h4>
                <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-gray-600">
                  <li>{t('marketing_google.wizard.authorize.instructions.open_window')}</li>
                  <li>{t('marketing_google.wizard.authorize.instructions.select_account')}</li>
                  <li>{t('marketing_google.wizard.authorize.instructions.grant_permissions')}</li>
                  <li>{t('marketing_google.wizard.authorize.instructions.wait_redirect')}</li>
                </ol>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex items-center">
                  <AlertCircle className="mr-2 h-4 w-4 text-yellow-600" />
                  <p className="text-sm text-gray-600">
                    {t('marketing_google.wizard.authorize.note')}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleStartConnection}
                disabled={isConnecting}
                className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
              >
                {isConnecting ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin inline" />
                    {t('common.connecting')}
                  </>
                ) : (
                  <>
                    <ExternalLink className="mr-2 h-4 w-4 inline" />
                    {t('marketing_google.wizard.authorize.open_again')}
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={handleTestConnection}
                className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              >
                {t('marketing_google.wizard.authorize.check_connection')}
              </button>
            </div>
          </div>
        );

      case 'complete':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">
                {t('marketing_google.wizard.complete.title')}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {t('marketing_google.wizard.complete.description')}
              </p>
            </div>

            {connectionStatus && (
              <div className="space-y-4">
                <div className="rounded-lg border border-gray-200 bg-green-50 p-4">
                  <h4 className="font-medium text-gray-900">
                    {t('marketing_google.wizard.complete.connection_details')}
                  </h4>
                  <div className="mt-2 space-y-2 text-sm">
                    {connectionStatus.email && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Email:</span>
                        <span className="font-medium text-gray-900">{connectionStatus.email}</span>
                      </div>
                    )}
                    {connectionStatus.expires_at && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Expira:</span>
                        <span className="font-medium text-gray-900">
                          {new Date(connectionStatus.expires_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                    {connectionStatus.customers_count !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Cuentas accesibles:</span>
                        <span className="font-medium text-gray-900">{connectionStatus.customers_count}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-600">Estado:</span>
                      <span className="font-medium text-green-600">✓ Conectado</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-gray-200 bg-blue-50 p-4">
                  <h4 className="font-medium text-gray-900">
                    {t('marketing_google.wizard.complete.next_steps')}
                  </h4>
                  <ul className="mt-2 space-y-2 text-sm text-gray-600">
                    <li className="flex items-start">
                      <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                      {t('marketing_google.wizard.complete.steps.view_dashboard')}
                    </li>
                    <li className="flex items-start">
                      <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                      {t('marketing_google.wizard.complete.steps.configure_sync')}
                    </li>
                    <li className="flex items-start">
                      <CheckCircle className="mr-2 h-4 w-4 text-green-500 mt-0.5" />
                      {t('marketing_google.wizard.complete.steps.setup_alerts')}
                    </li>
                  </ul>
                </div>
              </div>
            )}

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleComplete}
                className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                {t('marketing_google.wizard.complete.finish_button')}
              </button>
              <button
                type="button"
                onClick={() => window.location.href = '/marketing?platform=google'}
                className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              >
                {t('marketing_google.wizard.complete.view_dashboard')}
              </button>
            </div>
          </div>
        );

      case 'error':
        return (
          <div className="space-y-6">
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-gray-900">
                {t('marketing_google.wizard.error.title')}
              </h3>
              <p className="mt-2 text-sm text-gray-600">
                {connectionError || t('marketing_google.wizard.error.description')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg border border-gray-200 bg-red-50 p-4">
                <h4 className="font-medium text-gray-900">
                  {t('marketing_google.wizard.error.troubleshooting.title')}
                </h4>
                <ul className="mt-2 space-y-2 text-sm text-gray-600">
                  <li>{t('marketing_google.wizard.error.troubleshooting.check_credentials')}</li>
                  <li>{t('marketing_google.wizard.error.troubleshooting.verify_redirect')}</li>
                  <li>{t('marketing_google.wizard.error.troubleshooting.check_permissions')}</li>
                  <li>{t('marketing_google.wizard.error.troubleshooting.contact_support')}</li>
                </ul>
              </div>

              {configStatus && (
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <h4 className="font-medium text-gray-900">
                    {t('marketing_google.wizard.error.config_status')}
                  </h4>
                  <div className="mt-2 space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Google Client ID:</span>
                      <span className={configStatus.google_client_id ? 'text-green-600' : 'text-red-600'}>
                        {configStatus.google_client_id ? '✓' : '✗'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Developer Token:</span>
                      <span className={configStatus.google_developer_token ? 'text-green-600' : 'text-red-600'}>
                        {configStatus.google_developer_token ? '✓' : '✗'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={handleRetry}
                className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                {t('marketing_google.wizard.error.retry_button')}
              </button>
              <button
                type="button"
                onClick={handleConfigureManually}
                className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              >
                {t('marketing_google.wizard.error.configure_manually')}
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4 text-center">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="relative w-full max-w-md transform overflow-hidden rounded-lg bg-white p-6 text-left shadow-xl transition-all">
          <div className="absolute right-0 top-0 pr-4 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
            >
              <span className="sr-only">Close</span>
              <X className="h-6 w-6" />
            </button>
          </div>

          <div className="mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              {t('marketing_google.wizard.title')}
            </h2>
            <div className="mt-2 flex items-center space-x-2">
              <div className="flex-1 h-2 rounded-full bg-gray-200">
                <div 
                  className="h-2 rounded-full bg-blue-600 transition-all duration-300"
                  style={{ 
                    width: currentStep === 'welcome' ? '25%' : 
                           currentStep === 'configure' ? '50%' : 
                           currentStep === 'authorize' ? '75%' : '100%' 
                  }}
                />
              </div>
              <span className="text-sm text-gray-500">
                {currentStep === 'welcome' ? '1/4' : 
                 currentStep === 'configure' ? '2/4' : 
                 currentStep === 'authorize' ? '3/4' : '4/4'}
              </span>
            </div>
          </div>

          {renderStep()}
        </div>
      </div>
    </div>
  );
};

export default GoogleConnectionWizard;
