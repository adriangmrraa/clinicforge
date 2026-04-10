import React, { useState, useRef } from 'react';
import { Database, Download, Upload, Lock, Mail, AlertCircle, Loader2, CheckCircle2, XCircle, RefreshCw, X } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';

interface BackupTask {
  task_id?: string;
  status: 'idle' | 'sending_code' | 'waiting_code' | 'generating' | 'ready' | 'error' | 'downloaded';
  progress_pct: number;
  message: string;
  error?: string;
  download_ready?: boolean;
  attempts_remaining?: number;
  code_expires_in?: number;
}

interface BackupRestoreSectionProps {
  userRole?: string;
  tenantId?: number;
}

export const BackupRestoreSection: React.FC<BackupRestoreSectionProps> = ({ userRole, tenantId }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalStep, setModalStep] = useState<'password' | 'code' | 'progress' | 'download'>('password');
  
  // Form states
  const [password, setPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  
  // Loading states
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  
  // Error states
  const [error, setError] = useState<string | null>(null);
  const [attemptsRemaining, setAttemptsRemaining] = useState(3);

  // Backup task state
  const [task, setTask] = useState<BackupTask>({
    status: 'idle',
    progress_pct: 0,
    message: '',
  });
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Restore states
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreProgress, setRestoreProgress] = useState<string>('');
  const [restoreResult, setRestoreResult] = useState<any>(null);

  // Clean up polling on unmount
  React.useEffect(() => {
    return () => {
      if (pollingInterval) clearInterval(pollingInterval);
    };
  }, [pollingInterval]);

  // === BACKUP FLOW ===

  const handleRequestCode = async () => {
    if (!password) {
      setError(t('backup.error_password_required'));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      setSendingCode(true);
      const res = await api.post('/admin/backup/request-code');
      
      if (res.status === 200) {
        setCodeSent(true);
        setModalStep('code');
        setTask(prev => ({ ...prev, status: 'waiting_code', message: t('backup.waiting_code') }));
        
        // Start cooldown for resend
        setResendCooldown(60);
        const interval = setInterval(() => {
          setResendCooldown(prev => {
            if (prev <= 1) {
              clearInterval(interval);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        setAttemptsRemaining(3);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      if (err.response?.status === 429) {
        setError(msg);
      } else if (err.response?.status === 503) {
        setError(t('backup.error_smtp_not_configured'));
      } else {
        setError(msg || t('backup.error_sending_code'));
      }
    } finally {
      setLoading(false);
      setSendingCode(false);
    }
  };

  const handleGenerateBackup = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setError(t('backup.error_invalid_code'));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await api.post('/admin/backup/generate', {
        password,
        code: verificationCode,
      });

      if (res.status === 202) {
        const { task_id } = res.data;
        setModalStep('progress');
        setTask({
          status: 'generating',
          task_id,
          progress_pct: 0,
          message: t('backup.starting_backup'),
        });

        // Start polling
        const interval = setInterval(async () => {
          try {
            const statusRes = await api.get(`/admin/backup/status/${task_id}`);
            const statusData = statusRes.data;
            
            setTask(prev => ({
              ...prev,
              status: statusData.status as any,
              progress_pct: statusData.progress_pct,
              message: statusData.message,
              download_ready: statusData.download_ready,
              error: statusData.error,
            }));

            if (statusData.status === 'completed' || statusData.status === 'ready') {
              clearInterval(interval);
              setPollingInterval(null);
              setTask(prev => ({ ...prev, status: 'ready' }));
            } else if (statusData.status === 'error') {
              clearInterval(interval);
              setPollingInterval(null);
            }
          } catch (e) {
            console.error('Polling error:', e);
          }
        }, 2000);

        setPollingInterval(interval);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      if (err.response?.status === 401) {
        setError(t('backup.error_wrong_password'));
      } else if (err.response?.status === 400) {
        // Wrong code - decrement attempts
        const remaining = err.response?.data?.attempts_remaining ?? attemptsRemaining - 1;
        setAttemptsRemaining(remaining);
        
        if (remaining <= 0) {
          setError(t('backup.error_max_attempts'));
          setModalStep('password');
          setCodeSent(false);
          setVerificationCode('');
        } else {
          setError(`${t('backup.error_wrong_code')} (${remaining} ${t('backup.attempts_remaining')})`);
        }
      } else if (err.response?.status === 409) {
        setError(t('backup.error_concurrent_backup'));
      } else {
        setError(msg || t('backup.error_generating'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!task.task_id) return;

    try {
      const response = await api.get(`/admin/backup/download/${task.task_id}`, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `backup_${new Date().toISOString().split('T')[0]}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setTask(prev => ({ ...prev, status: 'downloaded' }));
      setTimeout(() => closeModal(), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('backup.error_downloading'));
    }
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setModalStep('password');
    setPassword('');
    setVerificationCode('');
    setCodeSent(false);
    setError(null);
    setAttemptsRemaining(3);
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    setTask({ status: 'idle', progress_pct: 0, message: '' });
  };

  // === RESTORE FLOW ===

  const handleRestoreFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.name.endsWith('.zip')) {
      setRestoreFile(file);
      setError(null);
    } else {
      setError(t('backup.error_invalid_zip'));
    }
  };

  const handleRestore = async () => {
    if (!restoreFile) return;

    setRestoreLoading(true);
    setError(null);
    setRestoreProgress(t('backup.restore_validating'));
    setRestoreResult(null);

    try {
      const formData = new FormData();
      formData.append('file', restoreFile);

      const res = await api.post('/admin/backup/restore', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setRestoreResult(res.data);
      setRestoreProgress(t('backup.restore_completed'));
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      setError(msg || t('backup.error_restoring'));
    } finally {
      setRestoreLoading(false);
    }
  };

  const closeRestoreModal = () => {
    setIsRestoreModalOpen(false);
    setRestoreFile(null);
    setRestoreResult(null);
    setError(null);
  };

  if (userRole !== 'ceo') return null;

  return (
    <>
      {/* === BACKUP CARD === */}
      <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-indigo-500/20 rounded-xl">
            <Database size={22} className="text-indigo-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{t('backup.title')}</h3>
            <p className="text-sm text-white/50">{t('backup.description')}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => setIsModalOpen(true)}
            disabled={task.status === 'generating'}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium flex items-center gap-2 transition-all"
          >
            {task.status === 'generating' ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Download size={18} />
            )}
            {t('backup.generate_button')}
          </button>

          {task.status === 'ready' && task.download_ready && (
            <button
              onClick={handleDownload}
              className="px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium flex items-center gap-2 transition-all"
            >
              <Download size={18} />
              {t('backup.download_button')}
            </button>
          )}
        </div>

        {task.status === 'generating' && (
          <div className="mt-4 p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-indigo-300">{task.message}</span>
              <span className="text-sm font-medium text-indigo-300">{task.progress_pct}%</span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${task.progress_pct}%` }}
              />
            </div>
          </div>
        )}

        {task.status === 'error' && (
          <div className="mt-4 p-3 bg-red-500/10 rounded-xl border border-red-500/20">
            <div className="flex items-center gap-2 text-red-400">
              <AlertCircle size={18} />
              <span className="text-sm">{task.error || t('backup.error_generic')}</span>
            </div>
          </div>
        )}
      </div>

      {/* === RESTORE CARD === */}
      <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-amber-500/20 rounded-xl">
            <Upload size={22} className="text-amber-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{t('backup.restore_title')}</h3>
            <p className="text-sm text-white/50">{t('backup.restore_description')}</p>
          </div>
        </div>

        <button
          onClick={() => setIsRestoreModalOpen(true)}
          className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-medium flex items-center gap-2 transition-all"
        >
          <Upload size={18} />
          {t('backup.restore_button')}
        </button>
      </div>

      {/* === BACKUP MODAL === */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={t('backup.modal_title')} maxWidth="max-w-md">
        {modalStep === 'password' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-white/60 text-sm">
              <Lock size={16} />
              {t('backup.modal_password_hint')}
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-2">{t('backup.modal_password_label')}</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>

            <button
              onClick={handleRequestCode}
              disabled={loading || !password}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
            >
              {sendingCode ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Mail size={18} />
              )}
              {t('backup.request_code_button')}
            </button>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
          </div>
        )}

        {modalStep === 'code' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-green-400 text-sm">
              <CheckCircle2 size={16} />
              {t('backup.code_sent_message')}
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-2">{t('backup.code_input_label')}</label>
              <input
                type="text"
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-center text-2xl font-mono tracking-widest outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="000000"
                maxLength={6}
                autoComplete="one-time-code"
              />
              <p className="text-xs text-white/40 mt-2 text-center">
                {attemptsRemaining} {t('backup.attempts_remaining')}
              </p>
            </div>

            <button
              onClick={handleGenerateBackup}
              disabled={loading || verificationCode.length !== 6}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Download size={18} />
              )}
              {t('backup.generate_backup_button')}
            </button>

            <button
              onClick={handleRequestCode}
              disabled={resendCooldown > 0}
              className="w-full py-2 text-white/50 hover:text-white text-sm flex items-center justify-center gap-1 transition-colors"
            >
              <RefreshCw size={14} className={resendCooldown > 0 ? 'animate-spin' : ''} />
              {resendCooldown > 0 
                ? `${t('backup.resend_cooldown')} (${resendCooldown}s)`
                : t('backup.resend_code')
              }
            </button>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle size={16} />
                {error}
              </div>
            )}
          </div>
        )}

        {modalStep === 'progress' && (
          <div className="space-y-4">
            <div className="text-center py-4">
              <Loader2 size={48} className="mx-auto text-indigo-400 animate-spin mb-4" />
              <p className="text-white text-lg font-medium">{t('backup.generating_title')}</p>
              <p className="text-white/50 text-sm mt-1">{task.message}</p>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-white/60">{t('backup.progress_label')}</span>
                <span className="text-indigo-400 font-medium">{task.progress_pct}%</span>
              </div>
              <div className="h-3 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-indigo-500 transition-all duration-500"
                  style={{ width: `${task.progress_pct}%` }}
                />
              </div>
            </div>

            {task.status === 'error' && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-2 text-red-400 text-sm">
                <XCircle size={16} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">{t('backup.error_title')}</p>
                  <p className="text-red-300 mt-1">{task.error}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {modalStep === 'download' && (
          <div className="space-y-4">
            <div className="text-center py-4">
              <CheckCircle2 size={48} className="mx-auto text-green-400 mb-4" />
              <p className="text-white text-lg font-medium">{t('backup.ready_title')}</p>
              <p className="text-white/50 text-sm mt-1">{t('backup.ready_message')}</p>
            </div>

            <button
              onClick={handleDownload}
              className="w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
            >
              <Download size={18} />
              {t('backup.download_zip_button')}
            </button>
          </div>
        )}

        <button
          onClick={closeModal}
          className="mt-4 w-full py-2 text-white/50 hover:text-white text-sm flex items-center justify-center gap-1 transition-colors"
        >
          <X size={14} />
          {t('common.cancel')}
        </button>
      </Modal>

      {/* === RESTORE MODAL === */}
      <Modal isOpen={isRestoreModalOpen} onClose={closeRestoreModal} title={t('backup.restore_modal_title')} maxWidth="max-w-md">
        <div className="space-y-4">
          {!restoreResult ? (
            <>
              <div 
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-white/20 hover:border-indigo-500/50 rounded-xl p-8 text-center cursor-pointer transition-colors"
              >
                <Upload size={32} className="mx-auto text-white/40 mb-3" />
                <p className="text-white/70 text-sm">{t('backup.restore_dropzone')}</p>
                <p className="text-white/40 text-xs mt-1">{t('backup.restore_dropzone_hint')}</p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                onChange={handleRestoreFileSelect}
                className="hidden"
              />

              {restoreFile && (
                <div className="flex items-center justify-between p-3 bg-white/[0.04] rounded-xl">
                  <div className="flex items-center gap-2">
                    <Database size={16} className="text-indigo-400" />
                    <span className="text-white text-sm">{restoreFile.name}</span>
                  </div>
                  <span className="text-white/40 text-xs">
                    {(restoreFile.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
              )}

              {restoreLoading && (
                <div className="flex items-center gap-2 text-indigo-400">
                  <Loader2 size={16} className="animate-spin" />
                  <span className="text-sm">{restoreProgress}</span>
                </div>
              )}

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              <button
                onClick={handleRestore}
                disabled={restoreLoading || !restoreFile}
                className="w-full py-3 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
              >
                {restoreLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Upload size={18} />
                )}
                {t('backup.start_restore_button')}
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle2 size={24} />
                <span className="font-medium">{t('backup.restore_success_title')}</span>
              </div>

              <div className="space-y-2 p-4 bg-white/[0.04] rounded-xl">
                <div className="flex justify-between text-sm">
                  <span className="text-white/60">{t('backup.rows_inserted')}</span>
                  <span className="text-white">{restoreResult.rows_inserted}</span>
                </div>
                {restoreResult.tables_restored && (
                  <div className="mt-3 pt-3 border-t border-white/[0.08]">
                    <p className="text-xs text-white/40 mb-2">{t('backup.tables_restored')}</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(restoreResult.tables_restored).map(([table, count]) => (
                        <span key={table} className="px-2 py-1 bg-indigo-500/20 text-indigo-300 text-xs rounded">
                          {table}: {count}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {restoreResult.warnings?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-white/[0.08]">
                    <p className="text-xs text-amber-400 mb-1">{t('backup.warnings')}</p>
                    {restoreResult.warnings.map((w: string, i: number) => (
                      <p key={i} className="text-xs text-white/50">{w}</p>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={closeRestoreModal}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-all"
              >
                {t('common.close')}
              </button>
            </>
          )}
        </div>
      </Modal>
    </>
  );
};

export default BackupRestoreSection;