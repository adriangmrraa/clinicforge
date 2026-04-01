import { useState, useEffect, useRef } from 'react';
import { useTranslation } from '../context/LanguageContext';
import {
  FileText, Plus, Download, Mail, Trash2, Edit,
  RefreshCw, Loader2, X, ChevronLeft, AlertTriangle,
  Send, Save, Eye
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

type ViewState = 'list' | 'generating' | 'preview' | 'editing';

const TEMPLATE_TYPES = [
  { id: 'clinical_report', icon: '📋', color: 'blue' },
  { id: 'post_surgery', icon: '🩺', color: 'emerald' },
  { id: 'odontogram_art', icon: '🦷', color: 'violet' },
  { id: 'authorization_request', icon: '📄', color: 'amber' },
];

interface Props {
  patientId: number;
  patientEmail?: string;
}

// Strip HTML tags to get plain text for editing
function htmlToPlainText(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  // Preserve structure: convert data-section divs to section markers
  const sections = doc.querySelectorAll('[data-section]');
  if (sections.length === 0) {
    return doc.body.textContent || '';
  }
  const parts: string[] = [];
  sections.forEach(section => {
    const sectionId = section.getAttribute('data-section') || '';
    const editable = section.getAttribute('data-editable') === 'true';
    const heading = section.querySelector('h2, h3');
    const headingText = heading ? heading.textContent?.trim() : '';
    // Get text content without the heading
    const clone = section.cloneNode(true) as HTMLElement;
    const headingInClone = clone.querySelector('h2, h3');
    if (headingInClone) headingInClone.remove();
    const bodyText = clone.textContent?.trim() || '';
    if (headingText) {
      parts.push(`--- ${headingText} ${editable ? '(editable)' : '(fijo)'} ---`);
    }
    if (bodyText) {
      parts.push(bodyText);
    }
    parts.push('');
  });
  return parts.join('\n');
}

export default function DigitalRecordsTab({ patientId, patientEmail }: Props) {
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
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchRecords(); }, [patientId]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const resp = await api.get(`/admin/patients/${patientId}/digital-records`);
      setRecords(resp.data || []);
    } catch (err) {
      console.error('Error fetching digital records:', err);
      setRecords([]);
    } finally { setLoading(false); }
  };

  const handleViewRecord = async (record: DigitalRecord) => {
    if (!record.html_content) {
      try {
        const resp = await api.get(`/admin/patients/${patientId}/digital-records/${record.id}`);
        const full = resp.data;
        setSelectedRecord(full);
        setRecords(prev => prev.map(r => r.id === record.id ? { ...r, html_content: full.html_content, generation_warnings: full.generation_warnings } : r));
      } catch (err) {
        console.error('Error fetching record:', err);
        return;
      }
    } else {
      setSelectedRecord(record);
    }
    setViewState('preview');
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
    } finally { setGenerating(false); }
  };

  const handleDownloadPdf = async (record: DigitalRecord) => {
    try {
      const resp = await api.get(
        `/admin/patients/${patientId}/digital-records/${record.id}/pdf`,
        { responseType: 'blob' }
      );
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
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

  const handleSendEmail = async () => {
    if (!selectedRecord || !emailTo.trim()) return;
    setSending(true);
    try {
      await api.post(`/admin/patients/${patientId}/digital-records/${selectedRecord.id}/email`, {
        to_email: emailTo,
      });
      const updated = { ...selectedRecord, sent_to_email: emailTo, sent_at: new Date().toISOString(), status: 'sent' };
      setRecords(prev => prev.map(r => r.id === selectedRecord.id ? updated : r));
      setSelectedRecord(updated);
      setEmailModalOpen(false);
      setEmailTo('');
    } catch (err) {
      console.error('Error sending email:', err);
    } finally { setSending(false); }
  };

  const handleDelete = async (recordId: string) => {
    if (!confirm(t('digitalRecords.deleteConfirm'))) return;
    try {
      await api.delete(`/admin/patients/${patientId}/digital-records/${recordId}`);
      setRecords(prev => prev.filter(r => r.id !== recordId));
      if (selectedRecord?.id === recordId) { setSelectedRecord(null); setViewState('list'); }
    } catch (err) { console.error('Error deleting digital record:', err); }
  };

  const handleStartEdit = () => {
    if (!selectedRecord?.html_content) return;
    setEditContent(htmlToPlainText(selectedRecord.html_content));
    setViewState('editing');
  };

  const handleSaveEdit = async () => {
    if (!selectedRecord) return;
    setSaving(true);
    try {
      // Wrap plain text back in basic HTML structure
      const htmlWrapped = editContent.split('\n').map(line => {
        if (line.startsWith('--- ') && line.endsWith(' ---')) {
          const title = line.replace(/^--- /, '').replace(/ \(editable\) ---$/, '').replace(/ \(fijo\) ---$/, '');
          return `<h3 class="section-title">${title}</h3>`;
        }
        if (line.trim() === '') return '<br>';
        return `<p>${line}</p>`;
      }).join('\n');

      await api.patch(`/admin/patients/${patientId}/digital-records/${selectedRecord.id}`, {
        html_content: htmlWrapped,
      });
      const updated = { ...selectedRecord, html_content: htmlWrapped, updated_at: new Date().toISOString() };
      setRecords(prev => prev.map(r => r.id === selectedRecord.id ? updated : r));
      setSelectedRecord(updated);
      setViewState('preview');
    } catch (err) { console.error('Error saving edit:', err); }
    finally { setSaving(false); }
  };

  const openEmailModal = (record: DigitalRecord) => {
    setSelectedRecord(record);
    setEmailTo(patientEmail || '');
    setEmailModalOpen(true);
  };

  const getStatusBadge = (record: DigitalRecord) => {
    if (record.status === 'sent') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400"><Send size={10} />{t('digitalRecords.sent')}</span>;
    if (record.status === 'final') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400">{t('digitalRecords.final')}</span>;
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400">{t('digitalRecords.draft')}</span>;
  };

  const getTemplateLabel = (templateType: string) => {
    const tpl = TEMPLATE_TYPES.find(tp => tp.id === templateType);
    return tpl ? `${tpl.icon} ${t(`digitalRecords.${tpl.id}`)}` : templateType;
  };

  // ─── Render content based on viewState ─────────────────────────────────────
  const renderContent = () => {
    // Generating
    if (viewState === 'generating') {
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 size={40} className="text-white/40 animate-spin" />
          <p className="text-white/60 text-sm">{t('digitalRecords.generating')}</p>
        </div>
      );
    }

    // Editing
    if (viewState === 'editing' && selectedRecord) {
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <button onClick={() => setViewState('preview')} className="flex items-center gap-2 text-white/60 hover:text-white transition-colors text-sm">
              <ChevronLeft size={16} /> Volver a vista previa
            </button>
            <div className="flex items-center gap-2">
              <button onClick={() => setViewState('preview')} className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs">
                <Eye size={14} /> Vista previa
              </button>
              <button onClick={handleSaveEdit} disabled={saving} className="flex items-center gap-2 px-4 py-1.5 bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 text-xs font-medium disabled:opacity-50">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {saving ? 'Guardando...' : 'Guardar cambios'}
              </button>
            </div>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Edit size={18} className="text-blue-400" /> Editando: {selectedRecord.title}
            </h3>
            <p className="text-xs text-white/40 mt-1">Editá el contenido del documento. Las secciones marcadas (fijo) contienen datos del paciente. Al guardar, el PDF se regenera automáticamente.</p>
          </div>
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            className="w-full h-[60vh] bg-[#0d1117] border border-white/[0.08] text-white/90 rounded-lg p-4 text-sm leading-relaxed resize-y focus:outline-none focus:border-white/20"
            spellCheck={false}
          />
        </div>
      );
    }

    // Preview
    if (viewState === 'preview' && selectedRecord) {
      const record = selectedRecord;
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <button onClick={() => { setViewState('list'); setSelectedRecord(null); }} className="flex items-center gap-2 text-white/60 hover:text-white transition-colors text-sm">
              <ChevronLeft size={16} /> {t('digitalRecords.back')}
            </button>
            <div className="flex items-center gap-2 flex-wrap">
              {getStatusBadge(record)}
              <button onClick={handleStartEdit} className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-colors text-xs">
                <Edit size={14} /> Editar
              </button>
              <button onClick={() => handleDownloadPdf(record)} className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs">
                <Download size={14} /> {t('digitalRecords.downloadPdf')}
              </button>
              <button onClick={() => openEmailModal(record)} className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs">
                <Mail size={14} /> {t('digitalRecords.sendEmail')}
              </button>
              <button onClick={() => handleDelete(record.id)} className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors text-xs">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{record.title}</h3>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-white/40">{getTemplateLabel(record.template_type)}</span>
              {record.created_at && <span className="text-xs text-white/40">{new Date(record.created_at).toLocaleString('es-AR')}</span>}
            </div>
          </div>
          {record.generation_warnings && record.generation_warnings.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-amber-400 mb-1">{t('digitalRecords.warnings')}</p>
                  <ul className="space-y-1">
                    {record.generation_warnings.map((w, i) => <li key={i} className="text-xs text-amber-300/80">{w}</li>)}
                  </ul>
                </div>
              </div>
            </div>
          )}
          <div className="bg-white rounded-lg p-8 text-black overflow-auto max-h-[70vh] shadow-lg">
            <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(record.html_content || '', { ADD_TAGS: ['style'], ADD_ATTR: ['data-section', 'data-editable'] }) }} />
          </div>
          {record.sent_to_email && (
            <p className="text-xs text-white/40 flex items-center gap-1">
              <Send size={12} /> {t('digitalRecords.sentTo')}: {record.sent_to_email}
              {record.sent_at && ` — ${new Date(record.sent_at).toLocaleString('es-AR')}`}
            </p>
          )}
        </div>
      );
    }

    // List (default)
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <FileText size={20} className="text-white/50" /> {t('digitalRecords.title')}
          </h3>
          <div className="flex items-center gap-2">
            <button onClick={fetchRecords} className="p-2 text-white/40 hover:text-white/70 hover:bg-white/[0.04] rounded-lg transition-colors">
              <RefreshCw size={16} />
            </button>
            <button onClick={() => setGenerateModalOpen(true)} className="flex items-center gap-2 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm font-medium">
              <Plus size={16} /> {t('digitalRecords.generate')}
            </button>
          </div>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 size={28} className="text-white/30 animate-spin" /></div>
        ) : records.length === 0 ? (
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-10 text-center">
            <FileText size={44} className="mx-auto mb-4 text-white/20" />
            <p className="text-white/40 text-sm">{t('digitalRecords.empty')}</p>
            <button onClick={() => setGenerateModalOpen(true)} className="mt-4 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm font-medium">
              {t('digitalRecords.generate')}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {records.map(record => (
              <div key={record.id} className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 hover:border-white/[0.12] transition-all">
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-white truncate">{record.title}</span>
                      {getStatusBadge(record)}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-white/40">
                      <span>{getTemplateLabel(record.template_type)}</span>
                      {record.created_at && <span>{new Date(record.created_at).toLocaleString('es-AR')}</span>}
                      {record.sent_to_email && <span className="flex items-center gap-1"><Send size={10} />{record.sent_to_email}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => handleViewRecord(record)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs">
                      <Eye size={13} /> {t('digitalRecords.view')}
                    </button>
                    <button onClick={() => handleDownloadPdf(record)} className="px-2.5 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] text-xs" title={t('digitalRecords.downloadPdf')}>
                      <Download size={13} />
                    </button>
                    <button onClick={() => openEmailModal(record)} className="px-2.5 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] text-xs" title={t('digitalRecords.sendEmail')}>
                      <Mail size={13} />
                    </button>
                    <button onClick={() => handleDelete(record.id)} className="px-2.5 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 text-xs" title={t('digitalRecords.delete')}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ─── Single return with content + modals always rendered ───────────────────
  return (
    <>
      {renderContent()}

      {/* Template Selection Modal — always in DOM */}
      {generateModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-white">{t('digitalRecords.selectTemplate')}</h2>
              <button onClick={() => setGenerateModalOpen(false)} className="text-white/40 hover:text-white/70 p-1.5 rounded-full"><X size={16} /></button>
            </div>
            <div className="p-5 grid grid-cols-2 gap-3">
              {TEMPLATE_TYPES.map(tpl => (
                <button key={tpl.id} onClick={() => handleGenerate(tpl.id)} disabled={generating}
                  className="flex flex-col items-start gap-2 p-4 bg-white/[0.03] border border-white/[0.06] rounded-lg hover:bg-white/[0.06] hover:border-white/[0.12] transition-all text-left disabled:opacity-50">
                  <span className="text-2xl">{tpl.icon}</span>
                  <div>
                    <p className="text-sm font-semibold text-white">{t(`digitalRecords.${tpl.id}`)}</p>
                    <p className="text-xs text-white/40 mt-0.5 leading-snug">{t(`digitalRecords.${tpl.id}_desc`)}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Email Modal — always in DOM, works from any viewState */}
      {emailModalOpen && selectedRecord && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-sm shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Mail size={18} className="text-blue-400" />
                {t('digitalRecords.sendEmailTitle')}
              </h2>
              <button onClick={() => setEmailModalOpen(false)} className="text-white/40 hover:text-white/70 p-1.5 rounded-full"><X size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-xs text-white/50">Enviando: <span className="text-white/80 font-medium">{selectedRecord.title}</span></p>
              {patientEmail && (
                <button onClick={() => setEmailTo(patientEmail)} className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors ${emailTo === patientEmail ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' : 'bg-white/[0.03] border-white/[0.06] text-white/60 hover:bg-white/[0.06]'}`}>
                  <Mail size={14} /> Email del paciente: {patientEmail}
                </button>
              )}
              <div>
                <label className="text-xs text-white/50 mb-1 block">O ingresá otro email:</label>
                <input type="email" value={emailTo} onChange={e => setEmailTo(e.target.value)} placeholder={t('digitalRecords.emailPlaceholder')}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/30 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-white/20" />
              </div>
              <div className="flex gap-3 pt-1">
                <button onClick={() => setEmailModalOpen(false)} className="flex-1 px-4 py-2.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-sm">
                  {t('common.cancel')}
                </button>
                <button onClick={handleSendEmail} disabled={sending || !emailTo.trim()}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 text-sm font-medium disabled:opacity-50">
                  {sending ? <><Loader2 size={14} className="animate-spin" /> {t('digitalRecords.sending')}</> : <><Send size={14} /> Enviar</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
