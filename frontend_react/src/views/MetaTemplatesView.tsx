import React from 'react';
import { Layout, MessageSquare, Send, BarChart3, Clock, CheckCircle2, ChevronRight, Sparkles } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';

const MetaTemplatesView: React.FC = () => {
    const { t } = useTranslation();

    const features = [
        {
            icon: <Send className="text-blue-600" size={24} />,
            title: "Reapertura de Canales",
            description: "Envía plantillas aprobadas por Meta para iniciar conversaciones fuera de la ventana de 24 horas."
        },
        {
            icon: <BarChart3 className="text-green-600" size={24} />,
            title: "Campañas Masivas",
            description: "Envía recordatorios de citas, promociones o noticias a toda tu base de contactos de forma segura."
        },
        {
            icon: <CheckCircle2 className="text-purple-600" size={24} />,
            title: "Aprobación Oficial",
            description: "Gestión directa de plantillas HSM (High Security Message) validadas por Meta para evitar bloqueos."
        }
    ];

    const stats = [
        { label: "Tasa de Apertura", value: "98%", color: "text-green-600" },
        { label: "CTR Promedio", value: "15-25%", color: "text-blue-600" },
        { label: "Conversión de Re-engagement", value: "45%", color: "text-purple-600" }
    ];

    return (
        <div className="flex flex-col h-full bg-gray-50 overflow-hidden">
            {/* Header */}
            <header className="bg-white border-b px-6 py-4 flex items-center justify-between shrink-0 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-2 rounded-lg shadow-md">
                        <Layout className="text-white" size={24} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-gray-900">Plantillas Meta</h1>
                        <p className="text-xs text-gray-500 font-medium">Bulk Messaging & ROI Forge</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wider">Próximamente</span>
                </div>
            </header>

            {/* Content Area */}
            <div className="flex-1 min-h-0 overflow-y-auto p-6 md:p-8">
                <div className="max-w-5xl mx-auto space-y-8">

                    {/* Hero Section */}
                    <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100 relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-8 opacity-10">
                            <Sparkles size={120} className="text-blue-600" />
                        </div>
                        <div className="relative z-10 max-w-2xl">
                            <h2 className="text-3xl font-extrabold text-gray-900 mb-4 leading-tight">
                                Rompe la barrera de las 24 horas con <span className="text-blue-600">Mensajes de Alta Conversión</span>.
                            </h2>
                            <p className="text-gray-600 text-lg mb-6 leading-relaxed">
                                Las plantillas Meta te permiten contactar a tus leads y pacientes en cualquier momento,
                                garantizando que tu clínica esté siempre presente.
                            </p>
                            <button className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold shadow-lg shadow-blue-200 flex items-center gap-2 hover:bg-blue-700 transition-all cursor-not-allowed opacity-80">
                                Explorar Catálogo <ChevronRight size={18} />
                            </button>
                        </div>
                    </div>

                    {/* Features Grid */}
                    <div className="grid md:grid-cols-3 gap-6">
                        {features.map((f, i) => (
                            <div key={i} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                                <div className="mb-4 bg-gray-50 w-12 h-12 rounded-xl flex items-center justify-center shadow-inner">
                                    {f.icon}
                                </div>
                                <h3 className="font-bold text-gray-900 mb-2">{f.title}</h3>
                                <p className="text-sm text-gray-500 leading-relaxed">{f.description}</p>
                            </div>
                        ))}
                    </div>

                    {/* Stats Section */}
                    <div className="bg-indigo-900 rounded-2xl p-8 text-white shadow-xl">
                        <div className="grid md:grid-cols-3 gap-8 text-center">
                            {stats.map((s, i) => (
                                <div key={i} className="space-y-1">
                                    <p className="text-indigo-200 text-sm font-medium uppercase tracking-widest">{s.label}</p>
                                    <p className={`text-4xl font-black ${s.color.replace('text-', 'text-indigo-300')}`}>{s.value}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Process / Coming Soon info */}
                    <div className="text-center py-12">
                        <div className="inline-flex items-center gap-2 text-indigo-600 bg-indigo-50 px-4 py-2 rounded-full font-bold text-sm mb-4">
                            <Clock size={16} /> Beta Privada en Progreso
                        </div>
                        <h3 className="text-2xl font-bold text-gray-900 mb-2">¿Listo para escalar tus ventas?</h3>
                        <p className="text-gray-500 max-w-lg mx-auto italic">
                            Estamos integrando la API de WhatsApp Cloud oficial para que puedas gestionar tus plantillas directamente desde Nexus.
                        </p>
                    </div>

                </div>
            </div>
        </div>
    );
};

export default MetaTemplatesView;
