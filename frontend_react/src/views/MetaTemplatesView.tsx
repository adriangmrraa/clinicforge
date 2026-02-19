import React, { useState, useEffect } from 'react';
import {
    Layout,
    MessageSquare,
    Send,
    BarChart3,
    Clock,
    CheckCircle2,
    ChevronRight,
    AlertCircle,
    Activity,
    Globe,
    History,
    RefreshCw,
    ShieldCheck
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface AutomationLog {
    id: number;
    patient_name: string;
    trigger_type: string;
    status: 'sent' | 'failed' | 'delivered' | 'read';
    created_at: string;
    error_details?: string;
}

const MetaTemplatesView: React.FC = () => {
    const { t } = useTranslation();
    const [logs, setLogs] = useState<AutomationLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [timezone, setTimezone] = useState('America/Argentina/Buenos_Aires');

    const fetchLogs = async () => {
        try {
            setRefreshing(true);
            const res = await api.get('/admin/marketing/automation-logs');
            setLogs(res.data);
        } catch (err) {
            console.error("Error fetching logs:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchLogs();
    }, []);

    const triggerLabels: Record<string, string> = {
        'appointment_reminder': 'Recordatorio 24h',
        'appointment_feedback': 'Feedback Post-Cita',
        'lead_recovery': 'Recuperación de Lead'
    };

    const statusColors: Record<string, string> = {
        'sent': 'bg-blue-100 text-blue-700',
        'failed': 'bg-red-100 text-red-700',
        'delivered': 'bg-green-100 text-green-700',
        'read': 'bg-purple-100 text-purple-700'
    };

    return (
        <div className="flex flex-col h-full bg-gray-50 overflow-hidden">
            {/* Header */}
            <header className="bg-white border-b px-6 py-4 flex items-center justify-between shrink-0 shadow-sm z-10">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-2 rounded-lg shadow-md">
                        <Layout className="text-white" size={24} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-gray-900">Automatizaciones & HSM</h1>
                        <p className="text-xs text-gray-500 font-medium">WhatsApp Marketing & ROI Forge</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg text-xs font-semibold text-gray-600 border border-gray-200">
                        <Globe size={14} className="text-gray-400" />
                        {timezone}
                    </div>
                    <button
                        onClick={fetchLogs}
                        disabled={refreshing}
                        className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                    >
                        <RefreshCw size={20} className={refreshing ? 'animate-spin' : ''} />
                    </button>
                </div>
            </header>

            {/* Content Area */}
            <div className="flex-1 min-h-0 overflow-y-auto p-6">
                <div className="max-w-6xl mx-auto space-y-6">

                    {/* Hero Integration Status */}
                    <div className="grid md:grid-cols-3 gap-6">
                        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-start gap-4">
                            <div className="bg-green-100 p-3 rounded-xl">
                                <ShieldCheck className="text-green-600" size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-900">Motor Activo</h3>
                                <p className="text-xs text-gray-500">Escaneando citas y leads cada 15 min.</p>
                                <span className="mt-2 inline-block px-2 py-0.5 bg-green-50 text-green-600 text-[10px] font-bold rounded uppercase">Operacional</span>
                            </div>
                        </div>
                        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-start gap-4">
                            <div className="bg-blue-100 p-3 rounded-xl">
                                <Send className="text-blue-600" size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-900">HSM Enviados</h3>
                                <p className="text-2xl font-black text-gray-900">{logs.filter(l => l.status === 'sent').length}</p>
                                <p className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">Últimas 24 horas</p>
                            </div>
                        </div>
                        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-start gap-4">
                            <div className="bg-purple-100 p-3 rounded-xl">
                                <Activity className="text-purple-600" size={24} />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-900">Conversión</h3>
                                <p className="text-2xl font-black text-gray-900">85%</p>
                                <p className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">Tasa de Entrega</p>
                            </div>
                        </div>
                    </div>

                    <div className="grid lg:grid-cols-3 gap-6">
                        {/* Audit Log Table */}
                        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                            <div className="px-6 py-4 border-b flex items-center justify-between bg-gray-50/50">
                                <div className="flex items-center gap-2">
                                    <History size={18} className="text-gray-500" />
                                    <h3 className="font-bold text-gray-900">Feed de Transparencia</h3>
                                </div>
                                <span className="text-[10px] font-bold text-gray-400 uppercase">Tiempo Real</span>
                            </div>

                            <div className="flex-1 overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="bg-gray-50 text-[10px] uppercase tracking-widest text-gray-400 font-black">
                                            <th className="px-6 py-3 border-b">Paciente</th>
                                            <th className="px-6 py-3 border-b">Trigger</th>
                                            <th className="px-6 py-3 border-b">Fecha/Hora</th>
                                            <th className="px-6 py-3 border-b">Estado</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                        {loading ? (
                                            Array(5).fill(0).map((_, i) => (
                                                <tr key={i} className="animate-pulse">
                                                    <td colSpan={4} className="px-6 py-4 h-12 bg-gray-50/50"></td>
                                                </tr>
                                            ))
                                        ) : logs.length > 0 ? (
                                            logs.map((log) => (
                                                <tr key={log.id} className="hover:bg-gray-50/80 transition-colors group">
                                                    <td className="px-6 py-4">
                                                        <div className="font-bold text-gray-900 text-sm">{log.patient_name}</div>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-1 rounded inline-block">
                                                            {triggerLabels[log.trigger_type] || log.trigger_type}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="text-xs text-gray-500 font-medium">
                                                            {new Date(log.created_at).toLocaleString('es-AR', {
                                                                day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                                                            })}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <span className={`text-[10px] font-black uppercase px-2 py-1 rounded-full ${statusColors[log.status] || 'bg-gray-100'}`}>
                                                            {log.status}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={4} className="px-6 py-12 text-center text-gray-400 flex flex-col items-center gap-2">
                                                    <AlertCircle size={32} />
                                                    <p className="font-medium italic">No hay logs de automatización disponibles aún.</p>
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Sidebar: Config & Info */}
                        <div className="space-y-6">
                            {/* Timezone Config */}
                            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                                <div className="flex items-center gap-2 mb-4">
                                    <Globe size={18} className="text-blue-600" />
                                    <h4 className="font-bold text-gray-900">Configuración Regional</h4>
                                </div>
                                <p className="text-xs text-gray-500 mb-4 leading-relaxed">
                                    Asegúrate de que la zona horaria coincida con la ubicación de tu clínica para que los recordatorios lleguen a tiempo.
                                </p>
                                <select
                                    value={timezone}
                                    onChange={(e) => setTimezone(e.target.value)}
                                    className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm font-bold text-gray-700 outline-none focus:ring-2 focus:ring-blue-500 transition-all cursor-not-allowed opacity-70"
                                    disabled
                                >
                                    <option value="America/Argentina/Buenos_Aires">Buenos Aires (GMT-3)</option>
                                    <option value="America/Mexico_City">Ciudad de México (GMT-6)</option>
                                    <option value="Europe/Madrid">Madrid (GMT+1)</option>
                                </select>
                                <p className="mt-2 text-[10px] text-blue-600 font-bold bg-blue-50 p-2 rounded-lg">
                                    Actualmente el CEP puede solicitar cambios de zona horaria vía soporte.
                                </p>
                            </div>

                            {/* Automation Info */}
                            <div className="bg-indigo-900 rounded-2xl p-6 text-white shadow-lg overflow-hidden relative">
                                <div className="absolute -top-4 -right-4 opacity-10">
                                    <BarChart3 size={100} />
                                </div>
                                <h4 className="font-bold text-lg mb-2 flex items-center gap-2">
                                    <Activity size={18} className="text-indigo-300" />
                                    Reglas de Negocio
                                </h4>
                                <ul className="space-y-4 relative z-10">
                                    <li className="flex gap-3">
                                        <div className="bg-indigo-700 h-5 w-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black">1</div>
                                        <div className="text-xs">
                                            <p className="font-bold text-indigo-100">Recordatorio 24h</p>
                                            <p className="opacity-70">Envío automático exacto 24 horas antes de la cita.</p>
                                        </div>
                                    </li>
                                    <li className="flex gap-3">
                                        <div className="bg-indigo-700 h-5 w-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black">2</div>
                                        <div className="text-xs">
                                            <p className="font-bold text-indigo-100">Feedback Pacientes</p>
                                            <p className="opacity-70">Mensaje de calidad 45 minutos después de marcar como 'Completada'.</p>
                                        </div>
                                    </li>
                                    <li className="flex gap-3">
                                        <div className="bg-indigo-700 h-5 w-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black">3</div>
                                        <div className="text-xs">
                                            <p className="font-bold text-indigo-100">Recuperación de Leads</p>
                                            <p className="opacity-70">Si un lead de Meta no agenda en 2 horas, se envía incentivo.</p>
                                        </div>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MetaTemplatesView;
