import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { ScrollText, RefreshCw } from 'lucide-react';

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    source: string;
}

export const Logs: React.FC = () => {
    const { fetchApi, loading } = useApi();
    const [logs, setLogs] = useState<LogEntry[]>([]);

    const loadLogs = async () => {
        try {
            // Note: The specific endpoint might vary, using a standard convention or 
            // what was hinted in app.js as 'loadLogs' -> adminFetch('/admin/logs')?
            // If /admin/logs doesn't exist, we might need to fallback to console events
            const data = await fetchApi('/admin/logs?limit=50');
            if (Array.isArray(data)) {
                setLogs(data);
            } else if (data.logs) {
                setLogs(data.logs);
            }
        } catch (e) {
            console.error("Failed to load logs", e);
        }
    };

    useEffect(() => {
        loadLogs();
        const interval = setInterval(loadLogs, 5000); // Live poll
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="view active">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 className="view-title" style={{ margin: 0 }}>Live History</h1>
                <button className="btn-secondary" onClick={loadLogs} disabled={loading}>
                    <RefreshCw size={14} className={loading ? 'spin' : ''} style={{ marginRight: '6px' }} />
                    Actualizar
                </button>
            </div>

            <div className="glass" style={{ padding: '0', overflow: 'hidden' }}>
                <div className="table-responsive" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Nivel</th>
                                <th>Origen</th>
                                <th>Mensaje</th>
                            </tr>
                        </thead>
                        <tbody>
                            {logs.map((log, i) => (
                                <tr key={i}>
                                    <td style={{ whiteSpace: 'nowrap', fontSize: '11px', color: '#a1a1aa' }}>
                                        {new Date(log.timestamp).toLocaleString()}
                                    </td>
                                    <td>
                                        <span className={`service-pill ${log.level === 'ERROR' ? 'error' : log.level === 'WARN' ? 'warning' : 'ok'}`} style={{ fontSize: '10px' }}>
                                            {log.level}
                                        </span>
                                    </td>
                                    <td style={{ fontSize: '12px' }}>{log.source || 'Orchestrator'}</td>
                                    <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{log.message}</td>
                                </tr>
                            ))}
                            {logs.length === 0 && (
                                <tr>
                                    <td colSpan={4} style={{ textAlign: 'center', padding: '30px', color: '#666' }}>
                                        No hay registros recientes.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};
