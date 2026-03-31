import React, { useState, useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useNavigate } from 'react-router-dom';
import {
  Users, Search, Filter, Calendar, Phone, Mail, MessageSquare,
  CheckCircle2, Clock, XCircle, AlertCircle, UserPlus, Edit,
  ChevronRight, ChevronLeft, Download, RefreshCw, BarChart3,
  Eye, MoreVertical, Tag, UserCheck, ArrowUpDown
} from 'lucide-react';
import api, { WS_URL } from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import { Modal } from '../components/Modal';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

interface Lead {
  id: string;
  full_name: string;
  email: string;
  phone_number: string;
  status: string;
  campaign_name: string;
  ad_name: string;
  created_at: string;
  assigned_name: string;
  assigned_email: string;
  medical_interest: string;
  notes_count: number;
  converted_to_patient_id: string | null;
  patient_name: string | null;
}

interface LeadsResponse {
  leads: Lead[];
  total: number;
  limit: number;
  offset: number;
}

interface StatusCount {
  status: string;
  count: number;
}

interface LeadsSummary {
  totals: {
    total_leads: number;
    converted_leads: number;
    conversion_rate: number;
    active_leads: number;
  };
  by_status: StatusCount[];
  by_campaign: Array<{
    campaign_id: string;
    campaign_name: string;
    total_leads: number;
    converted_leads: number;
    conversion_rate: number;
  }>;
}

const getStatusOptions = (t: any) => [
  { value: '', label: t('leads.status_all') },
  { value: 'new', label: t('leads.status_new'), color: 'bg-blue-500/10 text-blue-400' },
  { value: 'contacted', label: t('leads.status_contacted'), color: 'bg-green-500/10 text-green-400' },
  { value: 'consultation_scheduled', label: t('leads.status_consultation_scheduled'), color: 'bg-purple-500/10 text-purple-400' },
  { value: 'treatment_planned', label: t('leads.status_treatment_planned'), color: 'bg-amber-500/10 text-amber-400' },
  { value: 'converted', label: t('leads.status_converted'), color: 'bg-emerald-500/10 text-emerald-400' },
  { value: 'not_interested', label: t('leads.status_not_interested'), color: 'bg-red-500/10 text-red-400' },
  { value: 'spam', label: t('leads.status_spam'), color: 'bg-white/[0.06] text-white/60' },
];

const STATUS_ICONS: Record<string, React.ReactNode> = {
  new: <Clock className="w-4 h-4" />,
  contacted: <Phone className="w-4 h-4" />,
  consultation_scheduled: <Calendar className="w-4 h-4" />,
  treatment_planned: <UserCheck className="w-4 h-4" />,
  converted: <CheckCircle2 className="w-4 h-4" />,
  not_interested: <XCircle className="w-4 h-4" />,
  spam: <AlertCircle className="w-4 h-4" />,
};

export default function LeadsManagementView() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  // State for leads data
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for filters
  const [statusFilter, setStatusFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [campaignFilter, setCampaignFilter] = useState('');
  
  // State for pagination
  const [totalLeads, setTotalLeads] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  // State for summary stats
  const [summary, setSummary] = useState<LeadsSummary | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  
  // State for modals
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [newStatus, setNewStatus] = useState('');
  const [statusChangeReason, setStatusChangeReason] = useState('');
  const socketRef = useRef<Socket | null>(null);

  // WebSocket Connection
  useEffect(() => {
    socketRef.current = io(WS_URL);

    socketRef.current.on('NEW_PATIENT', () => {
      loadLeads();
      loadSummary();
    });

    return () => {
      if (socketRef.current) socketRef.current.disconnect();
    };
  }, []);

  // Load leads on mount and when filters change
  useEffect(() => {
    loadLeads();
    loadSummary();
  }, [currentPage, statusFilter, campaignFilter, dateFrom, dateTo]);

  const loadLeads = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((currentPage - 1) * pageSize).toString(),
      });
      
      if (statusFilter) params.append('status', statusFilter);
      if (campaignFilter) params.append('campaign_id', campaignFilter);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      
      const { data } = await api.get<LeadsResponse>(`/admin/leads?${params}`);
      
      setLeads(data.leads);
      setTotalLeads(data.total);
    } catch (err: any) {
      console.error('Error loading leads:', err);
      setError(err.response?.data?.detail || 'Error loading leads');
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      
      const { data } = await api.get<LeadsSummary>(`/admin/leads/stats/summary?${params}`);
      setSummary(data);
    } catch (err) {
      console.error('Error loading summary:', err);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // Implement search functionality
    console.log('Searching for:', searchTerm);
  };

  const handleStatusUpdate = async () => {
    if (!selectedLead || !newStatus) return;
    
    try {
      await api.put(`/admin/leads/${selectedLead.id}/status`, {
        new_status: newStatus,
        change_reason: statusChangeReason,
      });
      
      // Refresh leads
      loadLeads();
      loadSummary();
      
      // Close modal
      setShowStatusModal(false);
      setSelectedLead(null);
      setNewStatus('');
      setStatusChangeReason('');
    } catch (err) {
      console.error('Error updating status:', err);
    }
  };

  const handleExport = () => {
    // Implement export functionality
    console.log('Exporting leads...');
  };

  const handleViewLead = (leadId: string) => {
    navigate(`/leads/${leadId}`);
  };

  const handleConvertToPatient = (leadId: string) => {
    // Implement conversion functionality
    console.log('Converting lead:', leadId);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusLabel = (status: string) => {
    return t(`leads.status_${status || 'all'}`);
  };

  const getStatusColor = (status: string) => {
    const ST_OPTIONS = getStatusOptions(t);
    const option = ST_OPTIONS.find(opt => opt.value === status);
    return option?.color || 'bg-white/[0.06] text-white/60';
  };

  // Calculate pagination
  const totalPages = Math.ceil(totalLeads / pageSize);
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalLeads);

  return (
    <div className="min-h-screen">
      <PageHeader
        title={t('leads.page_title')}
        subtitle={t('leads.page_subtitle')}
        icon={<Users className="w-6 h-6" />}
        action={
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-4 py-2 bg-white/[0.06] border border-white/[0.06] rounded-lg text-white/70 font-medium hover:bg-white/[0.04]"
            >
              <Filter className="w-4 h-4" />
              {t('leads.filters')}
            </button>
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 bg-white/[0.06] border border-white/[0.06] rounded-lg text-white/70 font-medium hover:bg-white/[0.04]"
            >
              <Download className="w-4 h-4" />
              {t('leads.export')}
            </button>
            <button
              onClick={loadLeads}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
            >
              <RefreshCw className="w-4 h-4" />
              {t('common.refresh')}
            </button>
          </div>
        }
      />

      {/* Summary Stats */}
      {summary && (
        <div className="px-6 pb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <GlassCard image={CARD_IMAGES.leads}>
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/40 font-medium">{t('leads.stats.total')}</p>
                    <p className="text-lg sm:text-2xl font-black text-white">{summary.totals.total_leads}</p>
                  </div>
                  <Users className="w-8 h-8 text-blue-500" />
                </div>
              </div>
            </GlassCard>

            <GlassCard image={CARD_IMAGES.leads}>
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/40 font-medium">{t('leads.stats.converted')}</p>
                    <p className="text-lg sm:text-2xl font-black text-green-600">{summary.totals.converted_leads}</p>
                  </div>
                  <CheckCircle2 className="w-8 h-8 text-green-500" />
                </div>
              </div>
            </GlassCard>

            <GlassCard image={CARD_IMAGES.leads}>
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/40 font-medium">{t('leads.stats.conversion_rate')}</p>
                    <p className="text-lg sm:text-2xl font-black text-indigo-600">{summary.totals.conversion_rate}%</p>
                  </div>
                  <BarChart3 className="w-8 h-8 text-indigo-500" />
                </div>
              </div>
            </GlassCard>

            <GlassCard image={CARD_IMAGES.leads}>
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/40 font-medium">{t('leads.stats.active')}</p>
                    <p className="text-lg sm:text-2xl font-black text-amber-600">{summary.totals.active_leads}</p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center">
                    <span className="text-amber-600 font-bold">!</span>
                  </div>
                </div>
              </div>
            </GlassCard>
          </div>
        </div>
      )}

      {/* Filters Panel */}
      {showFilters && (
        <div className="px-6 pb-6">
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-white">{t('leads.filter_leads')}</h3>
              <button
                onClick={() => setShowFilters(false)}
                className="text-white/40 hover:text-white/60"
              >
                ×
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Status Filter */}
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  {t('leads.status')}
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {getStatusOptions(t).map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* Date From */}
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  {t('leads.date_from')}
                </label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              {/* Date To */}
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  {t('leads.date_to')}
                </label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              {/* Campaign Filter */}
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  {t('leads.campaign')}
                </label>
                <select
                  value={campaignFilter}
                  onChange={(e) => setCampaignFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">{t('leads.all_campaigns')}</option>
                  {summary?.by_campaign.map(campaign => (
                    <option key={campaign.campaign_id} value={campaign.campaign_id}>
                      {campaign.campaign_name} ({campaign.total_leads})
                    </option>
                  ))}
                </select>
              </div>
            </div>
            
            {/* Search */}
            <div className="mt-4">
              <form onSubmit={handleSearch} className="flex gap-2">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-white/30 w-5 h-5" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder={t('leads.search_placeholder')}
                    className="w-full pl-10 pr-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
                >
                  {t('leads.search')}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="px-6">
        <GlassCard image={CARD_IMAGES.leads} hoverScale={false} className="overflow-hidden">
          {/* Table Header */}
          <div className="p-6 border-b border-white/[0.06]">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">{t('leads.leads_list')}</h3>
                <p className="text-sm text-white/40">
                  {t('leads.showing')} {startItem}-{endItem} {t('leads.of')} {totalLeads} {t('leads.leads')}
                </p>
              </div>
              
              {/* Status Distribution */}
              <div className="hidden md:flex items-center gap-2">
                {summary?.by_status.slice(0, 5).map(status => (
                  <div
                    key={status.status}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium"
                    style={{ backgroundColor: `${getStatusColor(status.status).split(' ')[0]}20` }}
                  >
                    <span className={getStatusColor(status.status).split(' ')[1]}>
                      {getStatusLabel(status.status)}: {status.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="p-8 text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">{t('common.error')}</h3>
              <p className="text-white/60 mb-4">{error}</p>
              <button
                onClick={loadLeads}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
              >
                {t('common.retry')}
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && leads.length === 0 && (
            <div className="p-8 text-center">
              <Users className="w-12 h-12 text-white/30 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">{t('leads.no_leads')}</h3>
              <p className="text-white/60 mb-4">{t('leads.no_leads_description')}</p>
              <a
                href="/configuracion?tab=leads"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700"
              >
                <MessageSquare className="w-4 h-4" />
                {t('leads.configure_webhook')}
              </a>
            </div>
          )}

          {/* Leads Table */}
          {!loading && !error && leads.length > 0 && (
            <>
              {/* Desktop Table */}
              <div className="hidden lg:block overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-white/[0.02]">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.lead')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.contact')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.campaign')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.status')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.date')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-white/40 uppercase tracking-wider">
                        {t('leads.actions')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.06]">
                    {leads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-white/[0.04]">
                        {/* Lead Info */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                              <span className="text-blue-600 font-bold">
                                {lead.full_name?.charAt(0) || '?'}
                              </span>
                            </div>
                            <div>
                              <div className="font-bold text-white">{lead.full_name || t('leads.unnamed')}</div>
                              {lead.medical_interest && (
                                <div className="text-xs text-white/40">{lead.medical_interest}</div>
                              )}
                            </div>
                          </div>
                        </td>
                        
                        {/* Contact Info */}
                        <td className="px-6 py-4">
                          <div className="space-y-1">
                            {lead.phone_number && (
                              <div className="flex items-center gap-2 text-sm">
                                <Phone className="w-3 h-3 text-white/30" />
                                <span className="text-white/60">{lead.phone_number}</span>
                              </div>
                            )}
                            {lead.email && (
                              <div className="flex items-center gap-2 text-sm">
                                <Mail className="w-3 h-3 text-white/30" />
                                <span className="text-white/60">{lead.email}</span>
                              </div>
                            )}
                          </div>
                        </td>
                        
                        {/* Campaign Info */}
                        <td className="px-6 py-4">
                          <div className="space-y-1">
                            <div className="font-medium text-white">{lead.campaign_name || t('leads.no_campaign')}</div>
                            {lead.ad_name && (
                              <div className="text-xs text-white/40">{lead.ad_name}</div>
                            )}
                          </div>
                        </td>
                        
                        {/* Status */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className={`px-3 py-1 rounded-full text-xs font-bold ${getStatusColor(lead.status)}`}>
                              {STATUS_ICONS[lead.status] || <Clock className="w-3 h-3" />}
                              <span className="ml-1">{getStatusLabel(lead.status)}</span>
                            </div>
                          </div>
                        </td>
                        
                        {/* Date */}
                        <td className="px-6 py-4">
                          <div className="text-sm text-white/60">
                            {formatDate(lead.created_at)}
                          </div>
                          <div className="text-xs text-white/40">
                            {formatDateTime(lead.created_at)}
                          </div>
                        </td>
                        
                        {/* Actions */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleViewLead(lead.id)}
                              className="p-2 text-white/60 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg"
                              title={t('leads.view_details')}
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                            
                            <button
                              onClick={() => {
                                setSelectedLead(lead);
                                setNewStatus(lead.status);
                                setShowStatusModal(true);
                              }}
                              className="p-2 text-white/60 hover:text-green-400 hover:bg-green-500/10 rounded-lg"
                              title={t('leads.change_status')}
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            
                            {lead.status !== 'converted' && !lead.converted_to_patient_id && (
                              <button
                                onClick={() => handleConvertToPatient(lead.id)}
                                className="p-2 text-white/60 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg"
                                title={t('leads.convert_to_patient')}
                              >
                                <UserPlus className="w-4 h-4" />
                              </button>
                            )}
                            
                            {lead.notes_count > 0 && (
                              <div className="flex items-center gap-1 text-xs text-white/40">
                                <MessageSquare className="w-3 h-3" />
                                <span>{lead.notes_count}</span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Cards */}
              <div className="lg:hidden divide-y divide-white/[0.06]">
                {leads.map((lead) => (
                  <div key={lead.id} className="p-5 hover:bg-white/[0.04]">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                          <span className="text-blue-600 font-bold">
                            {lead.full_name?.charAt(0) || '?'}
                          </span>
                        </div>
                        <div>
                          <div className="font-bold text-white">{lead.full_name || t('leads.unnamed')}</div>
                          <div className="text-xs text-white/40">{formatDate(lead.created_at)}</div>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded-full text-xs font-bold ${getStatusColor(lead.status)}`}>
                        {getStatusLabel(lead.status)}
                      </div>
                    </div>
                    
                    <div className="space-y-2 mb-3">
                      {lead.phone_number && (
                        <div className="flex items-center gap-2 text-sm">
                          <Phone className="w-3 h-3 text-white/30" />
                          <span className="text-white/60">{lead.phone_number}</span>
                        </div>
                      )}
                      
                      {lead.email && (
                        <div className="flex items-center gap-2 text-sm">
                          <Mail className="w-3 h-3 text-white/30" />
                          <span className="text-white/60">{lead.email}</span>
                        </div>
                      )}
                      
                      {lead.campaign_name && (
                        <div className="flex items-center gap-2 text-sm">
                          <Tag className="w-3 h-3 text-white/30" />
                          <span className="text-white/60">{lead.campaign_name}</span>
                        </div>
                      )}
                      
                      {lead.medical_interest && (
                        <div className="text-sm text-white/60">
                          <span className="font-medium">Interés:</span> {lead.medical_interest}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleViewLead(lead.id)}
                          className="px-3 py-1 text-sm text-blue-400 hover:bg-blue-500/10 rounded-lg"
                        >
                          {t('leads.view')}
                        </button>
                        
                        <button
                          onClick={() => {
                            setSelectedLead(lead);
                            setNewStatus(lead.status);
                            setShowStatusModal(true);
                          }}
                          className="px-3 py-1 text-sm text-green-400 hover:bg-green-500/10 rounded-lg"
                        >
                          {t('leads.edit_status')}
                        </button>
                      </div>
                      
                      {lead.notes_count > 0 && (
                        <div className="flex items-center gap-1 text-xs text-white/40">
                          <MessageSquare className="w-3 h-3" />
                          <span>{lead.notes_count}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-6 py-4 border-t border-white/[0.06]">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-white/40">
                      {t('leads.page')} {currentPage} {t('leads.of')} {totalPages}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                        disabled={currentPage === 1}
                        className="p-2 text-white/60 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="w-5 h-5" />
                      </button>
                      
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        let pageNum;
                        if (totalPages <= 5) {
                          pageNum = i + 1;
                        } else if (currentPage <= 3) {
                          pageNum = i + 1;
                        } else if (currentPage >= totalPages - 2) {
                          pageNum = totalPages - 4 + i;
                        } else {
                          pageNum = currentPage - 2 + i;
                        }
                        
                        return (
                          <button
                            key={pageNum}
                            onClick={() => setCurrentPage(pageNum)}
                            className={`w-8 h-8 rounded-lg font-medium ${
                              currentPage === pageNum
                                ? 'bg-blue-600 text-white'
                                : 'text-white/60 hover:bg-white/[0.04]'
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                      
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                        disabled={currentPage === totalPages}
                        className="p-2 text-white/60 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-white/40">{t('leads.items_per_page')}:</span>
                      <select
                        value={pageSize}
                        onChange={(e) => {
                          setPageSize(Number(e.target.value));
                          setCurrentPage(1);
                        }}
                        className="px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-sm text-white"
                      >
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </GlassCard>
      </div>

      {/* Status Update Modal */}
      <Modal
        isOpen={showStatusModal}
        onClose={() => {
          setShowStatusModal(false);
          setSelectedLead(null);
          setNewStatus('');
          setStatusChangeReason('');
        }}
        title={t('leads.update_status')}
      >
        {selectedLead && (
          <div className="space-y-4">
            <div className="bg-white/[0.02] p-4 rounded-lg">
              <div className="font-bold text-white">{selectedLead.full_name || t('leads.unnamed')}</div>
              <div className="text-sm text-white/40">
                {selectedLead.phone_number} • {selectedLead.email}
              </div>
              <div className="text-sm text-white/40 mt-1">
                {t('leads.current_status')}: <span className="font-bold">{getStatusLabel(selectedLead.status)}</span>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/60 mb-2">
                {t('leads.new_status')}
              </label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {getStatusOptions(t).filter(opt => opt.value).map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/60 mb-2">
                {t('leads.reason_for_change')} ({t('common.optional')})
              </label>
              <textarea
                value={statusChangeReason}
                onChange={(e) => setStatusChangeReason(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder={t('leads.reason_placeholder')}
              />
            </div>
            
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={() => {
                  setShowStatusModal(false);
                  setSelectedLead(null);
                  setNewStatus('');
                  setStatusChangeReason('');
                }}
                className="px-4 py-2 text-white/70 bg-white/[0.06] rounded-lg font-medium hover:bg-white/[0.04]"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleStatusUpdate}
                disabled={!newStatus}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('leads.update')}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}