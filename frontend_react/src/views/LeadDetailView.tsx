import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Phone, Mail, Calendar, MapPin, User, MessageSquare,
  CheckCircle2, Clock, XCircle, AlertCircle, Edit, Copy, 
  ExternalLink, History, FileText, Tag, Building2, Globe,
  Send, Plus, Trash2, UserCheck, Shield
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import { Modal } from '../components/Modal';

interface Lead {
  id: string;
  full_name: string;
  email: string;
  phone_number: string;
  status: string;
  
  // Meta Ads Attribution
  campaign_id: string;
  campaign_name: string;
  ad_id: string;
  ad_name: string;
  adset_id: string;
  adset_name: string;
  page_id: string;
  page_name: string;
  form_id: string;
  
  // Medical Context
  medical_interest: string;
  preferred_specialty: string;
  insurance_provider: string;
  preferred_date: string;
  preferred_time: string;
  
  // Management
  assigned_to: string;
  assigned_name: string;
  assigned_email: string;
  notes_count: number;
  
  // Conversion
  converted_to_patient_id: string;
  patient_name: string;
  converted_at: string;
  
  // Metadata
  custom_questions: Record<string, any>;
  attribution_data: Record<string, any>;
  webhook_payload: Record<string, any>;
  
  // Timestamps
  created_at: string;
  updated_at: string;
}

interface StatusHistory {
  id: string;
  old_status: string;
  new_status: string;
  change_reason: string;
  changed_by: string;
  created_at: string;
}

interface Note {
  id: string;
  content: string;
  created_by: string;
  created_by_email: string;
  created_by_name: string;
  created_at: string;
}

interface LeadDetails {
  lead: Lead;
  status_history: StatusHistory[];
  notes: Note[];
}

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800',
  contacted: 'bg-green-100 text-green-800',
  consultation_scheduled: 'bg-purple-100 text-purple-800',
  treatment_planned: 'bg-amber-100 text-amber-800',
  converted: 'bg-emerald-100 text-emerald-800',
  not_interested: 'bg-red-100 text-red-800',
  spam: 'bg-gray-100 text-gray-800',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'Nuevo',
  contacted: 'Contactado',
  consultation_scheduled: 'Consulta Agendada',
  treatment_planned: 'Tratamiento Planificado',
  converted: 'Convertido',
  not_interested: 'No Interesado',
  spam: 'Spam',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  new: <Clock className="w-4 h-4" />,
  contacted: <Phone className="w-4 h-4" />,
  consultation_scheduled: <Calendar className="w-4 h-4" />,
  treatment_planned: <UserCheck className="w-4 h-4" />,
  converted: <CheckCircle2 className="w-4 h-4" />,
  not_interested: <XCircle className="w-4 h-4" />,
  spam: <AlertCircle className="w-4 h-4" />,
};

export default function LeadDetailView() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  // State for lead data
  const [leadDetails, setLeadDetails] = useState<LeadDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for modals
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [showConvertModal, setShowConvertModal] = useState(false);
  
  // State for forms
  const [newStatus, setNewStatus] = useState('');
  const [statusChangeReason, setStatusChangeReason] = useState('');
  const [newNote, setNewNote] = useState('');
  const [newPatientId, setNewPatientId] = useState('');
  
  // State for copying
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadLeadDetails();
    }
  }, [id]);

  const loadLeadDetails = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const { data } = await api.get<LeadDetails>(`/admin/leads/${id}`);
      setLeadDetails(data);
      setNewStatus(data.lead.status);
    } catch (err: any) {
      console.error('Error loading lead details:', err);
      setError(err.response?.data?.detail || 'Error loading lead details');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async () => {
    if (!id || !newStatus) return;
    
    try {
      await api.put(`/admin/leads/${id}/status`, {
        new_status: newStatus,
        change_reason: statusChangeReason,
      });
      
      // Refresh lead details
      loadLeadDetails();
      
      // Close modal and reset form
      setShowStatusModal(false);
      setStatusChangeReason('');
    } catch (err) {
      console.error('Error updating status:', err);
    }
  };

  const handleAddNote = async () => {
    if (!id || !newNote.trim()) return;
    
    try {
      await api.post(`/admin/leads/${id}/notes`, {
        content: newNote,
      });
      
      // Refresh lead details
      loadLeadDetails();
      
      // Close modal and reset form
      setShowNoteModal(false);
      setNewNote('');
    } catch (err) {
      console.error('Error adding note:', err);
    }
  };

  const handleConvertToPatient = async () => {
    if (!id || !newPatientId.trim()) return;
    
    try {
      await api.post(`/admin/leads/${id}/convert`, {
        patient_id: newPatientId,
      });
      
      // Refresh lead details
      loadLeadDetails();
      
      // Close modal and reset form
      setShowConvertModal(false);
      setNewPatientId('');
    } catch (err) {
      console.error('Error converting lead:', err);
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

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 60) {
      return `hace ${diffMins} min`;
    } else if (diffHours < 24) {
      return `hace ${diffHours} h`;
    } else {
      return `hace ${diffDays} días`;
    }
  };

  const getStatusColor = (status: string) => {
    return STATUS_COLORS[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusLabel = (status: string) => {
    return STATUS_LABELS[status] || status;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-6xl mx-auto">
          <button
            onClick={() => navigate('/leads')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('common.back')}
          </button>
          
          <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-red-800 mb-2">{t('common.error')}</h3>
            <p className="text-red-700 mb-4">{error}</p>
            <button
              onClick={loadLeadDetails}
              className="px-4 py-2 bg-red-600 text-white rounded-lg font-bold hover:bg-red-700"
            >
              {t('common.retry')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!leadDetails) {
    return null;
  }

  const { lead, status_history, notes } = leadDetails;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/leads')}
                className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="w-4 h-4" />
                {t('common.back')}
              </button>
              
              <div>
                <h1 className="text-2xl font-black text-gray-900">
                  {lead.full_name || t('leads.unnamed_lead')}
                </h1>
                <p className="text-gray-500">
                  {t('leads.lead_id')}: {lead.id.substring(0, 8)}...
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-2 ${getStatusColor(lead.status)}`}>
                {STATUS_ICONS[lead.status]}
                <span>{getStatusLabel(lead.status)}</span>
              </div>
              
              <button
                onClick={() => setShowStatusModal(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
              >
                <Edit className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Lead Info */}
          <div className="lg:col-span-2 space-y-8">
            {/* Contact Card */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <User className="w-5 h-5 text-blue-600" />
                  {t('leads.contact_information')}
                </h2>
              </div>
              
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Basic Info */}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">
                        {t('leads.full_name')}
                      </label>
                      <div className="font-bold text-gray-900">
                        {lead.full_name || t('leads.not_provided')}
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">
                        {t('leads.phone_number')}
                      </label>
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-gray-900 flex items-center gap-2">
                          <Phone className="w-4 h-4 text-gray-400" />
                          {lead.phone_number || t('leads.not_provided')}
                        </div>
                        {lead.phone_number && (
                          <button
                            onClick={() => copyToClipboard(lead.phone_number, 'phone')}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            {copied === 'phone' ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                          </button>
                        )}
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">
                        {t('leads.email')}
                      </label>
                      <div className="flex items-center justify-between">
                        <div className="font-medium text-gray-900 flex items-center gap-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          {lead.email || t('leads.not_provided')}
                        </div>
                        {lead.email && (
                          <button
                            onClick={() => copyToClipboard(lead.email, 'email')}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            {copied === 'email' ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Medical Info */}
                  <div className="space-y-4">
                    {lead.medical_interest && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.medical_interest')}
                        </label>
                        <div className="font-medium text-gray-900">
                          {lead.medical_interest}
                        </div>
                      </div>
                    )}
                    
                    {lead.preferred_specialty && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.preferred_specialty')}
                        </label>
                        <div className="font-medium text-gray-900">
                          {lead.preferred_specialty}
                        </div>
                      </div>
                    )}
                    
                    {lead.insurance_provider && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.insurance_provider')}
                        </label>
                        <div className="font-medium text-gray-900">
                          {lead.insurance_provider}
                        </div>
                      </div>
                    )}
                    
                    {(lead.preferred_date || lead.preferred_time) && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.preferred_appointment')}
                        </label>
                        <div className="font-medium text-gray-900 flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          {lead.preferred_date} {lead.preferred_time && `a las ${lead.preferred_time}`}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Meta Ads Attribution Card */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <Tag className="w-5 h-5 text-green-600" />
                  {t('leads.meta_ads_attribution')}
                </h2>
              </div>
              
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Campaign Info */}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">
                        {t('leads.campaign')}
                      </label>
                      <div className="font-bold text-gray-900">
                        {lead.campaign_name || t('leads.unknown_campaign')}
                      </div>
                      {lead.campaign_id && (
                        <div className="text-xs text-gray-500 font-mono mt-1">
                          ID: {lead.campaign_id}
                        </div>
                      )}
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-500 mb-1">
                        {t('leads.ad')}
                      </label>
                      <div className="font-medium text-gray-900">
                        {lead.ad_name || t('leads.unknown_ad')}
                      </div>
                      {lead.ad_id && (
                        <div className="text-xs text-gray-500 font-mono mt-1">
                          ID: {lead.ad_id}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Additional Info */}
                  <div className="space-y-4">
                    {lead.adset_name && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.adset')}
                        </label>
                        <div className="font-medium text-gray-900">
                          {lead.adset_name}
                        </div>
                        {lead.adset_id && (
                          <div className="text-xs text-gray-500 font-mono mt-1">
                            ID: {lead.adset_id}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {lead.page_name && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.page')}
                        </label>
                        <div className="font-medium text-gray-900">
                          {lead.page_name}
                        </div>
                        {lead.page_id && (
                          <div className="text-xs text-gray-500 font-mono mt-1">
                            ID: {lead.page_id}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {lead.form_id && (
                      <div>
                        <label className="block text-sm font-medium text-gray-500 mb-1">
                          {t('leads.form_id')}
                        </label>
                        <div className="font-medium text-gray-900 font-mono">
                          {lead.form_id}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Custom Questions */}
                {lead.custom_questions && Object.keys(lead.custom_questions).length > 0 && (
                  <div className="mt-6 pt-6 border-t border-gray-100">
                    <h3 className="text-sm font-bold text-gray-700 mb-3">
                      {t('leads.custom_questions')}
                    </h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                        {JSON.stringify(lead.custom_questions, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Notes Section */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <MessageSquare className="w-5 h-5 text-amber-600" />
                  {t('leads.notes')} ({notes.length})
                </h2>
                <button
                  onClick={() => setShowNoteModal(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg font-bold hover:bg-amber-700"
                >
                  <Plus className="w-4 h-4" />
                  {t('leads.add_note')}
                </button>
              </div>
              
              <div className="p-6">
                {notes.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>{t('leads.no_notes')}</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {notes.map((note) => (
                      <div key={note.id} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                              <span className="text-blue-600 font-bold text-sm">
                                {note.created_by_name?.charAt(0) || 'U'}
                              </span>
                            </div>
                            <div>
                              <div className="font-bold text-gray-900">
                                {note.created_by_name || t('leads.unknown_user')}
                              </div>
                              <div className="text-xs text-gray-500">
                                {formatTimeAgo(note.created_at)} • {formatDate(note.created_at)}
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="text-gray-700 whitespace-pre-wrap">
                          {note.content}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-8">
            {/* Status History */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <History className="w-5 h-5 text-purple-600" />
                  {t('leads.status_history')}
                </h2>
              </div>
              
              <div className="p-6">
                {status_history.length === 0 ? (
                  <div className="text-center py-4 text-gray-500">
                    <p>{t('leads.no_status_history')}</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {status_history.map((history) => (
                      <div key={history.id} className="border-l-2 border-blue-400 pl-4 py-2">
                        <div className="flex items-center gap-2 mb-1">
                          <div className={`px-2 py-1 rounded text-xs font-bold ${getStatusColor(history.new_status)}`}>
                            {getStatusLabel(history.new_status)}
                          </div>
                          <div className="text-xs text-gray-500">
                            {formatTimeAgo(history.created_at)}
                          </div>
                        </div>
                        <div className="text-sm text-gray-700">
                          {history.change_reason || t('leads.no_reason_provided')}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {formatDate(history.created_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <Calendar className="w-5 h-5 text-green-600" />
                  {t('leads.timeline')}
                </h2>
              </div>
              
              <div className="p-6">
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                      <Plus className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <div className="font-bold text-gray-900">{t('leads.lead_created')}</div>
                      <div className="text-sm text-gray-500">{formatDate(lead.created_at)}</div>
                    </div>
                  </div>
                  
                  {lead.updated_at !== lead.created_at && (
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                        <Edit className="w-4 h-4 text-green-600" />
                      </div>
                      <div>
                        <div className="font-bold text-gray-900">{t('leads.last_updated')}</div>
                        <div className="text-sm text-gray-500">{formatDate(lead.updated_at)}</div>
                      </div>
                    </div>
                  )}
                  
                  {lead.converted_at && (
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      </div>
                      <div>
                        <div className="font-bold text-gray-900">{t('leads.converted_to_patient')}</div>
                        <div className="text-sm text-gray-500">{formatDate(lead.converted_at)}</div>
                        {lead.patient_name && (
                          <div className="text-sm text-gray-700 mt-1">
                            {t('leads.patient')}: {lead.patient_name}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900 flex items-center gap-3">
                  <Send className="w-5 h-5 text-indigo-600" />
                  {t('leads.quick_actions')}
                </h2>
              </div>
              
              <div className="p-6 space-y-3">
                <button
                  onClick={() => setShowStatusModal(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
                >
                  <Edit className="w-4 h-4" />
                  {t('leads.change_status')}
                </button>
                
                <button
                  onClick={() => setShowNoteModal(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-600 text-white rounded-lg font-bold hover:bg-amber-700"
                >
                  <MessageSquare className="w-4 h-4" />
                  {t('leads.add_note')}
                </button>
                
                {lead.status !== 'converted' && !lead.converted_to_patient_id && (
                  <button
                    onClick={() => setShowConvertModal(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700"
                  >
                    <UserCheck className="w-4 h-4" />
                    {t('leads.convert_to_patient')}
                  </button>
                )}
                
                {lead.phone_number && (
                  <a
                    href={`tel:${lead.phone_number}`}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg font-bold hover:bg-green-700"
                  >
                    <Phone className="w-4 h-4" />
                    {t('leads.call_lead')}
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status Update Modal */}
      <Modal
        isOpen={showStatusModal}
        onClose={() => {
          setShowStatusModal(false);
          setStatusChangeReason('');
        }}
        title={t('leads.update_status')}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('leads.new_status')}
            </label>
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('leads.reason_for_change')} ({t('common.optional')})
            </label>
            <textarea
              value={statusChangeReason}
              onChange={(e) => setStatusChangeReason(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder={t('leads.reason_placeholder')}
            />
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => {
                setShowStatusModal(false);
                setStatusChangeReason('');
              }}
              className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg font-medium hover:bg-gray-200"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleUpdateStatus}
              disabled={!newStatus}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('leads.update')}
            </button>
          </div>
        </div>
      </Modal>

      {/* Add Note Modal */}
      <Modal
        isOpen={showNoteModal}
        onClose={() => {
          setShowNoteModal(false);
          setNewNote('');
        }}
        title={t('leads.add_note')}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('leads.note_content')}
            </label>
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder={t('leads.note_placeholder')}
            />
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => {
                setShowNoteModal(false);
                setNewNote('');
              }}
              className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg font-medium hover:bg-gray-200"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleAddNote}
              disabled={!newNote.trim()}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg font-bold hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('leads.add_note')}
            </button>
          </div>
        </div>
      </Modal>

      {/* Convert to Patient Modal */}
      <Modal
        isOpen={showConvertModal}
        onClose={() => {
          setShowConvertModal(false);
          setNewPatientId('');
        }}
        title={t('leads.convert_to_patient')}
      >
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-blue-600 mt-0.5" />
              <div>
                <p className="text-blue-800 font-medium">
                  {t('leads.conversion_warning_title')}
                </p>
                <p className="text-blue-700 text-sm mt-1">
                  {t('leads.conversion_warning_description')}
                </p>
              </div>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('leads.patient_id')}
            </label>
            <input
              type="text"
              value={newPatientId}
              onChange={(e) => setNewPatientId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder={t('leads.patient_id_placeholder')}
            />
            <p className="text-xs text-gray-500 mt-1">
              {t('leads.patient_id_help')}
            </p>
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => {
                setShowConvertModal(false);
                setNewPatientId('');
              }}
              className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg font-medium hover:bg-gray-200"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleConvertToPatient}
              disabled={!newPatientId.trim()}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('leads.convert')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}