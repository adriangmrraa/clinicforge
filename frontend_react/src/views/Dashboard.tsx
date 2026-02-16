import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { useTranslation } from '../context/LanguageContext';
import { Activity, Server, MessageSquare, Users } from 'lucide-react';

interface Stats {
    active_tenants: number;
    total_messages: number;
    processed_messages: number;
}

interface HealthCheck {
    name: string;
    status: 'OK' | 'FAIL' | 'WARN';
    details?: string;
}

interface HealthData {
    status: string;
    checks: HealthCheck[];
}

export const Dashboard: React.FC = () => {
    const { t } = useTranslation();
    const { fetchApi, loading } = useApi();
    const [stats, setStats] = useState<Stats | null>(null);
    const [health, setHealth] = useState<HealthData | null>(null);
    const [lastSync, setLastSync] = useState<string>('');

    useEffect(() => {
        const loadData = async () => {
            try {
                const [statsData, healthData] = await Promise.all([
                    fetchApi('/admin/stats'),
                    fetchApi('/admin/diagnostics/healthz')
                ]);
                setStats(statsData);
                setHealth(healthData);
                setLastSync(new Date().toLocaleTimeString());
            } catch (e) {
                console.error(e);
            }
        };
        loadData();
        const interval = setInterval(loadData, 30000); // Refresh every 30s
        return () => clearInterval(interval);
    }, [fetchApi]);

    const getServiceStatus = (serviceName: string) => {
        const check = health?.checks?.find(c => c.name === serviceName);
        if (!check) return { color: 'var(--text-secondary)', status: 'UNKNOWN' };
        if (check.status === 'OK') return { color: 'var(--success)', status: 'OK' };
        if (check.status === 'FAIL') return { color: '#ff4d4d', status: 'FAIL' };
        return { color: '#ffc107', status: 'WARN' };
    };

    return (
        <div className="view active">
            <div className="top-bar" style={{ marginBottom: '20px' }}>
                <div className="health-strip">
                    {['orchestrator', 'whatsapp_service', 'database', 'redis'].map(svc => {
                        const { color, status } = getServiceStatus(svc);
                        return (
                            <div key={svc} className="service-pill" style={{ borderColor: color }}>
                                <div className="pill-dot" style={{ backgroundColor: color }}></div>
                                {svc.replace('_service', '')}: {status}
                            </div>
                        );
                    })}
                </div>
                <div className="last-signals">
                    <span className="signal-label">{t('dashboard.last_sync')}: {lastSync || t('dashboard.never')}</span>
                </div>
            </div>

            <h1 className="view-title">{t('dashboard.panel_title')}</h1>

            <div className="stats-grid">
                <div className="stat-card glass accent">
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className="stat-label">{t('dashboard.active_tenants')}</span>
                        <Users className="stat-icon" size={20} color="var(--accent)" />
                    </div>
                    <span className="stat-value">{stats?.active_tenants || 0}</span>
                    <span className="stat-meta">{t('dashboard.stores_connected')}</span>
                </div>

                <div className="stat-card glass">
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className="stat-label">{t('dashboard.total_messages')}</span>
                        <MessageSquare className="stat-icon" size={20} color="var(--text-secondary)" />
                    </div>
                    <span className="stat-value">{stats?.total_messages || 0}</span>
                    <span className="stat-meta">{t('dashboard.processed_today')}</span>
                </div>

                <div className="stat-card glass">
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className="stat-label">{t('dashboard.success_rate')}</span>
                        <Activity className="stat-icon" size={20} color="var(--success)" />
                    </div>
                    <span className="stat-value">
                        {stats?.total_messages ? Math.round((stats.processed_messages / stats.total_messages) * 100) : 0}%
                    </span>
                    <span className="stat-meta">{t('dashboard.responses_generated')}</span>
                </div>
            </div>
        </div>
    );
};
