/**
 * Tipos para chat omnicanal (YCloud + Chatwoot).
 */

export type ChatChannel = 'whatsapp' | 'instagram' | 'facebook' | 'chatwoot';
export type ChatProvider = 'ycloud' | 'meta_direct' | 'chatwoot';

/** Item del summary unificado (Chatwoot/chat_conversations). */
export interface ChatSummaryItem {
  id: string;
  tenant_id: number;
  name: string;
  channel: string;
  provider: string;
  last_message: string;
  last_message_at: string | null;
  last_user_message_at?: string | null;
  unread_count: number;
  is_locked: boolean;
  status?: string;
  external_user_id?: string;
  avatar_url?: string | null;
  meta?: { username?: string; inbox_name?: string; customer_avatar?: string };
  last_derivhumano_at?: string | null;
}

/** Mensaje de la API /admin/chats/{id}/messages */
export interface ChatApiMessage {
  id: string;
  conversation_id: string | null;
  role: 'user' | 'assistant' | 'human_supervisor' | 'system';
  content: string;
  timestamp: string | null;
  attachments?: unknown;
  correlation_id?: string;
}
