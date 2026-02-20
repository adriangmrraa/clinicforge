import { Shield, FileText, ChevronLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function PrivacyTermsView() {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-6">
            <div className="max-w-3xl mx-auto space-y-8">
                {/* Back Button */}
                <button
                    onClick={() => navigate('/login')}
                    className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors mb-4"
                >
                    <ChevronLeft size={20} /> Volver al Inicio
                </button>

                {/* Header */}
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Shield size={32} />
                    </div>
                    <h1 className="text-3xl font-bold text-gray-900">Centro Legal de Dentalogic</h1>
                    <p className="text-gray-500 text-lg">Transparencia y seguridad en el manejo de tus datos.</p>
                </div>

                {/* Privacy Policy */}
                <section id="privacy" className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm space-y-6">
                    <div className="flex items-center gap-3 border-b border-gray-100 pb-4">
                        <Shield className="text-blue-500" size={24} />
                        <h2 className="text-2xl font-bold text-gray-900">Política de Privacidad</h2>
                    </div>

                    <div className="prose prose-blue max-w-none text-gray-600 space-y-4">
                        <p>Última actualización: 19 de febrero de 2026</p>

                        <h3 className="text-lg font-semibold text-gray-900">1. Recopilación de Información</h3>
                        <p>
                            Dentalogic recopila información necesaria para la gestión de clínicas dentales, incluyendo nombres de pacientes,
                            historiales de agendamiento y datos de contacto. Cuando conectas tu cuenta de Meta Ads, recopilamos estadísticas de rendimiento
                            (clics, gasto, impresiones) para calcular tu ROI.
                        </p>

                        <h3 className="text-lg font-semibold text-gray-900">2. Uso de Datos de Meta</h3>
                        <p>
                            Los datos obtenidos a través de los APIs de Meta se utilizan exclusivamente para:
                        </p>
                        <ul className="list-disc pl-6 space-y-2">
                            <li>Visualizar el rendimiento de tus campañas en nuestro dashboard.</li>
                            <li>Atribuir mensajes entrantes de WhatsApp a anuncios específicos de Meta.</li>
                            <li>Generar reportes de retorno de inversión (ROI) para el propietario de la clínica.</li>
                        </ul>

                        <h3 className="text-lg font-semibold text-gray-900">3. Protección de Datos</h3>
                        <p>
                            Utilizamos cifrado AES-256 para proteger todos los tokens de acceso y credenciales sensibles. Nunca compartimos tus datos
                            con terceros sin tu consentimiento explícito.
                        </p>
                    </div>
                </section>

                {/* Terms of Service */}
                <section id="terms" className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm space-y-6">
                    <div className="flex items-center gap-3 border-b border-gray-100 pb-4">
                        <FileText className="text-indigo-500" size={24} />
                        <h2 className="text-2xl font-bold text-gray-900">Condiciones del Servicio</h2>
                    </div>

                    <div className="prose prose-indigo max-w-none text-gray-600 space-y-4">
                        <p>Al utilizar Dentalogic, aceptas los siguientes términos:</p>

                        <h3 className="text-lg font-semibold text-gray-900">1. Uso del Software</h3>
                        <p>
                            Dentalogic es una plataforma para la gestión administrativa de clínicas. El usuario es responsable de la veracidad
                            de los datos ingresados y del cumplimiento de las normativas de salud locales.
                        </p>

                        <h3 className="text-lg font-semibold text-gray-900">2. Integraciones de Terceros</h3>
                        <p>
                            La integración con Meta Ads y WhatsApp depende de los términos y condiciones de Meta Platforms, Inc. No nos hacemos responsables
                            por interrupciones de servicio causadas por plataformas externas.
                        </p>

                        <h3 className="text-lg font-semibold text-gray-900">3. Terminación</h3>
                        <p>
                            Puedes revocar el acceso a tus datos en cualquier momento a través del panel de configuración de Meta o dentro de nuestra
                            plataforma en la sección de Marketing.
                        </p>
                    </div>
                </section>

                {/* Footer */}
                <footer className="text-center text-gray-400 text-sm py-8 border-t border-gray-100">
                    &copy; 2026 Dentalogic. Todos los derechos reservados.
                </footer>
            </div>
        </div>
    );
}
