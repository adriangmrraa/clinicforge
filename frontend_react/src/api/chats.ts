/**
 * API de chats unificada: summary (Chatwoot), messages, send, human-override, config Chatwoot.
 * Usa la instancia api (axios) para enviar X-Admin-Token y Authorization.
 */

import api from './axios';
import type { ChatSummaryItem, ChatApiMessage } from '../types/chat';

export async function fetchChatsSummary(params: {
  limit?: number;
  offset?: number;
  channel?: string;
  human_override?: boolean;
}): Promise<ChatSummaryItem[]> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set('limit', String(params.limit));
  if (params.offset != null) q.set('offset', String(params.offset));
  if (params.channel) q.set('channel', params.channel);
  if (params.human_override === true) q.set('human_override', 'true');
  const res = await api.get<ChatSummaryItem[]>(`/admin/chats/summary?${q}`);
  return res.data;
}

export async function fetchChatMessages(
  conversationId: string,
  params?: { limit?: number; offset?: number }
): Promise<ChatApiMessage[]> {
  const q = new URLSearchParams();
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  const res = await api.get<ChatApiMessage[]>(
    `/admin/chats/${conversationId}/messages?${q}`
  );
  return res.data;
}

export async function sendChatMessage(
  conversationId: string,
  message: string
): Promise<{ status: string }> {
  const res = await api.post<{ status: string }>('/admin/chat/send', {
    conversation_id: conversationId,
    message,
  });
  return res.data;
}

export async function setHumanOverride(
  conversationId: string,
  enabled: boolean
): Promise<{ status: string; human_override: boolean }> {
  const res = await api.post<{ status: string; human_override: boolean }>(
    `/admin/conversations/${conversationId}/human-override`,
    { enabled }
  );
  return res.data;
}

export async function markConversationRead(
  conversationId: string
): Promise<{ status: string }> {
  const res = await api.put<{ status: string }>(
    `/admin/chats/${conversationId}/read`
  );
  return res.data;
}

/** Config Chatwoot para Config/Settings (URL webhook + token). */
export async function fetchChatwootConfig(): Promise<{
  webhook_path: string;
  access_token: string;
  tenant_id: number;
  api_base: string;
  full_webhook_url: string;
}> {
  const res = await api.get<{
    webhook_path: string;
    access_token: string;
    tenant_id: number;
    api_base: string;
    full_webhook_url: string;
  }>('/admin/integrations/chatwoot/config');
  return res.data;
}
