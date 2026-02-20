import React, { useState, useEffect } from 'react';
import { CheckCircle2, ChevronRight, Building2, Briefcase, BarChart3, Loader2 } from 'lucide-react';
import api from '../../api/axios';

interface MetaConnectionWizardProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export default function MetaConnectionWizard({ isOpen, onClose, onSuccess }: MetaConnectionWizardProps) {
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Data for steps
    const [clinics, setClinics] = useState<any[]>([]);
    const [portfolios, setPortfolios] = useState<any[]>([]);
    const [accounts, setAccounts] = useState<any[]>([]);

    // Selection
    const [selectedClinic, setSelectedClinic] = useState<any>(null);
    const [selectedPortfolio, setSelectedPortfolio] = useState<any>(null);
    const [selectedAccount, setSelectedAccount] = useState<any>(null);

    useEffect(() => {
        if (isOpen) {
            loadClinics();
        }
    }, [isOpen]);

    const loadClinics = async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await api.get('/admin/marketing/clinics');
            setClinics(data.clinics || []);
            setStep(1);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error loading clinics");
        } finally {
            setLoading(false);
        }
    };

    const loadPortfolios = async () => {
        setLoading(true);
        setError(null);
        try {
            const { data } = await api.get('/admin/marketing/meta-portfolios');
            setPortfolios(data.portfolios || []);
            setStep(2);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error loading portfolios");
        } finally {
            setLoading(false);
        }
    };

    const loadAccounts = async (portfolioId?: string) => {
        setLoading(true);
        setError(null);
        try {
            const url = portfolioId
                ? `/admin/marketing/meta-accounts?portfolio_id=${portfolioId}`
                : `/admin/marketing/meta-accounts`;
            const { data } = await api.get(url);
            setAccounts(data.accounts || []);
            setStep(3);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error loading accounts");
        } finally {
            setLoading(false);
        }
    };

    const handleConnect = async () => {
        setLoading(true);
        setError(null);
        try {
            await api.post('/admin/marketing/connect', {
                tenant_id: selectedClinic.id,
                ad_account_id: selectedAccount.id,
                ad_account_name: selectedAccount.name
            });
            setStep(4);
            setTimeout(() => {
                onSuccess();
                onClose();
            }, 2000);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error connecting account");
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-white rounded-[32px] w-full max-w-lg overflow-hidden shadow-2xl animate-in zoom-in-95 duration-300">
                {/* Header */}
                <div className="p-8 border-b border-gray-100 bg-gray-50/50">
                    <div className="flex items-center gap-4 mb-2">
                        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
                            <BarChart3 size={24} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">Meta Connection Wizard</h2>
                            <p className="text-sm text-gray-500">Configure your ads connection in seconds.</p>
                        </div>
                    </div>
                </div>

                {/* Steps Progress */}
                <div className="px-8 pt-6 flex justify-between items-center">
                    {[1, 2, 3].map((s) => (
                        <div key={s} className="flex items-center gap-2">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm transition-all ${step === s ? 'bg-blue-600 text-white' :
                                step > s ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-400'
                                }`}>
                                {step > s ? <CheckCircle2 size={16} /> : s}
                            </div>
                            {s < 3 && <div className={`w-12 h-0.5 ${step > s ? 'bg-green-500' : 'bg-gray-100'}`} />}
                        </div>
                    ))}
                </div>

                {/* Content */}
                <div className="p-8">
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-2xl text-sm font-medium border border-red-100 animate-in slide-in-from-top-2">
                            {error}
                        </div>
                    )}

                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-12 gap-4">
                            <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                            <p className="text-gray-500 font-medium">Fetching data from Meta...</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {/* STEP 1: Choose Clinic */}
                            {step === 1 && (
                                <>
                                    <h3 className="font-bold text-gray-900 mb-2">Paso 1: ¿A qué clínica conectamos?</h3>
                                    <div className="grid gap-3">
                                        {clinics.map(c => (
                                            <button
                                                key={c.id}
                                                onClick={() => {
                                                    setSelectedClinic(c);
                                                    loadPortfolios();
                                                }}
                                                className="w-full p-4 rounded-2xl border-2 border-gray-100 hover:border-blue-600 hover:bg-blue-50/50 transition-all text-left flex items-center justify-between group"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <Building2 className="text-gray-400 group-hover:text-blue-600" size={20} />
                                                    <div>
                                                        <div className="font-bold text-gray-900">{c.name}</div>
                                                        <div className="text-xs text-gray-500">ID: {c.id}</div>
                                                    </div>
                                                </div>
                                                {c.is_connected && (
                                                    <span className="text-[10px] font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full uppercase">Ya conectada</span>
                                                )}
                                                <ChevronRight className="text-gray-300 group-hover:text-blue-600" size={18} />
                                            </button>
                                        ))}
                                    </div>
                                </>
                            )}

                            {/* STEP 2: Choose Portfolio */}
                            {step === 2 && (
                                <>
                                    <h3 className="font-bold text-gray-900 mb-2">Paso 2: Selecciona el Portafolio</h3>
                                    <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-2">
                                        {portfolios.map(p => (
                                            <button
                                                key={p.id}
                                                onClick={() => {
                                                    setSelectedPortfolio(p);
                                                    loadAccounts(p.id);
                                                }}
                                                className="w-full p-4 rounded-2xl border-2 border-gray-100 hover:border-blue-600 hover:bg-blue-50/50 transition-all text-left flex items-center justify-between group"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <Briefcase className="text-gray-400 group-hover:text-blue-600" size={20} />
                                                    <div className="font-bold text-gray-900">{p.name}</div>
                                                </div>
                                                <ChevronRight className="text-gray-300 group-hover:text-blue-600" size={18} />
                                            </button>
                                        ))}
                                        {portfolios.length === 0 && (
                                            <div className="text-center py-8 space-y-4">
                                                <p className="text-gray-500">No se encontraron Business Managers.</p>
                                                <button
                                                    onClick={() => loadAccounts()}
                                                    className="w-full py-3 bg-blue-50 text-blue-600 rounded-xl font-bold hover:bg-blue-100 transition-all"
                                                >
                                                    Listar todas las cuentas de anuncios
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                    <button onClick={() => setStep(1)} className="text-blue-600 text-sm font-bold hover:underline">← Volver</button>
                                </>
                            )}

                            {/* STEP 3: Choose Ad Account */}
                            {step === 3 && (
                                <>
                                    <h3 className="font-bold text-gray-900 mb-2">Paso 3: Elige la Cuenta de Anuncios</h3>
                                    <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-2">
                                        {accounts.map(a => (
                                            <button
                                                key={a.id}
                                                onClick={() => setSelectedAccount(a)}
                                                className={`w-full p-4 rounded-2xl border-2 transition-all text-left flex items-center justify-between group ${selectedAccount?.id === a.id ? 'border-blue-600 bg-blue-50' : 'border-gray-100 hover:border-blue-600 hover:bg-blue-50/50'
                                                    }`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className="font-bold text-gray-900">{a.name}</div>
                                                    <div className="text-[10px] font-bold bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded uppercase">{a.currency}</div>
                                                </div>
                                                {selectedAccount?.id === a.id && <CheckCircle2 className="text-blue-600" size={18} />}
                                            </button>
                                        ))}
                                        {accounts.length === 0 && (
                                            <div className="bg-amber-50 rounded-2xl p-6 border border-amber-100 text-center space-y-4">
                                                <div className="w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto">
                                                    <Briefcase size={24} />
                                                </div>
                                                <div>
                                                    <p className="font-bold text-amber-900">No hay cuentas disponibles</p>
                                                    <p className="text-xs text-amber-700 mt-1">Asegúrate de haber seleccionado tus cuentas en el popup de Meta Ads (Facebook).</p>
                                                </div>
                                                <div className="flex flex-col gap-2">
                                                    <button
                                                        onClick={() => loadAccounts()}
                                                        className="py-2.5 px-4 bg-white border border-amber-200 text-amber-800 rounded-xl text-xs font-bold hover:bg-amber-100 transition-all"
                                                    >
                                                        Buscar fuera del portafolio
                                                    </button>
                                                    <a
                                                        href="/marketing?reconnect=true"
                                                        className="text-xs text-blue-600 font-bold hover:underline"
                                                    >
                                                        Re-conectar eligiendo todas las cuentas
                                                    </a>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="pt-6 border-t border-gray-100 mt-4">
                                        <div className="text-xs font-bold text-gray-500 mb-2 uppercase tracking-wide">¿No ves tu cuenta?</div>
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                placeholder="Pegar ID manual (ej. 120218...)"
                                                className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500 transition-all font-mono"
                                                onChange={(e) => {
                                                    const val = e.target.value.trim();
                                                    if (val) {
                                                        setSelectedAccount({ id: val, name: "Cuenta Manual (" + val.slice(-4) + ")", currency: "UNK" });
                                                    } else {
                                                        setSelectedAccount(null);
                                                    }
                                                }}
                                            />
                                        </div>
                                        <p className="text-[10px] text-gray-400 mt-2">
                                            Si tienes permisos pero Meta no lista la cuenta, pega el ID directamente aquí.
                                        </p>
                                    </div>
                                    <div className="pt-6 flex gap-3">
                                        <button onClick={() => setStep(2)} className="flex-1 py-4 text-gray-500 font-bold hover:bg-gray-50 rounded-2xl transition-all">Atrás</button>
                                        <button
                                            disabled={!selectedAccount}
                                            onClick={handleConnect}
                                            className="flex-2 px-8 py-4 bg-gray-900 text-white rounded-2xl font-bold hover:bg-black transition-all disabled:opacity-50"
                                        >
                                            Confirmar Conexión
                                        </button>
                                    </div>
                                </>
                            )}

                            {/* STEP 4: Success */}
                            {step === 4 && (
                                <div className="flex flex-col items-center justify-center py-8 gap-4 text-center animate-in zoom-in-90 animate-out fade-out duration-500 scale-in-center">
                                    <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                                        <CheckCircle2 size={48} />
                                    </div>
                                    <div>
                                        <h3 className="text-2xl font-bold text-gray-900">¡Conexión Exitosa!</h3>
                                        <p className="text-gray-500 mt-2">La cuenta <strong>{selectedAccount?.name}</strong> está lista.<br />Sincronizando datos...</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer simple (opcional) */}
                <div className="p-6 bg-gray-50 text-center">
                    <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600 font-medium tracking-tight">Cerrar Asistente</button>
                </div>
            </div>
        </div>
    );
}
