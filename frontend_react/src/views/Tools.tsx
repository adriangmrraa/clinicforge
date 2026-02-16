import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { Modal } from '../components/Modal';
import { Wrench, Plus, Settings } from 'lucide-react';

interface Tool {
    name: string;
    type: string;
    service_url?: string;
    config?: any;
}

export const Tools: React.FC = () => {
    const { fetchApi } = useApi();
    const [tools, setTools] = useState<Tool[]>([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [formData, setFormData] = useState<Tool>({ name: '', type: 'http', service_url: '', config: {} });

    const loadTools = async () => {
        try {
            const data = await fetchApi('/admin/tools');
            setTools(data || []);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        loadTools();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await fetchApi('/admin/tools', { method: 'POST', body: formData });
            setIsModalOpen(false);
            loadTools();
        } catch (e) {
            alert('Error al guardar herramienta');
        }
    };

    return (
        <div className="view active">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 className="view-title" style={{ margin: 0 }}>Herramientas Disponibles</h1>
                <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
                    <Plus size={18} style={{ marginRight: '8px' }} />
                    Nueva Herramienta
                </button>
            </div>

            <div className="glass">
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Nombre</th>
                            <th>Tipo</th>
                            <th>URL de Servicio</th>
                            <th>Configuración</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tools.map((t, i) => (
                            <tr key={i}>
                                <td style={{ fontWeight: 600 }}>{t.name}</td>
                                <td><span className="badge type">{t.type}</span></td>
                                <td style={{ fontSize: '12px', color: '#a1a1aa' }}>{t.service_url || 'N/A'}</td>
                                <td>
                                    <button className="btn-secondary" style={{ padding: '4px 8px', fontSize: '11px' }}>
                                        <Settings size={12} style={{ marginRight: '4px' }} /> Configurar
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {tools.length === 0 && (
                            <tr>
                                <td colSpan={4} style={{ textAlign: 'center', padding: '30px', color: '#666' }}>
                                    No hay herramientas configuradas. Las herramientas permiten extender las capacidades de la IA.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Nueva Herramienta">
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Nombre de la Herramienta</label>
                        <input required value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} placeholder="Ej: Buscador de Productos" />
                    </div>
                    <div className="form-group">
                        <label>Tipo</label>
                        <select value={formData.type} onChange={e => setFormData({ ...formData, type: e.target.value })}>
                            <option value="http">HTTP Request (API)</option>
                            <option value="tienda_nube">Tienda Nube Action</option>
                            <option value="function">Function Call</option>
                        </select>
                    </div>
                    {formData.type === 'http' && (
                        <div className="form-group">
                            <label>Service URL</label>
                            <input value={formData.service_url} onChange={e => setFormData({ ...formData, service_url: e.target.value })} placeholder="https://api.example.com/v1/search" />
                        </div>
                    )}
                    <div style={{ marginTop: '30px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>Cancelar</button>
                        <button type="submit" className="btn-primary">Crear Herramienta</button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};
