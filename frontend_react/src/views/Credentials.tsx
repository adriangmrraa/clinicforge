import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { Modal } from '../components/Modal';
import { Key, Globe, Store, Trash2, Edit2, Plus } from 'lucide-react';

interface Credential {
    id?: number;
    name: string;
    value: string;
    category: string;
    description: string;
    scope: 'global' | 'tenant';
    tenant_id?: number | null;
}

interface Tenant {
    id: number;
    store_name: string;
}

export const Credentials: React.FC = () => {
    const { fetchApi, loading } = useApi();
    const [credentials, setCredentials] = useState<Credential[]>([]);
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [deploymentConfig, setDeploymentConfig] = useState<any>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingCred, setEditingCred] = useState<Credential | null>(null);

    // Form State
    const [formData, setFormData] = useState<Credential>({
        name: '',
        value: '',
        category: 'openai',
        description: '',
        scope: 'global',
        tenant_id: null
    });

    const loadData = async () => {
        try {
            const [credsData, tenantsData, deployData] = await Promise.all([
                fetchApi('/admin/credentials'),
                fetchApi('/admin/tenants'),
                fetchApi('/admin/config/deployment')
            ]);
            console.log('Credentials Response:', credsData);
            console.log('Tenants Response:', tenantsData);

            if (Array.isArray(credsData)) {
                setCredentials(credsData);
            } else {
                console.error('Expected array for credentials, got:', credsData);
                setCredentials([]);
            }

            if (Array.isArray(tenantsData)) {
                setTenants(tenantsData);
            } else {
                console.error('Expected array for tenants, got:', tenantsData);
                setTenants([]);
            }

            setDeploymentConfig(deployData);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (editingCred?.id) {
                // Update logic would go here if backend supported PUT /credentials/{id}
                // For now assuming the backend might only have POST/DELETE or I need to check admin_routes
                // Based on app.js, it seems we might just recreate or update.
                // Actually app.js didn't have explicit update for credentials, just create/delete?
                // Wait, editCredential in app.js fetches data but where does it save?
                // Ah, it populates the form which submits to /admin/credentials (POST).
                // So POST handles both create and update (upsert) or just create?
                // Logic in app.js: "const res = await adminFetch('/admin/credentials', 'POST', data);"
                // So it's a POST.
                await fetchApi('/admin/credentials', { method: 'POST', body: formData });
            } else {
                await fetchApi('/admin/credentials', { method: 'POST', body: formData });
            }
            setIsModalOpen(false);
            loadData();
        } catch (e) {
            alert('Error al guardar credencial: ' + e.message);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('¿Eliminar credencial?')) return;
        try {
            await fetchApi(`/admin/credentials/${id}`, { method: 'DELETE' });
            loadData();
        } catch (e) {
            alert('Error al eliminar: ' + e.message);
        }
    };

    const openEdit = (cred: Credential) => {
        setEditingCred(cred);
        setFormData(cred);
        setIsModalOpen(true);
    };

    const openNew = () => {
        setEditingCred(null);
        setFormData({
            name: '',
            value: '',
            category: 'openai',
            description: '',
            scope: 'global',
            tenant_id: null
        });
        setIsModalOpen(true);
    };

    return (
        <div className="view active">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
                <h1 className="view-title" style={{ margin: 0 }}>Gestión de Credenciales</h1>
                <button className="btn-primary" onClick={openNew}>
                    <Plus size={18} style={{ marginRight: '8px' }} />
                    Nueva Credencial
                </button>
            </div>

            {deploymentConfig && (
                <div className="glass" style={{ padding: '20px', marginBottom: '20px', borderLeft: '4px solid var(--accent)' }}>
                    <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Globe size={18} color="var(--accent)" /> Configuración de Despliegue
                    </h3>
                    <div className="form-group">
                        <label>YCloud Webhook URL</label>
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <input
                                readOnly
                                value={deploymentConfig.webhook_ycloud_url}
                                style={{ flex: 1, background: 'rgba(0,0,0,0.2)' }}
                            />
                            <button
                                className="btn-secondary"
                                onClick={() => {
                                    navigator.clipboard.writeText(deploymentConfig.webhook_ycloud_url);
                                    alert('URL copiada!');
                                }}
                            >
                                Copiar
                            </button>
                        </div>
                        <p style={{ fontSize: '11px', color: '#a1a1aa', marginTop: '5px' }}>
                            Pegá esta URL en tu panel de YCloud para recibir mensajes. (Puerto interno: {deploymentConfig.webhook_ycloud_internal_port})
                        </p>
                    </div>
                </div>
            )}

            <div className="glass" style={{ padding: '20px' }}>
                <h3 style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Globe size={18} color="var(--accent)" /> Globales (Heredadas)
                </h3>
                <div style={{ display: 'grid', gap: '10px', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                    {credentials.filter(c => c.scope === 'global').map(cred => (
                        <div key={cred.id} className="stat-card" style={{ padding: '15px', background: 'rgba(255,255,255,0.03)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                <span style={{ fontWeight: 600 }}>{cred.name}</span>
                                <span style={{ fontSize: '11px', background: 'rgba(255,255,255,0.1)', padding: '2px 8px', borderRadius: '10px' }}>{cred.category}</span>
                            </div>
                            <div style={{ fontSize: '12px', color: '#a1a1aa', marginBottom: '15px', fontFamily: 'monospace' }}>
                                ••••••••••••••••
                            </div>
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button className="btn-secondary" style={{ padding: '5px 10px', fontSize: '12px' }} onClick={() => openEdit(cred)}><Edit2 size={12} /></button>
                                <button className="btn-delete" style={{ padding: '5px 10px', fontSize: '12px' }} onClick={() => handleDelete(cred.id!)}><Trash2 size={12} /></button>
                            </div>
                        </div>
                    ))}
                </div>

                <h3 style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '10px', marginBottom: '20px', marginTop: '40px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Store size={18} color="var(--success)" /> Específicas por Tienda
                </h3>
                <div style={{ display: 'grid', gap: '10px', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                    {credentials.filter(c => c.scope === 'tenant').map(cred => (
                        <div key={cred.id} className="stat-card" style={{ padding: '15px', background: 'rgba(255,255,255,0.03)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                <span style={{ fontWeight: 600 }}>{cred.name}</span>
                                <span style={{ fontSize: '11px', background: 'rgba(0, 230, 118, 0.1)', color: 'var(--success)', padding: '2px 8px', borderRadius: '10px' }}>
                                    {tenants.find(t => t.id === cred.tenant_id)?.store_name || 'Tienda Desconocida'}
                                </span>
                            </div>
                            <div style={{ fontSize: '12px', color: '#a1a1aa', marginBottom: '15px', fontFamily: 'monospace' }}>
                                ••••••••••••••••
                            </div>
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button className="btn-secondary" style={{ padding: '5px 10px', fontSize: '12px' }} onClick={() => openEdit(cred)}><Edit2 size={12} /></button>
                                <button className="btn-delete" style={{ padding: '5px 10px', fontSize: '12px' }} onClick={() => handleDelete(cred.id!)}><Trash2 size={12} /></button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingCred ? 'Editar Credencial' : 'Nueva Credencial'}>
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Nombre Identificador</label>
                        <input
                            required
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Ej: OpenAI Key Principal"
                        />
                    </div>
                    <div className="form-group">
                        <label>Valor (Token/Key)</label>
                        <input
                            required
                            type="password"
                            value={formData.value}
                            onChange={e => setFormData({ ...formData, value: e.target.value })}
                            placeholder="sk-..."
                        />
                    </div>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>Categoría</label>
                            <select
                                value={formData.category}
                                onChange={e => setFormData({ ...formData, category: e.target.value })}
                            >
                                <option value="openai">OpenAI</option>
                                <option value="whatsapp_cloud">WhatsApp Cloud API</option>
                                <option value="chatwoot">Chatwoot API (IG/FB)</option>
                                <option value="tiendanube">Tienda Nube</option>
                                <option value="database">Database</option>
                                <option value="other">Otro</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Alcance (Scope)</label>
                            <select
                                value={formData.scope}
                                onChange={e => setFormData({ ...formData, scope: e.target.value as 'global' | 'tenant' })}
                            >
                                <option value="global">Global (Todas las tiendas)</option>
                                <option value="tenant">Específico por Tienda</option>
                            </select>
                        </div>
                    </div>

                    {formData.scope === 'tenant' && (
                        <div className="form-group">
                            <label>Asignar a Tienda</label>
                            <select
                                required
                                value={formData.tenant_id?.toString() || ''}
                                onChange={e => setFormData({ ...formData, tenant_id: parseInt(e.target.value) })}
                            >
                                <option value="">Seleccionar Tienda...</option>
                                {tenants.map(t => (
                                    <option key={t.id} value={t.id}>{t.store_name}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div className="form-group">
                        <label>Descripción (Opcional)</label>
                        <textarea
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            rows={3}
                        />
                    </div>

                    <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancelar</button>
                        <button type="submit" className="btn-primary">Guardar Credencial</button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};
