import { Shield, FileText, ChevronLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../context/LanguageContext';

export default function PrivacyTermsView() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const appName = t('nav.app_name');

    const interpolate = (key: string) => t(key).replace(/{appName}/g, appName);

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-6">
            <div className="max-w-3xl mx-auto space-y-8">
                <button
                    onClick={() => navigate('/login')}
                    className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors mb-4"
                >
                    <ChevronLeft size={20} /> {t('legal.back_button')}
                </button>

                <div className="text-center space-y-4">
                    <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Shield size={32} />
                    </div>
                    <h1 className="text-3xl font-bold text-gray-900">{interpolate('legal.center_title')}</h1>
                    <p className="text-gray-500 text-lg">{t('legal.center_subtitle')}</p>
                </div>

                {/* Privacy Policy */}
                <section id="privacy" className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm space-y-6">
                    <div className="flex items-center gap-3 border-b border-gray-100 pb-4">
                        <Shield className="text-blue-500" size={24} />
                        <h2 className="text-2xl font-bold text-gray-900">{t('privacy.title')}</h2>
                    </div>

                    <div className="prose prose-blue max-w-none text-gray-600 space-y-4">
                        <p>{t('privacy.last_updated')}</p>

                        <h3 className="text-lg font-semibold text-gray-900">{t('privacy.s1_title')}</h3>
                        <p>{interpolate('privacy.s1_body')}</p>

                        <h3 className="text-lg font-semibold text-gray-900">{t('privacy.s2_title')}</h3>
                        <p>{t('privacy.s2_intro')}</p>
                        <ul className="list-disc pl-6 space-y-2">
                            <li>{t('privacy.s2_item1')}</li>
                            <li>{t('privacy.s2_item2')}</li>
                            <li>{t('privacy.s2_item3')}</li>
                        </ul>

                        <h3 className="text-lg font-semibold text-gray-900">{t('privacy.s3_title')}</h3>
                        <p>{t('privacy.s3_body')}</p>
                    </div>
                </section>

                {/* Terms of Service */}
                <section id="terms" className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm space-y-6">
                    <div className="flex items-center gap-3 border-b border-gray-100 pb-4">
                        <FileText className="text-indigo-500" size={24} />
                        <h2 className="text-2xl font-bold text-gray-900">{t('terms.title')}</h2>
                    </div>

                    <div className="prose prose-indigo max-w-none text-gray-600 space-y-4">
                        <p>{interpolate('terms.intro')}</p>

                        <h3 className="text-lg font-semibold text-gray-900">{t('terms.s1_title')}</h3>
                        <p>{interpolate('terms.s1_body')}</p>

                        <h3 className="text-lg font-semibold text-gray-900">{t('terms.s2_title')}</h3>
                        <p>{t('terms.s2_body')}</p>

                        <h3 className="text-lg font-semibold text-gray-900">{t('terms.s3_title')}</h3>
                        <p>{t('terms.s3_body')}</p>
                    </div>
                </section>

                <footer className="text-center text-gray-400 text-sm py-8 border-t border-gray-100">
                    {interpolate('legal.footer')}
                </footer>
            </div>
        </div>
    );
}
