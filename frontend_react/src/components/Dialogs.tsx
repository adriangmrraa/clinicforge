import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';

/**
 * On-brand replacement for the native `window.confirm` / `window.alert`
 * browser dialogs. Provides an imperative API usable from any handler
 * (even outside React components) plus a single <DialogHost /> that must
 * be mounted once, inside <LanguageProvider>.
 *
 *   if (!(await confirmDialog('¿Eliminar este turno?', { danger: true }))) return;
 *   showAlert('Guardado correctamente');
 *
 * Styling mirrors components/Modal.tsx (white card, black/50 backdrop) so
 * the dialogs feel native to the app. Renders at z-[200] to sit above any
 * open <Modal /> (z-[100]).
 */

type AlertVariant = 'info' | 'error' | 'success';

interface ConfirmOptions {
    title?: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    danger?: boolean;
}

interface AlertOptions {
    title?: string;
    message: string;
    variant?: AlertVariant;
    okText?: string;
}

interface DialogRequest {
    id: number;
    kind: 'confirm' | 'alert';
    options: ConfirmOptions & AlertOptions;
    resolve: (value: boolean) => void;
}

let counter = 0;
let listener: ((req: DialogRequest | null) => void) | null = null;
const queue: DialogRequest[] = [];
let active: DialogRequest | null = null;

function pump() {
    if (active || queue.length === 0) return;
    active = queue.shift() as DialogRequest;
    if (listener) listener(active);
}

function enqueue(kind: 'confirm' | 'alert', options: ConfirmOptions & AlertOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
        queue.push({ id: ++counter, kind, options, resolve });
        pump();
    });
}

/** On-brand confirm. Resolves true if the user confirms, false otherwise. */
export function confirmDialog(message: string, opts?: Partial<ConfirmOptions>): Promise<boolean> {
    return enqueue('confirm', { message, ...opts });
}

/** On-brand alert. Fire-and-forget drop-in replacement for window.alert. */
export function showAlert(message: string, opts?: Partial<AlertOptions>): void {
    void enqueue('alert', { message, ...opts });
}

export const DialogHost: React.FC = () => {
    const { t } = useTranslation();
    const [req, setReq] = useState<DialogRequest | null>(null);

    useEffect(() => {
        listener = setReq;
        pump(); // flush anything enqueued before mount
        return () => { listener = null; };
    }, []);

    const close = useCallback((result: boolean) => {
        const current = active;
        active = null;
        setReq(null);
        if (current) current.resolve(result);
        // Show the next queued dialog on the following tick.
        setTimeout(pump, 0);
    }, []);

    useEffect(() => {
        if (!req) return;
        document.body.style.overflow = 'hidden';
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') close(req.kind === 'alert');
            else if (e.key === 'Enter') close(true);
        };
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('keydown', onKey);
            document.body.style.overflow = '';
        };
    }, [req, close]);

    if (!req) return null;

    const o = req.options;
    const isConfirm = req.kind === 'confirm';
    const danger = !!o.danger;
    const variant: AlertVariant = o.variant || 'info';

    let iconWrap = 'bg-gray-100 text-gray-600';
    let icon = <AlertTriangle size={22} />;
    if (isConfirm) {
        if (danger) { iconWrap = 'bg-red-100 text-red-600'; icon = <AlertTriangle size={22} />; }
    } else if (variant === 'error') {
        iconWrap = 'bg-red-100 text-red-600'; icon = <AlertTriangle size={22} />;
    } else if (variant === 'success') {
        iconWrap = 'bg-emerald-100 text-emerald-600'; icon = <CheckCircle2 size={22} />;
    } else {
        iconWrap = 'bg-blue-100 text-blue-600'; icon = <Info size={22} />;
    }

    const confirmBtn = danger
        ? 'bg-red-600 text-white hover:bg-red-700 active:bg-red-800'
        : 'bg-gray-900 text-white hover:bg-gray-800 active:bg-black';

    return (
        <div
            className="fixed inset-0 z-[200] flex items-end lg:items-center justify-center lg:p-4 bg-black/50 backdrop-blur-sm"
            onClick={(e) => { if (e.target === e.currentTarget) close(isConfirm ? false : true); }}
        >
            <div
                role="alertdialog"
                aria-modal="true"
                className="relative w-full lg:max-w-sm bg-white border-t lg:border border-gray-200 rounded-t-2xl lg:rounded-2xl shadow-2xl flex flex-col max-h-[92vh]"
            >
                <button
                    onClick={() => close(isConfirm ? false : true)}
                    className="absolute top-3 right-3 p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                    aria-label={t('dialogs.close')}
                >
                    <X size={18} />
                </button>

                <div className="px-5 pt-6 pb-4 lg:px-6 overflow-y-auto overscroll-contain">
                    <div className={`w-11 h-11 rounded-full flex items-center justify-center ${iconWrap}`}>
                        {icon}
                    </div>
                    {o.title && (
                        <h2 className="mt-4 text-lg font-bold text-gray-900">{o.title}</h2>
                    )}
                    <p className={`${o.title ? 'mt-1' : 'mt-4'} text-[15px] leading-relaxed text-gray-600 whitespace-pre-line`}>
                        {o.message}
                    </p>
                </div>

                <div
                    className="flex flex-col-reverse lg:flex-row lg:justify-end gap-2 px-5 pb-5 lg:px-6 pt-1"
                    style={{ paddingBottom: 'max(1.25rem, env(safe-area-inset-bottom))' }}
                >
                    {isConfirm && (
                        <button
                            onClick={() => close(false)}
                            className="px-4 py-2.5 rounded-xl text-sm font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 transition-colors"
                        >
                            {o.cancelText || t('dialogs.cancel')}
                        </button>
                    )}
                    <button
                        onClick={() => close(true)}
                        autoFocus
                        className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors ${isConfirm ? confirmBtn : 'bg-gray-900 text-white hover:bg-gray-800 active:bg-black'}`}
                    >
                        {isConfirm ? (o.confirmText || t('dialogs.confirm')) : (o.okText || t('dialogs.ok'))}
                    </button>
                </div>
            </div>
        </div>
    );
};
