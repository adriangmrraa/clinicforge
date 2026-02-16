import React from 'react';
import { TrendingUp, DollarSign, Zap, Target } from 'lucide-react';

export default function CEOView() {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* AI ROI Card */}
            <div className="bg-white/60 backdrop-blur-xl p-6 rounded-[2rem] border border-white/60 shadow-soft hover:shadow-elevated transition-all group">
                <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-purple-50 text-purple-600 rounded-2xl group-hover:scale-110 transition-transform">
                        <Zap size={20} fill="currentColor" />
                    </div>
                    <span className="text-[10px] font-bold text-green-500 bg-green-50 px-2 py-1 rounded-lg">+12.5%</span>
                </div>
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">ROI de IA</h3>
                <p className="text-3xl font-black text-slate-800 tracking-tight">3,233%</p>
                <div className="mt-4 pt-4 border-t border-slate-100/50">
                    <p className="text-[10px] text-slate-400 font-medium">Retorno directo sobre inversión en agentes</p>
                </div>
            </div>

            {/* Revenue Card */}
            <div className="bg-white/60 backdrop-blur-xl p-6 rounded-[2rem] border border-white/60 shadow-soft">
                <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl">
                        <DollarSign size={20} />
                    </div>
                </div>
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Ingresos JIT</h3>
                <p className="text-3xl font-black text-slate-800 tracking-tight">$45k</p>
                <div className="w-full bg-slate-100 h-1.5 mt-6 rounded-full overflow-hidden">
                    <div className="bg-medical-500 h-full w-[75%] rounded-full shadow-[0_0_8px_rgba(var(--medical-500),0.5)]" />
                </div>
            </div>

            {/* Conversion Card */}
            <div className="bg-white/60 backdrop-blur-xl p-6 rounded-[2rem] border border-white/60 shadow-soft">
                <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-green-50 text-green-600 rounded-2xl">
                        <Target size={20} />
                    </div>
                </div>
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Conversión Lead</h3>
                <p className="text-3xl font-black text-slate-800 tracking-tight">3.5 <span className="text-sm text-slate-400">días</span></p>
                <p className="text-[10px] text-slate-500 mt-4 font-semibold">Velocidad de cierre de agenda</p>
            </div>

            {/* LTV Card */}
            <div className="bg-white/60 backdrop-blur-xl p-6 rounded-[2rem] border border-white/60 shadow-soft">
                <div className="flex items-center justify-between mb-4">
                    <div className="p-3 bg-amber-50 text-amber-600 rounded-2xl">
                        <TrendingUp size={20} />
                    </div>
                </div>
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">Patient LTV</h3>
                <p className="text-3xl font-black text-slate-800 tracking-tight">$1,200</p>
                <p className="text-[10px] text-slate-500 mt-4 font-semibold">Valor proyectado por paciente único</p>
            </div>
        </div>
    );
}
