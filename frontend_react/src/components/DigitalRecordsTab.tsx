import { useState, useEffect } from 'react';
import { useTranslation } from '../context/LanguageContext';
import {
  FileText, Plus, Download, Mail, Trash2, Edit,
  RefreshCw, Loader2, X, ChevronLeft, AlertTriangle,
  Send, Save, Eye, Lock, Check, AlertCircle
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

interface Section {
  id: string;
  title: string;
  content: string;
  editable: boolean;
}

type ViewState = 'list' | 'generating' | 'preview' | 'editing';

const TEMPLATE_TYPES = [
  { id: 'clinical_report', icon: '📋', color: 'blue' },
  { id: 'post_surgery', icon: '🩺', color: 'emerald' },
  { id: 'odontogram_art', icon: '🦷', color: 'violet' },
  { id: 'authorization_request', icon: '📄', color: 'amber' },
];

const SECTION_LABELS: Record<string, string> = {
  patient_info: 'Datos del Paciente',
  resumen_clinico: 'Resumen Clínico',
  antecedentes: 'Antecedentes Médicos',
  odontograma: 'Odontograma',
  estado_dental: 'Estado Dental',
  tratamientos_realizados: 'Tratamientos Realizados',
  historial_tabla: 'Historial de Registros',
  plan_tratamiento: 'Plan de Tratamiento',
  recomendaciones: 'Recomendaciones',
  contexto: 'Contexto',
  antecedente_quirurgico: 'Antecedente Quirúrgico',
  procedimiento_actual: 'Procedimiento Actual',
  evolucion: 'Evolución',
  conducta: 'Conducta y Seguimiento',
  proximo_turno: 'Próximo Turno',
  constancia: 'Constancia',
  tipo_evaluacion: 'Tipo de Evaluación',
  hallazgos: 'Hallazgos Clínicos',
  detalle_piezas: 'Detalle por Pieza',
  observacion: 'Observación',
  diagnostico: 'Diagnóstico',
  tratamiento_realizado: 'Tratamiento Realizado',
  tratamiento_solicitado: 'Tratamiento Solicitado',
  material_objetivo: 'Material y Objetivo',
  justificacion: 'Justificación Clínica',
  valor: 'Valor del Tratamiento',
  observaciones: 'Observaciones',
};

interface Props {
  patientId: number;
  patientEmail?: string;
  refreshKey?: number;
}

/** Parse HTML into sections using data-section attributes */
function parseSections(html: string): Section[] {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const sectionEls = doc.querySelectorAll('[data-section]');
  if (sectionEls.length === 0) {
    return [{ id: 'full', title: 'Documento', content: html, editable: true }];
  }
  const sections: Section[] = [];
  sectionEls.forEach(el => {
    const id = el.getAttribute('data-section') || 'unknown';
    const editable = el.getAttribute('data-editable') === 'true';
    sections.push({
      id,
      title: SECTION_LABELS[id] || id,
      content: el.innerHTML,
      editable,
    });
  });
  return sections;
}

/** Reconstruct HTML from edited sections */
function rebuildHtml(originalHtml: string, sections: Section[]): string {
  const doc = new DOMParser().parseFromString(originalHtml, 'text/html');
  sections.forEach(section => {
    const el = doc.querySelector(`[data-section="${section.id}"]`);
    if (el && section.editable) {
      el.innerHTML = section.content;
    }
  });
  return doc.body.innerHTML;
}

/** Strip HTML to plain text for textarea editing */
function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return doc.body.textContent?.trim() || '';
}

/** Convert plain text back to simple HTML */
function textToHtml(text: string, originalHtml: string): string {
  // Preserve any existing heading from original
  const doc = new DOMParser().parseFromString(originalHtml, 'text/html');
  const heading = doc.querySelector('h2, h3');
  const headingHtml = heading ? heading.outerHTML : '';
  const paragraphs = text.split('\n').filter(l => l.trim()).map(l => `<p>${l}</p>`).join('\n');
  return headingHtml ? `${headingHtml}\n<div class="narrative">${paragraphs}</div>` : `<div class="narrative">${paragraphs}</div>`;
}

export default function DigitalRecordsTab({ patientId, patientEmail, refreshKey }: Props) {
  const { t } = useTranslation();

  const [records, setRecords] = useState<DigitalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewState, setViewState] = useState<ViewState>('list');
  const [selectedRecord, setSelectedRecord] = useState<DigitalRecord | null>(null);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailTo, setEmailTo] = useState('');
  const [sending, setSending] = useState(false);
  const [emailStatus, setEmailStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  // Section-based editing
  const [editSections, setEditSections] = useState<Section[]>([]);

  useEffect(() => { fetchRecords(); }, [patientId, refreshKey]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const resp = await api.get(`/admin/patients/${patientId}/digital-records`);
      setRecords(resp.data || []);
    } catch (err) { console.error('Error fetching digital records:', err); setRecords([]); }
    finally { setLoading(false); }
  };

  const handleViewRecord = async (record: DigitalRecord) => {
    if (!record.html_content) {
      try {
        const resp = await api.get(`/admin/patients/${patientId}/digital-records/${record.id}`);
        const full = resp.data;
        setSelectedRecord(full);
        setRecords(prev => prev.map(r => r.id === record.id ? { ...r, html_content: full.html_content, generation_warnings: full.generation_warnings } : r));
      } catch (err) { console.error('Error fetching record:', err); return; }
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
      const resp = await api.post(`/admin/patients/${patientId}/digital-records/generate`, { template_type: templateType });
      const newRecord: DigitalRecord = resp.data;
      setRecords(prev => [newRecord, ...prev]);
      setSelectedRecord(newRecord);
      setViewState('preview');
    } catch (err) { console.error('Error generating digital record:', err); setViewState('list'); }
    finally { setGenerating(false); }
  };

  const handleDownloadPdf = async (record: DigitalRecord) => {
    try {
      const resp = await api.get(`/admin/patients/${patientId}/digital-records/${record.id}/pdf`, { responseType: 'blob' });
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${record.title || 'documento'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) { console.error('Error downloading PDF:', err); }
  };

  const handleSendEmail = async () => {
    if (!selectedRecord || !emailTo.trim()) return;
    setSending(true);
    setEmailStatus(null);
    try {
      await api.post(`/admin/patients/${patientId}/digital-records/${selectedRecord.id}/email`, { to_email: emailTo });
      const updated = { ...selectedRecord, sent_to_email: emailTo, sent_at: new Date().toISOString(), status: 'sent' };
      setRecords(prev => prev.map(r => r.id === selectedRecord.id ? updated : r));
      setSelectedRecord(updated);
      setEmailStatus({ type: 'success', msg: `Email enviado a ${emailTo}` });
      setTimeout(() => { setEmailModalOpen(false); setEmailTo(''); setEmailStatus(null); }, 1500);
    } catch (err: any) {
      console.error('Error sending email:', err);
      const detail = err?.response?.data?.detail || 'Error al enviar el email. Intentá de nuevo.';
      setEmailStatus({ type: 'error', msg: detail });
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
    const sections = parseSections(selectedRecord.html_content);
    setEditSections(sections);
    setViewState('editing');
  };

  const handleSectionTextChange = (sectionId: string, newText: string) => {
    setEditSections(prev => prev.map(s =>
      s.id === sectionId ? { ...s, content: textToHtml(newText, s.content) } : s
    ));
  };

  const handleSaveEdit = async () => {
    if (!selectedRecord?.html_content) return;
    setSaving(true);
    try {
      const newHtml = rebuildHtml(selectedRecord.html_content, editSections);
      await api.patch(`/admin/patients/${patientId}/digital-records/${selectedRecord.id}`, { html_content: newHtml });
      const updated = { ...selectedRecord, html_content: newHtml, updated_at: new Date().toISOString() };
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

  // ─── Render content ─────────────────────────────────────────────────────────
  const renderContent = () => {
    if (viewState === 'generating') {
      return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Loader2 size={40} className="text-white/40 animate-spin" />
          <p className="text-white/60 text-sm">{t('digitalRecords.generating')}</p>
        </div>
      );
    }

    // ── Editing: section cards ─────────────────────────────────────────────
    if (viewState === 'editing' && selectedRecord) {
      return (
        <div className="space-y-3 sm:space-y-4 pb-28">
          <div className="flex items-center justify-between gap-2">
            <button onClick={() => setViewState('preview')} className="flex items-center gap-1.5 text-white/60 hover:text-white transition-colors text-xs sm:text-sm">
              <ChevronLeft size={16} /> Volver
            </button>
            <button onClick={() => setViewState('preview')} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs">
              <Eye size={14} /> Preview
            </button>
          </div>
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
              <Edit size={16} className="text-blue-400 shrink-0" />
              <span className="truncate">{selectedRecord.title}</span>
            </h3>
            <p className="text-[11px] text-white/40 mt-1">Secciones con borde azul son editables. Las fijas contienen datos del paciente.</p>
          </div>

          <div className="space-y-2.5">
            {editSections.map(section => (
              <div
                key={section.id}
                className={`rounded-xl p-3 sm:p-4 space-y-2 transition-all ${
                  section.editable
                    ? 'bg-white/[0.03] border-2 border-blue-500/20'
                    : 'bg-white/[0.02] border border-white/[0.06] opacity-70'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {!section.editable && <Lock size={11} className="text-white/30 shrink-0" />}
                    <span className={`text-[11px] font-bold uppercase tracking-wider truncate ${section.editable ? 'text-blue-400' : 'text-white/30'}`}>
                      {section.title}
                    </span>
                  </div>
                  {section.editable && (
                    <span className="text-[9px] text-blue-400/60 bg-blue-500/10 px-1.5 py-0.5 rounded-full shrink-0">Editable</span>
                  )}
                </div>
                {section.editable ? (
                  <textarea
                    value={htmlToText(section.content)}
                    onChange={e => handleSectionTextChange(section.id, e.target.value)}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white/90 rounded-lg p-2.5 sm:p-3 text-[13px] sm:text-sm leading-relaxed resize-y min-h-[70px] focus:outline-none focus:border-blue-500/30 focus:bg-white/[0.06] transition-colors"
                    rows={Math.max(3, htmlToText(section.content).split('\n').length + 1)}
                  />
                ) : (
                  <div className="text-[13px] sm:text-sm text-white/50 leading-relaxed overflow-x-auto">
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(section.content, { ADD_TAGS: ['table', 'thead', 'tbody', 'tr', 'th', 'td', 'svg', 'path', 'circle', 'line', 'g', 'text', 'rect'] }) }} />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Floating save button — safe area for iPhone notch */}
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 pb-safe">
            <button
              onClick={handleSaveEdit}
              disabled={saving}
              className="flex items-center gap-2 px-5 sm:px-6 py-2.5 sm:py-3 bg-white text-[#0a0e1a] rounded-full text-sm font-semibold shadow-lg shadow-black/40 hover:bg-white/90 active:scale-95 transition-all disabled:opacity-50"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      );
    }

    // ── Preview ────────────────────────────────────────────────────────────
    if (viewState === 'preview' && selectedRecord) {
      const record = selectedRecord;
      return (
        <div className="space-y-3 sm:space-y-4">
          {/* Back button */}
          <button onClick={() => { setViewState('list'); setSelectedRecord(null); }} className="flex items-center gap-1.5 text-white/60 hover:text-white transition-colors text-xs sm:text-sm">
            <ChevronLeft size={16} /> {t('digitalRecords.back')}
          </button>

          {/* Title + meta */}
          <div>
            <h3 className="text-base sm:text-lg font-semibold text-white leading-tight">{record.title}</h3>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              {getStatusBadge(record)}
              <span className="text-[11px] text-white/40">{getTemplateLabel(record.template_type)}</span>
              {record.created_at && <span className="text-[11px] text-white/40">{new Date(record.created_at).toLocaleString('es-AR')}</span>}
            </div>
          </div>

          {/* Action buttons — horizontal scroll on mobile */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
            <button onClick={handleStartEdit} className="flex items-center gap-1.5 px-3 py-2 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/20 text-xs whitespace-nowrap shrink-0">
              <Edit size={14} /> Editar
            </button>
            <button onClick={() => handleDownloadPdf(record)} className="flex items-center gap-1.5 px-3 py-2 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs whitespace-nowrap shrink-0">
              <Download size={14} /> PDF
            </button>
            <button onClick={() => openEmailModal(record)} className="flex items-center gap-1.5 px-3 py-2 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs whitespace-nowrap shrink-0">
              <Mail size={14} /> Email
            </button>
            <button onClick={() => handleDelete(record.id)} className="flex items-center gap-1.5 px-2.5 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 text-xs whitespace-nowrap shrink-0">
              <Trash2 size={14} />
            </button>
          </div>

          {/* Warnings */}
          {record.generation_warnings && record.generation_warnings.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 sm:p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-[11px] font-semibold text-amber-400 mb-1">{t('digitalRecords.warnings')}</p>
                  <ul className="space-y-0.5">{record.generation_warnings.map((w, i) => <li key={i} className="text-[11px] text-amber-300/80">{w}</li>)}</ul>
                </div>
              </div>
            </div>
          )}

          {/* HTML Preview — responsive padding */}
          <div className="bg-white rounded-lg p-4 sm:p-8 text-black overflow-auto max-h-[60vh] sm:max-h-[70vh] shadow-lg text-[13px] sm:text-base">
            <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(record.html_content || '', { ADD_TAGS: ['svg', 'path', 'circle', 'line', 'g', 'text', 'rect'], ADD_ATTR: ['data-section', 'data-editable', 'viewBox', 'fill', 'stroke', 'stroke-width', 'cx', 'cy', 'r', 'd', 'x1', 'y1', 'x2', 'y2', 'opacity', 'transform', 'font-size', 'font-weight', 'text-anchor', 'stroke-linecap', 'stroke-dasharray'] }) }} />
          </div>

          {/* Sent info */}
          {record.sent_to_email && (
            <p className="text-[11px] text-white/40 flex items-center gap-1">
              <Send size={11} /> {t('digitalRecords.sentTo')}: {record.sent_to_email}
              {record.sent_at && ` — ${new Date(record.sent_at).toLocaleString('es-AR')}`}
            </p>
          )}
        </div>
      );
    }

    // ── List ───────────────────────────────────────────────────────────────
    return (
      <div className="space-y-3 sm:space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
            <FileText size={18} className="text-white/50 shrink-0" />
            <span className="truncate">{t('digitalRecords.title')}</span>
          </h3>
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <button onClick={fetchRecords} className="p-2 text-white/40 hover:text-white/70 hover:bg-white/[0.04] rounded-lg"><RefreshCw size={15} /></button>
            <button onClick={() => setGenerateModalOpen(true)} className="flex items-center gap-1.5 bg-white text-[#0a0e1a] px-3 sm:px-4 py-2 rounded-lg hover:bg-white/90 text-xs sm:text-sm font-medium">
              <Plus size={15} />
              <span className="hidden sm:inline">{t('digitalRecords.generate')}</span>
              <span className="sm:hidden">Generar</span>
            </button>
          </div>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-12"><Loader2 size={28} className="text-white/30 animate-spin" /></div>
        ) : records.length === 0 ? (
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-8 sm:p-10 text-center">
            <FileText size={40} className="mx-auto mb-3 text-white/20" />
            <p className="text-white/40 text-sm">{t('digitalRecords.empty')}</p>
            <button onClick={() => setGenerateModalOpen(true)} className="mt-4 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:bg-white/90 text-sm font-medium">{t('digitalRecords.generate')}</button>
          </div>
        ) : (
          <div className="space-y-2.5">
            {records.map(record => (
              <div key={record.id} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 sm:p-4 hover:border-white/[0.12] transition-all">
                {/* Info */}
                <div className="mb-2.5">
                  <div className="flex flex-wrap items-center gap-1.5 mb-1">
                    <span className="text-[13px] sm:text-sm font-semibold text-white">{record.title}</span>
                    {getStatusBadge(record)}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-white/40">
                    <span>{getTemplateLabel(record.template_type)}</span>
                    {record.created_at && <span>{new Date(record.created_at).toLocaleDateString('es-AR')}</span>}
                    {record.sent_to_email && <span className="flex items-center gap-1"><Send size={9} />{record.sent_to_email}</span>}
                  </div>
                </div>
                {/* Actions — always row, scroll on mobile */}
                <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
                  <button onClick={() => handleViewRecord(record)} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-xs whitespace-nowrap shrink-0">
                    <Eye size={13} /> Ver
                  </button>
                  <button onClick={() => handleDownloadPdf(record)} className="flex items-center gap-1 px-2 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] text-xs whitespace-nowrap shrink-0">
                    <Download size={13} /> PDF
                  </button>
                  <button onClick={() => openEmailModal(record)} className="flex items-center gap-1 px-2 py-1.5 bg-white/[0.06] border border-white/[0.08] text-white/50 rounded-lg hover:bg-white/[0.1] text-xs whitespace-nowrap shrink-0">
                    <Mail size={13} /> Email
                  </button>
                  <button onClick={() => handleDelete(record.id)} className="flex items-center gap-1 px-2 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg hover:bg-red-500/20 text-xs whitespace-nowrap shrink-0">
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {renderContent()}

      {/* Template Selection Modal */}
      {generateModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-t-2xl sm:rounded-xl w-full sm:max-w-md shadow-2xl max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 sm:p-5 border-b border-white/[0.06] sticky top-0 bg-[#0d1117] z-10">
              <h2 className="text-sm sm:text-base font-semibold text-white">{t('digitalRecords.selectTemplate')}</h2>
              <button onClick={() => setGenerateModalOpen(false)} className="text-white/40 hover:text-white/70 p-1.5 rounded-full"><X size={16} /></button>
            </div>
            <div className="p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-3 pb-6 sm:pb-5">
              {TEMPLATE_TYPES.map(tpl => (
                <button key={tpl.id} onClick={() => handleGenerate(tpl.id)} disabled={generating}
                  className="flex items-center sm:flex-col sm:items-start gap-3 sm:gap-2 p-3.5 sm:p-4 bg-white/[0.03] border border-white/[0.06] rounded-xl hover:bg-white/[0.06] hover:border-white/[0.12] transition-all text-left disabled:opacity-50 active:scale-[0.98]">
                  <span className="text-2xl shrink-0">{tpl.icon}</span>
                  <div className="min-w-0">
                    <p className="text-[13px] sm:text-sm font-semibold text-white">{t(`digitalRecords.${tpl.id}`)}</p>
                    <p className="text-[11px] sm:text-xs text-white/40 mt-0.5 leading-snug">{t(`digitalRecords.${tpl.id}_desc`)}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Email Modal */}
      {emailModalOpen && selectedRecord && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-t-2xl sm:rounded-xl w-full sm:max-w-sm shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-white flex items-center gap-2"><Mail size={18} className="text-blue-400" />{t('digitalRecords.sendEmailTitle')}</h2>
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
              {emailStatus && (
                <div className={`p-2.5 rounded-lg text-xs flex items-center gap-2 ${
                  emailStatus.type === 'success'
                    ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                    : 'bg-red-500/10 border border-red-500/20 text-red-400'
                }`}>
                  {emailStatus.type === 'success' ? <Check size={14} /> : <AlertCircle size={14} />}
                  {emailStatus.msg}
                </div>
              )}
              <div className="flex gap-3 pt-1">
                <button onClick={() => { setEmailModalOpen(false); setEmailStatus(null); }} className="flex-1 px-4 py-2.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-lg hover:bg-white/[0.1] text-sm">{t('common.cancel')}</button>
                <button onClick={handleSendEmail} disabled={sending || !emailTo.trim() || emailStatus?.type === 'success'}
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
