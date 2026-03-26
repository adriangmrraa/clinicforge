import { Shield, FileText, ChevronLeft, Lock, Eye, Server, Trash2, Scale, HeartHandshake } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../context/LanguageContext';

const keyframesStyle = `
@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-12px); }
}
@keyframes glow-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.6; }
}
`;

export default function PrivacyTermsView() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const appName = t('nav.app_name');
    const interpolate = (key: string) => t(key).replace(/{appName}/g, appName);

    return (
        <>
            <style>{keyframesStyle}</style>
            <div className="min-h-screen bg-[#0a0f1a] text-white relative overflow-hidden">
                {/* Background effects */}
                <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px]" style={{ animation: 'glow-pulse 6s ease-in-out infinite' }} />
                    <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-[100px]" style={{ animation: 'glow-pulse 8s ease-in-out infinite 2s' }} />
                </div>

                <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
                    {/* Back button */}
                    <button
                        onClick={() => navigate('/login')}
                        className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-8 group"
                    >
                        <ChevronLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
                        <span className="text-sm">{t('legal.back_button')}</span>
                    </button>

                    {/* Hero */}
                    <div className="text-center mb-12">
                        <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-cyan-500/20" style={{ animation: 'float 4s ease-in-out infinite' }}>
                            <Shield size={28} className="text-white" />
                        </div>
                        <h1 className="text-3xl sm:text-4xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                            {interpolate('legal.center_title')}
                        </h1>
                        <p className="text-gray-400 text-base sm:text-lg mt-3 max-w-xl mx-auto">{t('legal.center_subtitle')}</p>
                    </div>

                    {/* Trust badges */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
                        {[
                            { icon: Lock, label: 'Encriptacion SSL', color: 'cyan' },
                            { icon: Eye, label: 'Transparencia total', color: 'blue' },
                            { icon: Server, label: 'Datos en la nube', color: 'indigo' },
                            { icon: HeartHandshake, label: 'Compromiso etico', color: 'purple' },
                        ].map((badge, i) => (
                            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-4 text-center hover:bg-white/10 transition-colors">
                                <badge.icon size={20} className={`text-${badge.color}-400 mx-auto mb-2`} />
                                <p className="text-[11px] text-gray-400 font-medium">{badge.label}</p>
                            </div>
                        ))}
                    </div>

                    {/* Privacy Policy */}
                    <section className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-3xl p-6 sm:p-8 mb-6 hover:border-cyan-500/20 transition-colors">
                        <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-6">
                            <div className="w-10 h-10 bg-cyan-500/10 rounded-xl flex items-center justify-center">
                                <Shield className="text-cyan-400" size={20} />
                            </div>
                            <h2 className="text-xl sm:text-2xl font-bold text-white">{t('privacy.title')}</h2>
                        </div>

                        <div className="space-y-5 text-gray-300 text-sm sm:text-base leading-relaxed">
                            <p className="text-gray-500 text-xs">{t('privacy.last_updated')}</p>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('privacy.s1_title')}</h3>
                                <p>{interpolate('privacy.s1_body')}</p>
                            </div>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('privacy.s2_title')}</h3>
                                <p className="mb-3">{t('privacy.s2_intro')}</p>
                                <ul className="space-y-2 ml-1">
                                    {['s2_item1', 's2_item2', 's2_item3'].map((key) => (
                                        <li key={key} className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-2 shrink-0" />
                                            <span>{t(`privacy.${key}`)}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('privacy.s3_title')}</h3>
                                <p>{t('privacy.s3_body')}</p>
                            </div>
                        </div>
                    </section>

                    {/* Terms of Service */}
                    <section className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-3xl p-6 sm:p-8 mb-6 hover:border-blue-500/20 transition-colors">
                        <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-6">
                            <div className="w-10 h-10 bg-blue-500/10 rounded-xl flex items-center justify-center">
                                <FileText className="text-blue-400" size={20} />
                            </div>
                            <h2 className="text-xl sm:text-2xl font-bold text-white">{t('terms.title')}</h2>
                        </div>

                        <div className="space-y-5 text-gray-300 text-sm sm:text-base leading-relaxed">
                            <p>{interpolate('terms.intro')}</p>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('terms.s1_title')}</h3>
                                <p>{interpolate('terms.s1_body')}</p>
                            </div>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('terms.s2_title')}</h3>
                                <p>{t('terms.s2_body')}</p>
                            </div>

                            <div>
                                <h3 className="text-base font-semibold text-white mb-2">{t('terms.s3_title')}</h3>
                                <p>{t('terms.s3_body')}</p>
                            </div>
                        </div>
                    </section>

                    {/* Footer */}
                    <footer className="text-center py-8">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-6 h-6 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-lg flex items-center justify-center">
                                <Scale size={12} className="text-white" />
                            </div>
                            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Dentalogic AI</span>
                        </div>
                        <p className="text-gray-600 text-xs">{interpolate('legal.footer')}</p>
                    </footer>
                </div>
            </div>
        </>
    );
}
