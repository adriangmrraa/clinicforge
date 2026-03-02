import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, Search, Filter, Calendar, Phone, Mail, MessageSquare,
  CheckCircle2, Clock, XCircle, AlertCircle, UserPlus, Edit,
  ChevronRight, ChevronLeft, Download, RefreshCw, BarChart3,
  Eye, MoreVertical, Tag, UserCheck, ArrowUpDown
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

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'new', label: 'Nuevo', color: 'bg-blue-100 text-blue-800' },
  { value: 'contacted', label: 'Contactado', color: 'bg-green-100 text-green-800' },
  { value: 'consultation_scheduled', label: 'Consulta Agendada', color: 'bg-purple-100 text-purple-800' },
  { value: 'treatment_planned', label: 'Tratamiento Planificado', color: 'bg-amber-100 text-amber-800' },
  { value: 'converted', label: 'Convertido', color: 'bg-emerald-100 text-emerald-800' },
  { value: 'not_interested', label: 'No Interesado', color: 'bg-red-100 text-red-800' },
  { value: 'spam', label: 'Spam', color: 'bg-gray-100 text-gray-800' },
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
    const option = STATUS_OPTIONS.find(opt => opt.value === status);
    return option?.label || status;
  };

  const getStatusColor = (status: string) => {
    const option = STATUS_OPTIONS.find(opt => opt.value === status);
    return option?.color || 'bg-gray-100 text-gray-800';
  };

  // Calculate pagination
  const totalPages = Math.ceil(totalLeads / pageSize);
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalLeads);

  return (
    <div className="min-h-screen bg-gray-50">
      <PageHeader
        title={t('leads.page_title')}
        subtitle={t('leads.page_subtitle')}
        icon={<Users className="w-6 h-6" />}
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50"
            >
              <Filter className="w-4 h-4" />
              {t('leads.filters')}
            </button>
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50"
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.total')}</p>
                  <p className="text-2xl font-black text-gray-900">{summary.totals.total_leads}</p>
                </div>
                <Users className="w-8 h-8 text-blue-500" />
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.converted')}</p>
                  <p className="text-2xl font-black text-green-600">{summary.totals.converted_leads}</p>
                </div>
                <CheckCircle2 className="w-8 h-8 text-green-500" />
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.conversion_rate')}</p>
                  <p className="text-2xl font-black text-indigo-600">{summary.totals.conversion_rate}%</p>
                </div>
                <BarChart3 className="w-8 h-8 text-indigo-500" />
              </div>
            </div>
            
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500 font-medium">{t('leads.stats.active')}</p>
                  <p className="text-2xl font-black text-amber-600">{summary.totals.active_leads}</p>
                </div>
                <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                  <span className="text-amber-600 font-bold">!</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters Panel */}
      {showFilters && (
        <div className="px-6 pb-6">
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900">{t('leads.filter_leads')}</h3>
              <button
                onClick={() => setShowFilters(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ×
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Status Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('leads.status')}
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {STATUS_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              
              {/* Date From */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('leads.date_from')}
                </label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              {/* Date To */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('leads.date_to')}
                </label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              {/* Campaign Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('leads.campaign')}
                </label>
                <select
                  value={campaignFilter}
                  onChange={(e) => setCampaignFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder={t('leads.search_placeholder')}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          {/* Table Header */}
          <div className="p-6 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-gray-900">{t('leads.leads_list')}</h3>
                <p className="text-sm text-gray-500">
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
              <h3 className="text-lg font-bold text-gray-800 mb-2">{t('common.error')}</h3>
              <p className="text-gray-600 mb-4">{error}</p>
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
              <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-gray-800 mb-2">{t('leads.no_leads')}</h3>
              <p className="text-gray-600 mb-4">{t('leads.no_leads_description')}</p>
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
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.lead')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.contact')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.campaign')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.status')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.date')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {t('leads.actions')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {leads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-gray-50">
                        {/* Lead Info */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                              <span className="text-blue-600 font-bold">
                                {lead.full_name?.charAt(0) || '?'}
                              </span>
                            </div>
                            <div>
                              <div className="font-bold text-gray-900">{lead.full_name || t('leads.unnamed')}</div>
                              {lead.medical_interest && (
                                <div className="text-xs text-gray-500">{lead.medical_interest}</div>
                              )}
                            </div>
                          </div>
                        </td>
                        
                        {/* Contact Info */}
                        <td className="px-6 py-4">
                          <div className="space-y-1">
                            {lead.phone_number && (
                              <div className="flex items-center gap-2 text-sm">
                                <Phone className="w-3 h-3 text-gray-400" />
                                <span className="text-gray-700">{lead.phone_number}</span>
                              </div>
                            )}
                            {lead.email && (
                              <div className="flex items-center gap-2 text-sm">
                                <Mail className="w-3 h-3 text-gray-400" />
                                <span className="text-gray-700">{lead.email}</span>
                              </div>
                            )}
                          </div>
                        </td>
                        
                        {/* Campaign Info */}
                        <td className="px-6 py-4">
                          <div className="space-y-1">
                            <div className="font-medium text-gray-900">{lead.campaign_name || t('leads.no_campaign')}</div>
                            {lead.ad_name && (
                              <div className="text-xs text-gray-500">{lead.ad_name}</div>
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
                          <div className="text-sm text-gray-700">
                            {formatDate(lead.created_at)}
                          </div>
                          <div className="text-xs text-gray-500">
                            {formatDateTime(lead.created_at)}
                          </div>
                        </td>
                        
                        {/* Actions */}
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleViewLead(lead.id)}
                              className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
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
                              className="p-2 text-gray-600 hover:text-green-600 hover:bg-green-50 rounded-lg"
                              title={t('leads.change_status')}
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            
                            {lead.status !== 'converted' && !lead.converted_to_patient_id && (
                              <button
                                onClick={() => handleConvertToPatient(lead.id)}
                                className="p-2 text-gray-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg"
                                title={t('leads.convert_to_patient')}
                              >
                                <UserPlus className="w-4 h-4" />
                              </button>
                            )}
                            
                            {lead.notes_count > 0 && (
                              <div className="flex items-center gap-1 text-xs text-gray-500">
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
              <div className="lg:hidden divide-y divide-gray-100">
                {leads.map((lead) => (
                  <div key={lead.id} className="p-5 hover:bg-gray-50">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <span className="text-blue-600 font-bold">
                            {lead.full_name?.charAt(0) || '?'}
                          </span>
                        </div>
                        <div>
                          <div className="font-bold text-gray-900">{lead.full_name || t('leads.unnamed')}</div>
                          <div className="text-xs text-gray-500">{formatDate(lead.created_at)}</div>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded-full text-xs font-bold ${getStatusColor(lead.status)}`}>
                        {getStatusLabel(lead.status)}
                      </div>
                    </div>
                    
                    <div className="space-y-2 mb-3">
                      {lead.phone_number && (
                        <div className="flex items-center gap-2 text-sm">
                          <Phone className="w-3 h-3 text-gray-400" />
                          <span className="text-gray-700">{lead.phone_number}</span>
                        </div>
                      )}
                      
                      {lead.email && (
                        <div className="flex items-center gap-2 text-sm">
                          <Mail className="w-3 h-3 text-gray-400" />
                          <span className="text-gray-700">{lead.email}</span>
                        </div>
                      )}
                      
                      {lead.campaign_name && (
                        <div className="flex items-center gap-2 text-sm">
                          <Tag className="w-3 h-3 text-gray-400" />
                          <span className="text-gray-700">{lead.campaign_name}</span>
                        </div>
                      )}
                      
                      {lead.medical_interest && (
                        <div className="text-sm text-gray-600">
                          <span className="font-medium">Interés:</span> {lead.medical_interest}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleViewLead(lead.id)}
                          className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg"
                        >
                          {t('leads.view')}
                        </button>
                        
                        <button
                          onClick={() => {
                            setSelectedLead(lead);
                            setNewStatus(lead.status);
                            setShowStatusModal(true);
                          }}
                          className="px-3 py-1 text-sm text-green-600 hover:bg-green-50 rounded-lg"
                        >
                          {t('leads.edit_status')}
                        </button>
                      </div>
                      
                      {lead.notes_count > 0 && (
                        <div className="flex items-center gap-1 text-xs text-gray-500">
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
                <div className="px-6 py-4 border-t border-gray-100">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-500">
                      {t('leads.page')} {currentPage} {t('leads.of')} {totalPages}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                        disabled={currentPage === 1}
                        className="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
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
                                : 'text-gray-600 hover:bg-gray-100'
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                      
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                        disabled={currentPage === totalPages}
                        className="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">{t('leads.items_per_page')}:</span>
                      <select
                        value={pageSize}
                        onChange={(e) => {
                          setPageSize(Number(e.target.value));
                          setCurrentPage(1);
                        }}
                        className="px-2 py-1 border border-gray-300 rounded text-sm"
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
        </div>
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
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="font-bold text-gray-900">{selectedLead.full_name || t('leads.unnamed')}</div>
              <div className="text-sm text-gray-500">
                {selectedLead.phone_number} • {selectedLead.email}
              </div>
              <div className="text-sm text-gray-500 mt-1">
                {t('leads.current_status')}: <span className="font-bold">{getStatusLabel(selectedLead.status)}</span>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('leads.new_status')}
              </label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {STATUS_OPTIONS.filter(opt => opt.value).map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
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
                  setSelectedLead(null);
                  setNewStatus('');
                  setStatusChangeReason('');
                }}
                className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg font-medium hover:bg-gray-200"
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