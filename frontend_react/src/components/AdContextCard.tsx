/**
 * Spec 10: AdContextCard
 * Muestra el contexto del anuncio de Meta Ads al inicio de un chat.
 * Se renderiza antes del primer mensaje cuando el paciente vino de un ad.
 */
import { Megaphone, ExternalLink } from 'lucide-react';

interface AdContextCardProps {
    headline?: string;
    body?: string;
    sourceUrl?: string;
}

export default function AdContextCard({ headline, body, sourceUrl }: AdContextCardProps) {
    if (!headline && !body) return null;

    return (
        <div className="mx-4 mb-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-dashed border-blue-200 rounded-xl shadow-sm">
            <div className="flex items-start gap-3">
                {/* Icon */}
                <div className="flex-shrink-0 w-9 h-9 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Megaphone size={18} className="text-blue-600" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">
                        Contexto de Anuncio
                    </p>
                    {headline && (
                        <p className="text-sm font-medium text-gray-800 truncate" title={headline}>
                            {headline}
                        </p>
                    )}
                    {body && (
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2" title={body}>
                            {body}
                        </p>
                    )}
                </div>

                {/* External link */}
                {sourceUrl && (
                    <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 p-1.5 text-blue-400 hover:text-blue-600 hover:bg-blue-100 rounded-md transition-colors"
                        title="Ver anuncio original"
                    >
                        <ExternalLink size={14} />
                    </a>
                )}
            </div>
        </div>
    );
}
