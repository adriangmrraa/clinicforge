import { useState, useEffect } from 'react';
import { X, Search, User, Link as LinkIcon } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  phone_number: string;
  dni?: string;
}

interface LinkGuardianModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLinked: () => void;
  currentPatientId: number;
  currentPatientName: string;
  tenantId: number;
}

export default function LinkGuardianModal({
  isOpen, onClose, onLinked, currentPatientId, currentPatientName, tenantId
}: LinkGuardianModalProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(false);
  const [linking, setLinking] = useState(false);
  const [selectedGuardian, setSelectedGuardian] = useState<Patient | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setSearch('');
      setPatients([]);
      setSelectedGuardian(null);
    }
  }, [isOpen]);

  const searchPatients = async (query: string) => {
    if (!query.trim()) {
      setPatients([]);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get('/admin/patients', { params: { search: query, limit: 20 } });
      // Excluir al paciente actual
      const filtered = (res.data || []).filter((p: Patient) => p.id !== currentPatientId);
      setPatients(filtered);
    } catch (e) {
      console.error('Error searching patients:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleLink = async () => {
    if (!selectedGuardian) return;
    setLinking(true);
    try {
      await api.patch(`/admin/patients/${currentPatientId}/link-guardian`, {
        guardian_patient_id: selectedGuardian.id
      }, { headers: { 'X-Tenant-ID': String(tenantId) } });
      onLinked();
      onClose();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Error al enlazar');
    } finally {
      setLinking(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-[#0d1117] border border-white/10 rounded-xl w-full max-w-md max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <LinkIcon size={18} className="text-purple-400" />
            <h2 className="text-lg font-medium text-white">{t('chats.link_to_family') || 'Enlazar a familiar'}</h2>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* Current patient info */}
        <div className="p-4 bg-white/[0.02] border-b border-white/10">
          <p className="text-xs text-white/40 mb-1">{t('chats.linking_patient') || 'Paciente a enlazar'}</p>
          <p className="text-white font-medium">{currentPatientName}</p>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-white/10">
          <p className="text-xs text-white/40 mb-2">
            {t('chats.select_guardian') || 'Buscar familiar (paciente existente)'}
          </p>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); searchPatients(e.target.value); }}
              placeholder={t('chats.search_patient') || 'Buscar por nombre, teléfono o DNI...'}
              className="w-full pl-9 pr-4 py-2 bg-white/[0.04] border border-white/08 rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:border-white/20"
            />
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-2">
          {loading ? (
            <p className="text-center text-white/40 p-4">{t('common.loading') || 'Cargando...'}</p>
          ) : patients.length === 0 && search ? (
            <p className="text-center text-white/40 p-4">{t('chats.no_patients_found') || 'No se encontraron pacientes'}</p>
          ) : (
            <div className="space-y-1">
              {patients.map(p => (
                <button
                  key={p.id}
                  onClick={() => setSelectedGuardian(p)}
                  className={`w-full p-3 rounded-lg text-left flex items-center gap-3 transition-colors ${
                    selectedGuardian?.id === p.id 
                      ? 'bg-purple-500/20 border border-purple-500/30' 
                      : 'hover:bg-white/[0.04] border border-transparent'
                  }`}
                >
                  <User size={16} className="text-white/40" />
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">
                      {p.first_name} {p.last_name || ''}
                    </p>
                    <p className="text-xs text-white/40 truncate">{p.phone_number}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-white/10 flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 bg-white/[0.04] hover:bg-white/[0.08] text-white/70 rounded-lg text-sm font-medium"
          >
            {t('common.cancel') || 'Cancelar'}
          </button>
          <button
            onClick={handleLink}
            disabled={!selectedGuardian || linking}
            className="flex-1 py-2 px-4 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2"
          >
            <LinkIcon size={16} />
            {linking ? (t('common.loading') || 'Enlazando...') : (t('chats.link') || 'Enlazar')}
          </button>
        </div>
      </div>
    </div>
  );
}
