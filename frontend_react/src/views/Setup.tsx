import React, { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { ArrowRight, ArrowLeft, CheckCircle, Smartphone, ShoppingBag, Send } from 'lucide-react';

export const Setup: React.FC = () => {
    const { fetchApi, loading } = useApi();
    const [currentStep, setCurrentStep] = useState(1);
    const [formData, setFormData] = useState({
        bot_phone_number: '',
        store_name: '',
        store_website: '',
        tiendanube_store_id: '',
        tiendanube_token: ''
    });
    const [testResult, setTestResult] = useState<any>(null);

    const handleNext = async () => {
        setTestResult(null);
        if (currentStep === 1) {
            // Validate step 1?
        }
        if (currentStep === 2) {
            // Validate step 2
        }
        if (currentStep < 5) setCurrentStep(c => c + 1);
        else {
            // Finalize
            alert('Setup Completo!');
            window.location.href = '/';
        }
    };

    const handlePrev = () => {
        setTestResult(null);
        if (currentStep > 1) setCurrentStep(c => c - 1);
    };

    const runTest = async (step: number) => {
        try {
            setTestResult({ status: 'loading', message: 'Probando...' });

            if (step === 3) {
                // Create storee if needed
                const payload = {
                    store_name: formData.store_name,
                    bot_phone_number: formData.bot_phone_number,
                    store_website: formData.store_website,
                    tiendanube_store_id: formData.tiendanube_store_id,
                    tiendanube_access_token: formData.tiendanube_token
                };
                await fetchApi('/admin/tenants', { method: 'POST', body: payload });
                setTestResult({ status: 'success', message: 'Tienda creada/actualizada correctamente.' });
            } else if (step === 4) {
                await fetchApi('/admin/diagnostics/healthz');
                setTestResult({ status: 'success', message: 'Conexión con Orquestador: OK' });
            } else if (step === 5) {
                // Send test msg
                await fetchApi(`/admin/tenants/${formData.bot_phone_number}/test-message`, { method: 'POST' });
                setTestResult({ status: 'success', message: 'Mensaje enviado a tu WhatsApp.' });
            }

        } catch (e) {
            setTestResult({ status: 'error', message: e.message });
        }
    };

    return (
        <div className="view active">
            <h1 className="view-title">Asistente de Configuración</h1>

            <div className="glass" style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
                {/* Progress Bar */}
                <div style={{ marginBottom: '40px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                        {[1, 2, 3, 4, 5].map(step => (
                            <div key={step} style={{
                                width: '30px', height: '30px', borderRadius: '50%',
                                background: step <= currentStep ? 'var(--accent)' : 'rgba(255,255,255,0.1)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '14px', fontWeight: 'bold'
                            }}>
                                {step < currentStep ? <CheckCircle size={16} /> : step}
                            </div>
                        ))}
                    </div>
                    <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px' }}>
                        <div style={{ height: '100%', width: `${((currentStep - 1) / 4) * 100}%`, background: 'var(--accent)', transition: 'width 0.3s' }}></div>
                    </div>
                </div>

                <div className="setup-content" style={{ minHeight: '300px' }}>
                    {currentStep === 1 && (
                        <div className="fade-in">
                            <h2 style={{ marginBottom: '20px' }}>Crear Tienda</h2>
                            <p style={{ color: '#a1a1aa', marginBottom: '30px' }}>Configura los datos básicos de tu primera tienda.</p>
                            <div className="form-group">
                                <label>Número de WhatsApp (Bot)</label>
                                <div style={{ position: 'relative' }}>
                                    <Smartphone size={18} style={{ position: 'absolute', top: '14px', left: '12px', color: '#a1a1aa' }} />
                                    <input style={{ paddingLeft: '40px' }} value={formData.bot_phone_number} onChange={e => setFormData({ ...formData, bot_phone_number: e.target.value })} placeholder="54911..." />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Nombre de la Tienda</label>
                                <div style={{ position: 'relative' }}>
                                    <ShoppingBag size={18} style={{ position: 'absolute', top: '14px', left: '12px', color: '#a1a1aa' }} />
                                    <input style={{ paddingLeft: '40px' }} value={formData.store_name} onChange={e => setFormData({ ...formData, store_name: e.target.value })} placeholder="Mi Tienda" />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Sitio Web</label>
                                <input value={formData.store_website} onChange={e => setFormData({ ...formData, store_website: e.target.value })} placeholder="https://..." />
                            </div>
                        </div>
                    )}

                    {currentStep === 2 && (
                        <div className="fade-in">
                            <h2 style={{ marginBottom: '20px' }}>Conectar Tienda Nube</h2>
                            <p style={{ color: '#a1a1aa', marginBottom: '30px' }}>Ingresa tus credenciales de Tienda Nube para sincronizar el catálogo.</p>
                            <div className="form-group">
                                <label>ID de Tienda</label>
                                <input value={formData.tiendanube_store_id} onChange={e => setFormData({ ...formData, tiendanube_store_id: e.target.value })} placeholder="123456" />
                            </div>
                            <div className="form-group">
                                <label>Access Token</label>
                                <input type="password" value={formData.tiendanube_token} onChange={e => setFormData({ ...formData, tiendanube_token: e.target.value })} placeholder="Token API" />
                            </div>
                        </div>
                    )}

                    {currentStep === 3 && (
                        <div className="fade-in">
                            <h2 style={{ marginBottom: '20px' }}>Guardar Configuración</h2>
                            <p style={{ color: '#a1a1aa', marginBottom: '30px' }}>Vamos a guardar tu tienda en la base de datos.</p>
                            <button className="btn-secondary" onClick={() => runTest(3)} disabled={loading}>
                                {loading ? 'Guardando...' : 'Guardar y Verificar'}
                            </button>
                        </div>
                    )}

                    {currentStep === 4 && (
                        <div className="fade-in">
                            <h2 style={{ marginBottom: '20px' }}>Verificar Servicios</h2>
                            <p style={{ color: '#a1a1aa', marginBottom: '30px' }}>Comprobando estado del sistema...</p>
                            <button className="btn-secondary" onClick={() => runTest(4)} disabled={loading}>
                                {loading ? 'Verificando...' : 'Verificar Salud'}
                            </button>
                        </div>
                    )}

                    {currentStep === 5 && (
                        <div className="fade-in">
                            <h2 style={{ marginBottom: '20px' }}>Prueba Final</h2>
                            <p style={{ color: '#a1a1aa', marginBottom: '30px' }}>Enviaremos un mensaje de prueba a tu WhatsApp: {formData.bot_phone_number}</p>
                            <button className="btn-primary" onClick={() => runTest(5)} disabled={loading}>
                                <Send size={18} style={{ marginRight: '8px' }} />
                                {loading ? 'Enviando...' : 'Enviar Mensaje de Prueba'}
                            </button>
                        </div>
                    )}

                    {testResult && (
                        <div className={`preflight-check ${testResult.status === 'success' ? 'check-pass' : 'check-fail'}`} style={{ marginTop: '20px' }}>
                            <div className="check-header">
                                <span className="check-name">{testResult.message}</span>
                            </div>
                        </div>
                    )}

                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '40px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                    <button className="btn-secondary" onClick={handlePrev} disabled={currentStep === 1} style={{ display: currentStep === 1 ? 'none' : 'flex', alignItems: 'center', gap: '8px' }}>
                        <ArrowLeft size={18} /> Anterior
                    </button>
                    <button className="btn-primary" onClick={handleNext} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' }}>
                        {currentStep === 5 ? 'Finalizar' : 'Siguiente'} <ArrowRight size={18} />
                    </button>
                </div>
            </div>
        </div>
    );
};
