import React, { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { Modal } from '../components/Modal';
import { Shield, Globe, Store, Trash2, Edit2, Plus, Lock, Key } from 'lucide-react';
import PageHeader from '../components/PageHeader';

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
    const { fetchApi } = useApi();
    const [credentials, setCredentials] = useState<Credential[]>([]);
    const [tenants, setTenants] = useState<Tenant[]>([]);
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
            const [credsData, tenantsData] = await Promise.all([
                fetchApi('/admin/credentials'),
                fetchApi('/admin/tenants')
            ]);

            if (Array.isArray(credsData)) {
                setCredentials(credsData);
            } else {
                setCredentials([]);
            }

            if (Array.isArray(tenantsData)) {
                setTenants(tenantsData);
            } else {
                setTenants([]);
            }
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
                await fetchApi(`/admin/credentials/${editingCred.id}`, { method: 'PUT', body: formData });
            } else {
                await fetchApi('/admin/credentials', { method: 'POST', body: formData });
            }
            setIsModalOpen(false);
            loadData();
        } catch (e: any) {
            alert('Error al guardar credencial: ' + e.message);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('¿Eliminar credencial? Esta acción no se puede deshacer.')) return;
        try {
            await fetchApi(`/admin/credentials/${id}`, { method: 'DELETE' });
            loadData();
        } catch (e: any) {
            alert('Error al eliminar: ' + e.message);
        }
    };

    const openEdit = (cred: Credential) => {
        setEditingCred(cred);
        setFormData({ ...cred, value: '••••••••' }); // Keep masked value logic
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

    const getCategoryIcon = (cat: string) => {
        switch (cat) {
            case 'openai': return <Globe size={16} className="text-green-600" />;
            case 'whatsapp_cloud': return <Key size={16} className="text-emerald-600" />;
            case 'chatwoot': return <Key size={16} className="text-blue-600" />;
            case 'icloud': return <Lock size={16} className="text-gray-600" />;
            default: return <Key size={16} className="text-indigo-600" />;
        }
    };

    return (
        <div className="p-6 max-w-7xl mx-auto">
            <div className="flex justify-between items-center mb-8">
                <PageHeader
                    title="Credenciales"
                    subtitle="Gestión segura de claves API y secretos del sistema."
                    icon={<Shield size={22} />}
                />
                <button
                    onClick={openNew}
                    className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-lg shadow-indigo-600/20 transition-all font-medium"
                >
                    <Plus size={18} />
                    Nueva Credencial
                </button>
            </div>

            <div className="space-y-8">
                {/* GLOBAL CREDENTIALS */}
                <section>
                    <div className="flex items-center gap-2 mb-4 px-1">
                        <Globe className="text-indigo-500" size={20} />
                        <h3 className="text-lg font-semibold text-gray-800">Globales (Sistema)</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {credentials.filter(c => c.scope === 'global').map(cred => (
                            <div key={cred.id} className="bg-white border border-gray-200 rounded-2xl p-5 hover:shadow-md transition-shadow group relative overflow-hidden">
                                <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500 rounded-l-2xl"></div>
                                <div className="flex justify-between items-start mb-3 pl-2">
                                    <div>
                                        <h4 className="font-semibold text-gray-800 leading-tight">{cred.name}</h4>
                                        <span className="inline-flex items-center gap-1.5 mt-1 px-2 py-0.5 rounded-md bg-gray-100 text-xs text-gray-600 font-medium">
                                            {getCategoryIcon(cred.category)}
                                            {cred.category}
                                        </span>
                                    </div>
                                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button onClick={() => openEdit(cred)} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-indigo-600 transition-colors">
                                            <Edit2 size={16} />
                                        </button>
                                        <button onClick={() => handleDelete(cred.id!)} className="p-1.5 hover:bg-rose-50 rounded-lg text-gray-400 hover:text-rose-600 transition-colors">
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                                <div className="pl-2">
                                    <div className="bg-gray-50 rounded-lg px-3 py-2 font-mono text-xs text-gray-500 border border-gray-100 flex items-center gap-2">
                                        <Lock size={12} className="text-gray-400" />
                                        ••••••••••••••••
                                    </div>
                                    {cred.description && (
                                        <p className="mt-3 text-xs text-gray-400 line-clamp-2">{cred.description}</p>
                                    )}
                                </div>
                            </div>
                        ))}
                        {credentials.filter(c => c.scope === 'global').length === 0 && (
                            <div className="col-span-full py-10 text-center border-2 border-dashed border-gray-200 rounded-2xl text-gray-400">
                                No hay credenciales globales configuradas.
                            </div>
                        )}
                    </div>
                </section>

                {/* TENANT CREDENTIALS */}
                <section>
                    <div className="flex items-center gap-2 mb-4 px-1">
                        <Store className="text-emerald-500" size={20} />
                        <h3 className="text-lg font-semibold text-gray-800">Específicas por Sede</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {credentials.filter(c => c.scope === 'tenant').map(cred => (
                            <div key={cred.id} className="bg-white border border-gray-200 rounded-2xl p-5 hover:shadow-md transition-shadow group relative overflow-hidden">
                                <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500 rounded-l-2xl"></div>
                                <div className="flex justify-between items-start mb-3 pl-2">
                                    <div>
                                        <h4 className="font-semibold text-gray-800 leading-tight">{cred.name}</h4>
                                        <div className="flex flex-wrap gap-2 mt-1">
                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 text-xs text-gray-600 font-medium">
                                                {getCategoryIcon(cred.category)}
                                                {cred.category}
                                            </span>
                                            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-100">
                                                <Store size={10} className="mr-1" />
                                                {tenants.find(t => t.id === cred.tenant_id)?.store_name || 'Desconocida'}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                                        <button onClick={() => openEdit(cred)} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-indigo-600 transition-colors">
                                            <Edit2 size={16} />
                                        </button>
                                        <button onClick={() => handleDelete(cred.id!)} className="p-1.5 hover:bg-rose-50 rounded-lg text-gray-400 hover:text-rose-600 transition-colors">
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                                <div className="pl-2">
                                    <div className="bg-gray-50 rounded-lg px-3 py-2 font-mono text-xs text-gray-500 border border-gray-100 flex items-center gap-2">
                                        <Lock size={12} className="text-gray-400" />
                                        ••••••••••••••••
                                    </div>
                                </div>
                            </div>
                        ))}
                        {credentials.filter(c => c.scope === 'tenant').length === 0 && (
                            <div className="col-span-full py-10 text-center border-2 border-dashed border-gray-200 rounded-2xl text-gray-400">
                                No hay credenciales específicas por sede.
                            </div>
                        )}
                    </div>
                </section>
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingCred ? 'Editar Credencial' : 'Nueva Credencial'}>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Nombre Identificador</label>
                        <input
                            required
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Ej: OpenAI Key Principal"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Valor (Token/Key)
                            {editingCred && <span className="ml-2 text-xs text-amber-600 font-normal">* Dejar como está para no cambiar</span>}
                        </label>
                        <div className="relative">
                            <input
                                required
                                type="password"
                                className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all font-mono text-sm"
                                value={formData.value}
                                onChange={e => setFormData({ ...formData, value: e.target.value })}
                                placeholder="sk-..."
                            />
                            <Key className="absolute left-3 top-2.5 text-gray-400" size={16} />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Categoría</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white"
                                value={formData.category}
                                onChange={e => setFormData({ ...formData, category: e.target.value })}
                            >
                                <option value="openai">OpenAI</option>
                                <option value="whatsapp_cloud">WhatsApp Cloud API</option>
                                <option value="chatwoot">Chatwoot API (IG/FB)</option>
                                <option value="tiendanube">Tienda Nube</option>
                                <option value="icloud">iCloud / Apple</option>
                                <option value="database">Database</option>
                                <option value="other">Otro</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Alcance (Scope)</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white"
                                value={formData.scope}
                                onChange={e => setFormData({ ...formData, scope: e.target.value as 'global' | 'tenant' })}
                            >
                                <option value="global">Global (Todas)</option>
                                <option value="tenant">Por Sede</option>
                            </select>
                        </div>
                    </div>

                    {formData.scope === 'tenant' && (
                        <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-100 animate-in fade-in slide-in-from-top-2">
                            <label className="block text-sm font-medium text-emerald-800 mb-1">Asignar a Sede</label>
                            <select
                                required
                                className="w-full px-4 py-2 border border-emerald-200 rounded-xl focus:ring-2 focus:ring-emerald-500 outline-none bg-white"
                                value={formData.tenant_id?.toString() || ''}
                                onChange={e => setFormData({ ...formData, tenant_id: parseInt(e.target.value) })}
                            >
                                <option value="">Seleccionar Sede...</option>
                                {tenants.map(t => (
                                    <option key={t.id} value={t.id}>{t.store_name}</option>
                                ))}
                            </select>
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Descripción (Opcional)</label>
                        <textarea
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all min-h-[80px]"
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                            rows={3}
                        />
                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t border-gray-100 mt-6">
                        <button
                            type="button"
                            className="px-4 py-2 text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-xl font-medium transition-colors"
                            onClick={() => setIsModalOpen(false)}
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2"
                        >
                            <Shield size={18} />
                            {editingCred ? 'Guardar Cambios' : 'Crear Credencial'}
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    );
};
