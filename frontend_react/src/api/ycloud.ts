/**
 * API wrapper for YCloud sync endpoints.
 * Handles full WhatsApp message synchronization from YCloud.
 */

import api from './axios';

/** Sync progress response from backend */
export interface YCloudSyncProgress {
    task_id: string;
    status: 'queued' | 'processing' | 'completed' | 'error' | 'cancelled';
    messages_fetched: number;
    messages_saved: number;
    media_downloaded: number;
    errors: string[];
    started_at: string;
    completed_at: string | null;
    last_sync_at: string | null;
}

/** Sync config response from backend */
export interface YCloudSyncConfig {
    sync_enabled: boolean;
    max_messages: number;
    ycloud_api_key_configured: boolean;
    last_sync_at: string | null;
    rate_limited: boolean;
    rate_limit_until: string | null;
}

/** Start sync request body */
export interface StartSyncBody {
    tenant_id: number;
    password: string;
}

/**
 * Start a YCloud sync for a tenant.
 * Requires CEO password verification.
 */
export async function startYCloudSync(tenantId: number, password: string): Promise<{ task_id: string; message: string }> {
    const res = await api.post<{ task_id: string; message: string }>('/admin/ycloud/sync/start', {
        tenant_id: tenantId,
        password,
    });
    return res.data;
}

/**
 * Get sync progress for a task.
 */
export async function getSyncStatus(taskId: string): Promise<YCloudSyncProgress> {
    const res = await api.get<YCloudSyncProgress>(`/admin/ycloud/sync/status/${taskId}`);
    return res.data;
}

/**
 * Cancel a running sync task.
 */
export async function cancelSync(taskId: string): Promise<{ cancelled: boolean; message: string }> {
    const res = await api.post<{ cancelled: boolean; message: string }>(`/admin/ycloud/sync/cancel/${taskId}`);
    return res.data;
}

/**
 * Get sync configuration and status for a tenant.
 */
export async function getSyncConfig(tenantId: number): Promise<YCloudSyncConfig> {
    const res = await api.get<YCloudSyncConfig>(`/admin/ycloud/sync/config?tenant_id=${tenantId}`);
    return res.data;
}

/**
 * Update sync configuration for a tenant.
 */
export async function updateSyncConfig(
    tenantId: number,
    config: { sync_enabled?: boolean; max_messages?: number }
): Promise<YCloudSyncConfig> {
    const res = await api.patch<YCloudSyncConfig>(`/admin/ycloud/sync/config/${tenantId}`, config);
    return res.data;
}