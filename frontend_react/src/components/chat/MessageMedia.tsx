import React from 'react';
import { FileText, Image as ImageIcon, Video, Music, Download, ExternalLink } from 'lucide-react';
import { BACKEND_URL } from '../../api/axios';
import type { ChatApiMessage } from '../../types/chat';

interface ChatMessage {
    id: number | string;
    from_number: string;
    role: 'user' | 'assistant' | 'system' | 'human_supervisor';
    content: string;
    created_at: string;
    attachments?: any[];
    is_derivhumano?: boolean;
}

// Helper para convertir URLs en links
export const Linkify = ({ text }: { text: string }) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);

    return (
        <>
            {parts.map((part, i) => (
                urlRegex.test(part) ? (
                    <a
                        key={i}
                        href={part}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:underline inline-flex items-center gap-1"
                    >
                        {part} <ExternalLink size={12} />
                    </a>
                ) : part
            ))}
        </>
    );
};

export const MessageMedia = ({ attachments }: { attachments: any[] }) => {
    if (!attachments || attachments.length === 0) return null;

    const getProxyUrl = (url: string) => {
        if (url.startsWith('/media/')) return `${BACKEND_URL}${url}`;
        return `${BACKEND_URL}/admin/chat/media/proxy?url=${encodeURIComponent(url)}`;
    };

    const renderFileIcon = (type: string) => {
        switch (type) {
            case 'image': return <ImageIcon className="text-blue-500" />;
            case 'video': return <Video className="text-purple-500" />;
            case 'audio': return <Music className="text-green-500" />;
            default: return <FileText className="text-gray-500" />;
        }
    };

    const isGrouped = attachments.length > 4;

    return (
        <div className={`mt-2 flex flex-wrap gap-2 ${isGrouped ? 'grid grid-cols-3' : 'flex-col'}`}>
            {attachments.map((att, idx) => {
                const type = att.type || 'file';
                const url = getProxyUrl(att.url);

                if (type === 'image' && !isGrouped) {
                    return (
                        <div key={idx} className="relative group">
                            <img
                                src={url}
                                alt="attachment"
                                className="max-w-xs rounded-lg cursor-pointer hover:opacity-90 transition-opacity border"
                                onClick={() => window.open(url, '_blank')}
                            />
                        </div>
                    );
                }

                if (type === 'audio' && !isGrouped) {
                    return (
                        <div key={idx} className="bg-gray-50 p-2 rounded-lg border flex flex-col gap-2 min-w-[240px]">
                            <div className="flex items-center gap-2">
                                <audio controls src={url} className="h-8 w-full" />
                            </div>
                            {att.transcription && (
                                <div className="text-xs text-gray-600 bg-white p-2 rounded border italic">
                                    "{att.transcription}"
                                </div>
                            )}
                        </div>
                    );
                }

                return (
                    <div
                        key={idx}
                        className={`flex items-center gap-2 p-2 rounded-lg border bg-white hover:bg-gray-50 transition-colors cursor-pointer ${isGrouped ? 'aspect-square justify-center' : ''}`}
                        onClick={() => window.open(url, '_blank')}
                    >
                        {renderFileIcon(type)}
                        {!isGrouped && (
                            <div className="flex-1 overflow-hidden">
                                <p className="text-xs font-medium truncate">{att.file_name || 'Archivo'}</p>
                                {att.file_size && <p className="text-[10px] text-gray-500">{(att.file_size / 1024).toFixed(1)} KB</p>}
                            </div>
                        )}
                        {!isGrouped && <Download size={14} className="text-gray-400" />}
                    </div>
                );
            })}
        </div>
    );
};

export const MessageContent = ({ message }: { message: ChatMessage | ChatApiMessage }) => {
    const content = message.content || '';
    const attachments = (message as any).attachments || (message as any).content_attributes || [];

    return (
        <div className="flex flex-col gap-1">
            {content && <div className="whitespace-pre-wrap"><Linkify text={content} /></div>}
            <MessageMedia attachments={Array.isArray(attachments) ? attachments : []} />
        </div>
    );
};
