import React from 'react';
import { Clock, Users, Activity, AlertTriangle } from 'lucide-react';

export default function SecretaryView() {
    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Wait Time Alerter */}
            <div className="lg:col-span-2 space-y-6">
                <div className="bg-white/70 backdrop-blur-2xl p-8 rounded-[2.5rem] border border-white/60 shadow-elevated">
                    <div className="flex items-center justify-between mb-8">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-medical-50 text-medical-600 rounded-2xl">
                                <Clock size={20} />
                            </div>
                            <h3 className="font-bold text-slate-800 text-lg">Estado de Sala de Espera</h3>
                        </div>
                        <span className="px-4 py-1.5 bg-green-50 text-green-600 rounded-full text-[10px] font-black uppercase tracking-widest border border-green-100">
                            Flujo Óptimo
                        </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-2">
                            <p className="text-slate-400 text-[10px] font-black uppercase tracking-widest">Tiempo de Espera Promedio</p>
                            <div className="flex items-baseline gap-2">
                                <span className="text-5xl font-black text-slate-800 tracking-tighter">12</span>
                                <span className="text-xl font-bold text-slate-400">min</span>
                            </div>
                        </div>
                        <div className="flex flex-col justify-end">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-[10px] font-bold text-slate-500 uppercase">Ocupación de Consultorios</span>
                                <span className="text-[10px] font-black text-medical-600">85%</span>
                            </div>
                            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full bg-medical-500 w-[85%] rounded-full shadow-[0_0_12px_rgba(var(--medical-500),0.4)]" />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Next Patients List */}
                <div className="bg-white/40 backdrop-blur-xl p-6 rounded-[2rem] border border-white/40 shadow-soft">
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-6 px-2">Monitoreo de Flujo Próximo</h4>
                    <div className="space-y-4">
                        {[
                            { id: 1, name: 'John Doe', delay: 0, status: 'On Time' },
                            { id: 2, name: 'Jane Smith', delay: 10, status: 'Slight Delay' },
                            { id: 3, name: 'Robert Brown', delay: -5, status: 'Ahead' },
                        ].map(patient => (
                            <div key={patient.id} className="flex items-center justify-between p-4 bg-white/60 rounded-2xl border border-white/40 hover:border-medical-200 transition-all">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 bg-slate-100 rounded-xl flex items-center justify-center font-bold text-slate-500 uppercase">
                                        {patient.name.charAt(0)}
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-800 text-sm">{patient.name}</p>
                                        <p className="text-[10px] text-slate-400 font-medium italic">Turno: 16:30hs</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`text-[10px] font-bold uppercase tracking-tight ${patient.delay > 0 ? 'text-amber-500' : 'text-green-500'}`}>
                                        {patient.delay === 0 ? 'En hora' : patient.delay > 0 ? `+${patient.delay}m retraso` : `${Math.abs(patient.delay)}m antes`}
                                    </span>
                                    <button className="p-2 text-slate-300 hover:text-medical-600 transition-colors">
                                        <Activity size={16} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Operational Alerts */}
            <div className="space-y-6">
                <div className="bg-amber-50/50 backdrop-blur-md p-6 rounded-[2rem] border border-amber-100">
                    <div className="flex items-center gap-3 mb-4 text-amber-600">
                        <AlertTriangle size={24} />
                        <h3 className="font-black uppercase tracking-tighter text-sm">Alerta Operativa</h3>
                    </div>
                    <p className="text-xs text-amber-800 leading-relaxed font-medium">
                        Se detecta congestión proyectada para las 18:00hs debido a 2 procedimientos de alta complejidad simultáneos.
                    </p>
                    <button className="mt-4 w-full py-3 bg-amber-600 text-white rounded-xl text-xs font-black uppercase tracking-widest shadow-lg shadow-amber-900/20 active:scale-95 transition-all">
                        Optimizar Agenda
                    </button>
                </div>
            </div>
        </div>
    );
}
