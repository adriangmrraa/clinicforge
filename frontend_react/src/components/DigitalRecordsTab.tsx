import { useState, useEffect } from 'react';
import { useTranslation } from '../context/LanguageContext';
import {
  FileText, Plus, Download, Mail, Trash2,
  RefreshCw, Loader2, X, ChevronLeft, AlertTriangle,
  Send
} from 'lucide-react';
import DOMPurify from 'dompurify';
import api from '../api/axios';

interface DigitalRecord {
  id: string;
  template_type: string;
  title: string;
  html_content?: string;
  status: string;
  created_at: string | null;
  updated_at?: string | null;
  sent_to_email?: string | null;
  sent_at?: string | null;
  generation_warnings?: string[];
}

type ViewState = 'list' | 'generating' | 'preview';

const TEMPLATE_TYPES = [
  { id: 'clinical_report', icon: '📋', color: 'blue' },
  { id: 'post_surgery', icon: '🩺', color: 'emerald' },
  { id: 'odontogram_art', icon: '🦷', color: 'violet' },
  { id: 'authorization_request', icon: '📄', color: 'amber' },
];

interface Props {
  patientId: number;
}

export default function DigitalRecordsTab({ patientId }: Props) {
  const { t } = useTranslation();

  const [records, setRecords] = useState<DigitalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewState, setViewState] = useState<ViewState>('list');
  const [selectedRecord, setSelectedRecord] = useState<DigitalRecord | null>(null);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailTo, setEmailTo] = useState('');
  const [sending, setSending] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchRecords();
  }, [patientId]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const resp = await api.get(`/admin/patients/${patientId}/digital-records`);
      setRecords(resp.data || []);
    } catch (err) {
      console.error('Error fetching digital records:', err);
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (templateType: string) => {
    setGenerateModalOpen(false);
    setGenerating(true);
    setViewState('generating');
    try {
      const resp = await api.post(`/admin/patients/${patientId}/digital-records/generate`, {
        template_type: templateType,
      });
      const newRecord: DigitalRecord = resp.data;
      setRecords(prev => [newRecord, ...prev]);
      setSelectedRecord(newRecord);
      setViewState('preview');
    } catch (err) {
      console.error('Error generating digital record:', err);
      setViewState('list');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPdf = async (record: DigitalRecord) => {
    try {
      const resp = await api.get(
        `/admin/patients/${patientId}/digital-records/${record.id}/pdf`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${record.title || 'documento'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error downloading PDF:', err);
    }
  };

  const handleSendEmail = async (record: DigitalRecord, email: string) => {
    if (!email.trim()) return;
    setSending(true);
    try {
      await api.post(`/admin/patients/${patientId}/digital-records/${record.id}/email`, {
        email,
      });
      // Update the local record with sent info
      const updated = { ...record, sent_to_email: email, sent_at: new Date().toISOString(), status: 'sent' };
      setRecords(prev => prev.map(r => r.id === record.id ? updated : r));
      if (selectedRecord?.id === record.id) setSelectedRecord(updated);
      setEmailModalOpen(false);
      setEmailTo('');
    } catch (err) {
      console.error('Error sending email:', err);
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async (recordId: string) => {
    if (!confirm(t('digitalRecords.deleteConfirm'))) return;
    try {
      await api.delete(`/admin/patients/${patientId}/digital-records/${recordId}`);
      setRecords(prev => prev.filter(r => r.id !== recordId));
      if (selectedRecord?.id === recordId) {
        setSelectedRecord(null);
        setViewState('list');
      }
    } catch (err) {
      console.error('Error deleting digital record:', err);
    }
  };

  const handleSaveEdit = async (record: DigitalRecord, htmlContent: string) => {
    try {
      const resp = await api.patch(`/admin/patients/${patientId}/digital-records/${record.id}`, {
        html_content: htmlContent,
      });
      const updated = resp.data as DigitalRecord;
      setRecords(prev => prev.map(r => r.id === record.id ? updated : r));
      setSelectedRecord(updated);
    } catch (err) {
      console.error('Error saving edit:', err);
    }
  };

  const handleRegenerateSection = async (record: DigitalRecord, sectionId: string) => {
    try {
      const resp = await api.post(
        `/admin/patients/${patientId}/digital-records/${record.id}/regenerate-section`,
        { section_id: sectionId }
      );
      const updated = resp.data as DigitalRecord;
      setRecords(prev => prev.map(r => r.id === record.id ? updated : r));
      setSelectedRecord(updated);
    } catch (err) {
      console.error('Error regenerating section:', err);
    }
  };

  const getStatusBadge = (record: DigitalRecord) => {
    if (record.status === 'sent') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400">
          <Send size={10} />
          {t('digitalRecords.sent')}
        </span>
      );
    }
    if (record.status === 'final') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400">
          {t('digitalRecords.final')}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400">
        {t('digitalRecords.draft')}
      </span>
    );
  };

  const getTemplateColor = (templateType: string) => {
    const tpl = TEMPLATE_TYPES.find(t => t.id === templateType);
    return tpl?.color || 'blue';
  };

  // ─── Generating state ───────────────────────────────────────────────────────
  if (viewState === 'generating') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <Loader2 size={40} className="text-white/40 animate-spin" />
        <p className="text-white/60 text-sm">{t('digitalRecords.generating')}</p>
      </div>
    );
  }

  // ─── Preview state ───────────────────────────────────────────────────────────
  if (viewState === 'preview' && selectedRecord) {
    const record = selectedRecord;
    return (
      <div className="space-y-4">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <button
            onClick={() => { setViewState('list'); setSelectedRecord(null); }}
            className="flex items-center gap-2 text-white/60 hover:text-white transition-colors text-sm"
          >
            <ChevronLeft size={16} />
            {t('digitalRecords.back')}
          </button>
          <div className="flex items-center gap-2 flex-wrap">
            {getStatusBadge(record)}
            <button
              onClick={() => handleDownloadPdf(record)}
              className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors text-xs"
            >
              <Download size={14} />
              {t('digitalRecords.downloadPdf')}
            </button>
            <button
              onClick={() => { setEmailTo(''); setEmailModalOpen(true); }}
              className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors text-xs"
            >
              <Mail size={14} />
              {t('digitalRecords.sendEmail')}
            </button>
            <button
              onClick={() => handleDelete(record.id)}
              className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors text-xs"
            >
              <Trash2 size={14} />
              {t('digitalRecords.delete')}
            </button>
          </div>
        </div>

        {/* Title */}
        <div>
          <h3 className="text-lg font-semibold text-white">{record.title}</h3>
          {record.created_at && (
            <p className="text-xs text-white/40 mt-0.5">
              {new Date(record.created_at).toLocaleString('es-AR')}
            </p>
          )}
        </div>

        {/* Warnings */}
        {record.generation_warnings && record.generation_warnings.length > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-amber-400 mb-1">{t('digitalRecords.warnings')}</p>
                <ul className="space-y-1">
                  {record.generation_warnings.map((w, i) => (
                    <li key={i} className="text-xs text-amber-300/80">{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* HTML Preview */}
        <div className="bg-white rounded-lg p-6 text-black overflow-auto max-h-[70vh] shadow-lg">
          <div
            dangerouslySetInnerHTML={{
              __html: DOMPurify.sanitize(record.html_content || ''),
            }}
          />
        </div>

        {/* Sent info */}
        {record.sent_to_email && (
          <p className="text-xs text-white/40 flex items-center gap-1">
            <Send size={12} />
            {t('digitalRecords.sentTo')}: {record.sent_to_email}
          </p>
        )}
      </div>
    );
  }

  // ─── List state ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <FileText size={20} className="text-white/50" />
          {t('digitalRecords.title')}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchRecords}
            className="p-2 text-white/40 hover:text-white/70 hover:bg-white/[0.04] rounded-lg transition-colors"
            title="Refrescar"
          >
            <RefreshCw size={16} />
          </button>
          <button
            onClick={() => setGenerateModalOpen(true)}
            className="flex items-center gap-2 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm font-medium"
          >
            <Plus size={16} />
            {t('digitalRecords.generate')}
          </button>
        </div>
      </div>

      {/* Records list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={28} className="text-white/30 animate-spin" />
        </div>
      ) : records.length === 0 ? (
        <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-10 text-center">
          <FileText size={44} className="mx-auto mb-4 text-white/20" />
          <p className="text-white/40 text-sm">{t('digitalRecords.empty')}</p>
          <button
            onClick={() => setGenerateModalOpen(true)}
            className="mt-4 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm font-medium"
          >
            {t('digitalRecords.generate')}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {records.map(record => {
            const color = getTemplateColor(record.template_type);
            return (
              <div
                key={record.id}
                className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 flex flex-col sm:flex-row sm:items-center gap-3"
              >
                {/* Left: info */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-white truncate">{record.title}</span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-${color}-500/10 text-${color}-400`}>
                      {t(`digitalRecords.${record.template_type}`) || record.template_type}
                    </span>
                    {getStatusBadge(record)}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-white/40">
                    {record.created_at && (
                      <span>{new Date(record.created_at).toLocaleString('es-AR')}</span>
                    )}
                    {record.sent_to_email && (
                      <span className="flex items-center gap-1">
                        <Send size={10} />
                        {record.sent_to_email}
                      </span>
                    )}
                  </div>
                </div>

                {/* Right: actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => { setSelectedRecord(record); setViewState('preview'); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors text-xs"
                  >
                    <FileText size={13} />
                    {t('digitalRecords.view')}
                  </button>
                  <button
                    onClick={() => handleDownloadPdf(record)}
                    className="p-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors"
                    title={t('digitalRecords.downloadPdf')}
                  >
                    <Download size={14} />
                  </button>
                  <button
                    onClick={() => { setSelectedRecord(record); setEmailTo(''); setEmailModalOpen(true); }}
                    className="p-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors"
                    title={t('digitalRecords.sendEmail')}
                  >
                    <Mail size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(record.id)}
                    className="p-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors"
                    title={t('digitalRecords.delete')}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Template Selection Modal */}
      {generateModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-white">{t('digitalRecords.selectTemplate')}</h2>
              <button
                onClick={() => setGenerateModalOpen(false)}
                className="text-white/40 hover:text-white/70 bg-white/[0.06] p-1.5 rounded-full transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-5 grid grid-cols-2 gap-3">
              {TEMPLATE_TYPES.map(tpl => (
                <button
                  key={tpl.id}
                  onClick={() => handleGenerate(tpl.id)}
                  disabled={generating}
                  className="flex flex-col items-start gap-2 p-4 bg-white/[0.03] border border-white/[0.06] rounded-lg hover:bg-white/[0.06] hover:border-white/[0.12] transition-all text-left group disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="text-2xl">{tpl.icon}</span>
                  <div>
                    <p className="text-sm font-semibold text-white group-hover:text-white/90">
                      {t(`digitalRecords.${tpl.id}`)}
                    </p>
                    <p className="text-xs text-white/40 mt-0.5 leading-snug">
                      {t(`digitalRecords.${tpl.id}_desc`)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Email Send Modal */}
      {emailModalOpen && selectedRecord && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-sm shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-white">{t('digitalRecords.sendEmailTitle')}</h2>
              <button
                onClick={() => { setEmailModalOpen(false); setSelectedRecord(null); }}
                className="text-white/40 hover:text-white/70 bg-white/[0.06] p-1.5 rounded-full transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <input
                type="email"
                value={emailTo}
                onChange={e => setEmailTo(e.target.value)}
                placeholder={t('digitalRecords.emailPlaceholder')}
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/30 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-white/20 focus:bg-white/[0.06] transition-colors"
              />
              <div className="flex gap-3">
                <button
                  onClick={() => { setEmailModalOpen(false); setSelectedRecord(null); }}
                  className="flex-1 px-4 py-2 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] hover:text-white transition-colors text-sm"
                >
                  {t('common.cancel')}
                </button>
                <button
                  onClick={() => handleSendEmail(selectedRecord, emailTo)}
                  disabled={sending || !emailTo.trim()}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sending ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      {t('digitalRecords.sending')}
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      {t('digitalRecords.sendEmail')}
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
