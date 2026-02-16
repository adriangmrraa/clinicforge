import React, { useState, useEffect } from 'react';
import { LayoutDashboard, TrendingUp, Users, Clock, AlertCircle, Zap, ShieldCheck } from 'lucide-react';
import CEOView from './components/CEOView';
import SecretaryView from './components/SecretaryView';

export default function AnalyticsDashboard() {
    const [role, setRole] = useState<'ceo' | 'secretary'>('ceo'); // Mocked role selection
    const [loading, setLoading] = useState(false);

    return (
        <div className="flex flex-col h-screen overflow-hidden bg-slate-50/50">
            {/* Scroll Isolation: Fixed Header */}
            <header className="h-20 bg-white/70 backdrop-blur-xl border-b border-slate-200/60 px-8 flex items-center justify-between z-20">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-medical-600 text-white rounded-2xl shadow-lg shadow-medical-900/20">
                        <LayoutDashboard size={24} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-slate-800 tracking-tight">Sovereign Analytics</h1>
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-widest">Inteligencia Dental JIT v8.0</p>
                    </div>
                </div>

                <div className="flex bg-slate-100 p-1 rounded-2xl border border-slate-200">
                    <button
                        onClick={() => setRole('ceo')}
                        className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${role === 'ceo' ? 'bg-white text-medical-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                        CEO Mission
                    </button>
                    <button
                        onClick={() => setRole('secretary')}
                        className={`px-6 py-2 rounded-xl text-sm font-bold transition-all ${role === 'secretary' ? 'bg-white text-medical-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                        Operations
                    </button>
                </div>
            </header>

            {/* Scroll Isolation: Independent Scroll Area */}
            <main className="flex-1 min-h-0 overflow-y-auto p-8 custom-scrollbar">
                <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                    {role === 'ceo' ? <CEOView /> : <SecretaryView />}
                </div>
            </main>

            {/* Footer Info */}
            <footer className="h-10 bg-white/40 backdrop-blur-md border-t border-slate-200/40 px-8 flex items-center justify-center">
                <div className="flex items-center gap-2 text-[10px] text-slate-400 font-bold uppercase tracking-[0.2em]">
                    <ShieldCheck size={12} className="text-medical-500" />
                    Sovereign Data Protection: Tenant Isolation Active
                </div>
            </footer>
        </div>
    );
}
