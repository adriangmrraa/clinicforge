import React, { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    size?: 'md' | 'lg' | 'xl';
}

const sizeClasses = {
    md: 'lg:max-w-md',
    lg: 'lg:max-w-2xl',
    xl: 'lg:max-w-4xl'
};

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, size = 'lg' }) => {
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => { document.body.style.overflow = ''; };
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-[100] flex items-end lg:items-center justify-center lg:p-4 bg-black/50 backdrop-blur-sm"
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
            <div className={`relative w-full ${sizeClasses[size]} bg-white border-t lg:border border-gray-200 rounded-t-2xl lg:rounded-2xl shadow-2xl flex flex-col max-h-[92vh] lg:max-h-[85vh]`}>
                {/* Header */}
                <div className="flex justify-between items-center px-5 py-4 lg:px-6 lg:py-5 border-b border-gray-100 shrink-0">
                    <h2 className="text-lg lg:text-xl font-bold text-gray-900">{title}</h2>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors active:bg-gray-200"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="px-5 py-4 lg:px-6 lg:py-5 overflow-y-auto overscroll-contain" style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
                    {children}
                </div>
            </div>
        </div>
    );
};
