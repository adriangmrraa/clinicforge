import React, { useState, useRef } from 'react';
import { Database, Download, Upload, Lock, AlertCircle, Loader2, CheckCircle2, X } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import { Modal } from './Modal';

interface BackupRestoreSectionProps {
  userRole?: string;
  tenantId?: number;
}

export const BackupRestoreSection: React.FC<BackupRestoreSectionProps> = ({ userRole, tenantId }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Backup states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState('');
  const [backupReady, setBackupReady] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  // Restore states
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [restorePassword, setRestorePassword] = useState('');
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreProgress, setRestoreProgress] = useState('');
  const [restoreResult, setRestoreResult] = useState<any>(null);

  // === BACKUP: Password → Generate → Download ===

  const handleGenerate = async () => {
    if (!password) { setError(t('backup.error_password_required')); return; }

    setLoading(true);
    setError(null);

    try {
      // Step 1: Submit password and start generation
      const res = await api.post('/admin/backup/generate-direct', { password });
      const { task_id } = res.data;
      setTaskId(task_id);
      setProgress(0);
      setProgressMsg(t('backup.starting_backup'));

      // Step 2: Poll progress
      const interval = setInterval(async () => {
        try {
          const statusRes = await api.get(`/admin/backup/status/${task_id}`);
          const d = statusRes.data;
          setProgress(d.progress_pct || 0);
          setProgressMsg(d.message || '');

          if (d.status === 'done' || d.status === 'completed' || d.download_ready) {
            clearInterval(interval);
            setBackupReady(true);
            setLoading(false);
          } else if (d.status === 'error') {
            clearInterval(interval);
            setError(d.error || t('backup.error_generating'));
            setLoading(false);
          }
        } catch {
          // Polling error — keep trying
        }
      }, 2000);

    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message;
      if (err.response?.status === 401) {
        setError(t('backup.error_wrong_password'));
      } else if (err.response?.status === 409) {
        setError(t('backup.error_concurrent_backup'));
      } else {
        setError(typeof msg === 'string' ? msg : t('backup.error_generating'));
      }
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      const response = await api.get(`/admin/backup/download/${taskId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `backup_${new Date().toISOString().split('T')[0]}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setDownloaded(true);
      setTimeout(() => closeModal(), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('backup.error_downloading'));
    }
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setPassword('');
    setError(null);
    setTaskId(null);
    setProgress(0);
    setProgressMsg('');
    setBackupReady(false);
    setDownloaded(false);
    setLoading(false);
  };

  // === RESTORE ===

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
    if (!restoreFile || !restorePassword) return;
    setRestoreLoading(true);
    setError(null);
    setRestoreProgress(t('backup.restore_validating'));
    setRestoreResult(null);
    try {
      const formData = new FormData();
      formData.append('file', restoreFile);
      formData.append('password', restorePassword);
      const res = await api.post('/admin/backup/restore', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setRestoreResult(res.data);
      setRestoreProgress(t('backup.restore_completed'));
    } catch (err: any) {
      setError(err.response?.data?.detail || t('backup.error_restoring'));
    } finally {
      setRestoreLoading(false);
    }
  };

  const closeRestoreModal = () => {
    setIsRestoreModalOpen(false);
    setRestoreFile(null);
    setRestorePassword('');
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
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium flex items-center gap-2 transition-all"
        >
          <Download size={18} />
          {t('backup.generate_button')}
        </button>
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

      {/* === BACKUP MODAL (simplified: password → progress → download) === */}
      <Modal isOpen={isModalOpen} onClose={closeModal} title={t('backup.modal_title')} size="md">
        {!taskId && !backupReady && !downloaded ? (
          /* Step 1: Password */
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-white/60 text-sm">
              <Lock size={16} />
              Ingresá tu contraseña de CEO para generar el backup de todos los datos de la clínica.
            </div>
            <div>
              <label className="block text-sm text-white/70 mb-2">{t('backup.modal_password_label')}</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading || !password}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/50 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
              Generar Backup
            </button>
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle size={16} /> {error}
              </div>
            )}
          </div>
        ) : backupReady && !downloaded ? (
          /* Step 3: Download ready */
          <div className="space-y-4 text-center py-4">
            <CheckCircle2 size={48} className="mx-auto text-green-400" />
            <p className="text-white text-lg font-medium">{t('backup.ready_title')}</p>
            <p className="text-white/50 text-sm">{t('backup.ready_message')}</p>
            <button
              onClick={handleDownload}
              className="w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
            >
              <Download size={18} />
              {t('backup.download_zip_button')}
            </button>
          </div>
        ) : downloaded ? (
          /* Step 4: Downloaded */
          <div className="text-center py-6">
            <CheckCircle2 size={48} className="mx-auto text-green-400 mb-3" />
            <p className="text-white text-lg font-medium">Backup descargado correctamente</p>
          </div>
        ) : (
          /* Step 2: Progress */
          <div className="space-y-4 py-4">
            <div className="text-center">
              <Loader2 size={48} className="mx-auto text-indigo-400 animate-spin mb-4" />
              <p className="text-white text-lg font-medium">{t('backup.generating_title')}</p>
              <p className="text-white/50 text-sm mt-1">{progressMsg}</p>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-white/60">{t('backup.progress_label')}</span>
                <span className="text-indigo-400 font-medium">{progress}%</span>
              </div>
              <div className="h-3 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 transition-all duration-500" style={{ width: `${progress}%` }} />
              </div>
            </div>
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-2 text-red-400 text-sm">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}
          </div>
        )}
        <button onClick={closeModal} className="mt-4 w-full py-2 text-white/50 hover:text-white text-sm flex items-center justify-center gap-1">
          <X size={14} /> {t('common.cancel')}
        </button>
      </Modal>

      {/* === RESTORE MODAL === */}
      <Modal isOpen={isRestoreModalOpen} onClose={closeRestoreModal} title={t('backup.restore_modal_title')} size="md">
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
              <input ref={fileInputRef} type="file" accept=".zip" onChange={handleRestoreFileSelect} className="hidden" />
              {restoreFile && (
                <div className="flex items-center justify-between p-3 bg-white/[0.04] rounded-xl">
                  <div className="flex items-center gap-2">
                    <Database size={16} className="text-indigo-400" />
                    <span className="text-white text-sm">{restoreFile.name}</span>
                  </div>
                  <span className="text-white/40 text-xs">{(restoreFile.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
              )}
              {restoreFile && (
                <div>
                  <label className="block text-sm text-white/70 mb-2">
                    <Lock size={14} className="inline mr-1" />
                    {t('backup.modal_password_label')}
                  </label>
                  <input
                    type="password"
                    value={restorePassword}
                    onChange={(e) => setRestorePassword(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && restorePassword && handleRestore()}
                    className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white outline-none focus:ring-2 focus:ring-amber-500"
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
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
                  <AlertCircle size={16} /> {error}
                </div>
              )}
              <button
                onClick={handleRestore}
                disabled={restoreLoading || !restoreFile || !restorePassword}
                className="w-full py-3 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-600/50 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all"
              >
                {restoreLoading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
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
                          {table}: {String(count)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <button onClick={closeRestoreModal} className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-all">
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
