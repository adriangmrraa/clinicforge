import { useRef, useEffect, useState, useCallback } from 'react';

/**
 * Hook para manejar el scroll inteligente en listas de chat.
 * Solo hace scroll-to-bottom si:
 * 1. El usuario ya estaba al final antes de recibir nuevos mensajes.
 * 2. Es la carga inicial.
 * 3. Se fuerza manualmente (ej: al enviar mensaje).
 */
export const useSmartScroll = <T extends any[]>(messages: T) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [isAtBottom, setIsAtBottom] = useState(true);
    const [showScrollButton, setShowScrollButton] = useState(false);

    // Umbral de tolerancia en pixeles para considerar que está "al final"
    const BOTTOM_THRESHOLD = 100;

    const checkScrollPosition = useCallback(() => {
        if (!containerRef.current) return;

        const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
        const scrollBottom = scrollHeight - scrollTop - clientHeight;

        const atBottom = scrollBottom < BOTTOM_THRESHOLD;
        setIsAtBottom(atBottom);
        setShowScrollButton(!atBottom);
    }, []);

    // Listener de scroll
    useEffect(() => {
        const container = containerRef.current;
        if (container) {
            container.addEventListener('scroll', checkScrollPosition);
            // Chequeo inicial
            checkScrollPosition();
        }
        return () => {
            container?.removeEventListener('scroll', checkScrollPosition);
        };
    }, [checkScrollPosition]);

    // Efecto para auto-scroll cuando llegan mensajes
    useEffect(() => {
        if (isAtBottom) {
            scrollToBottom();
        }
    }, [messages, isAtBottom]);

    const scrollToBottom = (smooth = true) => {
        messagesEndRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
    };

    return {
        containerRef,
        messagesEndRef,
        showScrollButton,
        scrollToBottom,
        isAtBottom
    };
};
