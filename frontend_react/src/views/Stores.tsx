import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { Modal } from '../components/Modal';
import { Store, ShoppingBag, Plus, Trash2, Edit2, CheckCircle, XCircle } from 'lucide-react';

interface Tenant {
    id?: number;
    store_name: string;
    bot_phone_number: string;
    tiendanube_store_id?: string;
    tiendanube_access_token?: string;
    owner_email?: string;
    store_website?: string;
}

export const Stores: React.FC = () => {
    const { fetchApi } = useApi();
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);

    const [formData, setFormData] = useState<Tenant>({
        store_name: '',
        bot_phone_number: '',
        tiendanube_store_id: '',
        tiendanube_access_token: '',
        owner_email: '',
        store_website: ''
    });

    const loadTenants = async () => {
        try {
            const data = await fetchApi('/admin/tenants');
            setTenants(data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        loadTenants();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await fetchApi('/admin/tenants', { method: 'POST', body: formData });
            setIsModalOpen(false);
            loadTenants();
        } catch (e) {
            alert('Error al guardar tienda: ' + e.message);
        }
    };

    const handleDelete = async (phone: string) => {
        if (!confirm('¿Eliminar tienda y todos sus datos?')) return;
        try {
            await fetchApi(`/admin/tenants/${phone}`, { method: 'DELETE' });
            loadTenants();
        } catch (e) {
            alert('Error al eliminar: ' + e.message);
        }
    }

    const openEdit = (tenant: Tenant) => {
        setEditingTenant(tenant);
        setFormData(tenant);
        setIsModalOpen(true);
    };

    const openNew = () => {
        setEditingTenant(null);
        setFormData({
            store_name: '',
            bot_phone_number: '',
            tiendanube_store_id: '',
            tiendanube_access_token: '',
            owner_email: '',
            store_website: ''
        });
        setIsModalOpen(true);
    };


    return (
        <div className="view active">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
                <h1 className="view-title" style={{ margin: 0 }}>Mis Tiendas</h1>
                <button className="btn-primary" onClick={openNew}>
                    <Plus size={18} style={{ marginRight: '8px' }} />
                    Nueva Tienda
                </button>
            </div>

            <div className="glass">
                <div className="table-responsive">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Tienda / Dueño</th>
                                <th>WhatsApp Bot</th>
                                <th>Tienda Nube ID</th>
                                <th>Estado</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tenants.map(t => (
                                <tr key={t.id || t.bot_phone_number}>
                                    <td>
                                        <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <ShoppingBag size={14} color="var(--accent)" /> {t.store_name}
                                        </div>
                                        <div style={{ fontSize: '11px', color: '#a1a1aa', marginLeft: '22px' }}>{t.owner_email || 'Sin email'}</div>
                                    </td>
                                    <td>{t.bot_phone_number}</td>
                                    <td>{t.tiendanube_store_id || 'N/A'}</td>
                                    <td>
                                        {t.tiendanube_store_id ? (
                                            <span className="service-pill ok"><CheckCircle size={10} /> Conectado</span>
                                        ) : (
                                            <span className="service-pill error"><XCircle size={10} /> Sin Configurar</span>
                                        )}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <button className="btn-secondary" style={{ padding: '6px' }} onClick={() => openEdit(t)} title="Editar"><Edit2 size={14} /></button>
                                            <button className="btn-delete" style={{ padding: '6px' }} onClick={() => handleDelete(t.bot_phone_number)} title="Eliminar"><Trash2 size={14} /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {tenants.length === 0 && (
                                <tr>
                                    <td colSpan={5} style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                                        No tienes tiendas configuradas. ¡Agrega la primera!
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingTenant ? 'Editar Tienda' : 'Nueva Tienda'}>
                <form onSubmit={handleSubmit}>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>Nombre de la Tienda</label>
                            <input required value={formData.store_name} onChange={e => setFormData({ ...formData, store_name: e.target.value })} placeholder="Ej: Mi E-commerce" />
                        </div>
                        <div className="form-group">
                            <label>Teléfono del Bot (WhatsApp)</label>
                            <input required value={formData.bot_phone_number} onChange={e => setFormData({ ...formData, bot_phone_number: e.target.value })} placeholder="Ej: 54911..." />
                        </div>
                    </div>

                    <h4 style={{ color: 'var(--accent)', margin: '20px 0 10px', fontSize: '14px' }}>Integración Tienda Nube</h4>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>Store ID</label>
                            <input type="number" value={formData.tiendanube_store_id} onChange={e => setFormData({ ...formData, tiendanube_store_id: e.target.value })} placeholder="123456" />
                        </div>
                        <div className="form-group">
                            <label>Access Token</label>
                            <input type="password" value={formData.tiendanube_access_token} onChange={e => setFormData({ ...formData, tiendanube_access_token: e.target.value })} placeholder="Token de API" />
                        </div>
                    </div>

                    <div className="form-group" style={{ marginTop: '20px' }}>
                        <label>Email del Dueño</label>
                        <input value={formData.owner_email} onChange={e => setFormData({ ...formData, owner_email: e.target.value })} placeholder="admin@store.com" />
                    </div>

                    <div className="form-group">
                        <label>Website URL</label>
                        <input value={formData.store_website} onChange={e => setFormData({ ...formData, store_website: e.target.value })} placeholder="https://..." />
                    </div>

                    <div style={{ marginTop: '30px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancelar</button>
                        <button type="submit" className="btn-primary">Guardar Tienda</button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};
