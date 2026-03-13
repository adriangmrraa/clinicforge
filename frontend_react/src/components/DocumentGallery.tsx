import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { Upload, FileText, Image, File, Trash2, Download, Eye, X, Activity } from 'lucide-react';
import api from '../api/axios';

interface PatientDocument {
  id: number;
  filename: string;
  file_name: string;
  file_path: string;
  file_size?: number;
  mime_type?: string;
  document_type: string;
  uploaded_by?: number;
  created_at: string;
  source?: string;
  uploaded_at?: string;
}

interface DocumentGalleryProps {
  patientId: number;
  readOnly?: boolean;
}

type DocumentType = 'clinical' | 'prescription' | 'radiology' | 'consent' | 'lab' | 'other';

const DOCUMENT_TYPES: { id: DocumentType; label: string; icon: React.ReactNode }[] = [
  { id: 'clinical', label: 'document_gallery.types.clinical', icon: <FileText size={20} /> },
  { id: 'prescription', label: 'document_gallery.types.prescription', icon: <FileText size={20} /> },
  { id: 'radiology', label: 'document_gallery.types.radiology', icon: <Image size={20} /> },
  { id: 'consent', label: 'document_gallery.types.consent', icon: <File size={20} /> },
  { id: 'lab', label: 'document_gallery.types.lab', icon: <FileText size={20} /> },
  { id: 'other', label: 'document_gallery.types.other', icon: <File size={20} /> }
];

const MIME_TYPE_ICONS: Record<string, React.ReactNode> = {
  'application/pdf': <FileText className="text-red-500" size={24} />,
  'image/jpeg': <Image className="text-blue-500" size={24} />,
  'image/png': <Image className="text-green-500" size={24} />,
  'image/gif': <Image className="text-purple-500" size={24} />,
  'audio/mpeg': <Activity className="text-orange-500" size={24} />,
  'audio/ogg': <Activity className="text-orange-500" size={24} />,
  'audio/wav': <Activity className="text-orange-500" size={24} />,
  'application/msword': <FileText className="text-blue-600" size={24} />,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': <FileText className="text-blue-600" size={24} />
};

export default function DocumentGallery({ patientId, readOnly = false }: DocumentGalleryProps) {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>('clinical');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Cargar documentos
  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get(`/admin/patients/${patientId}/documents`);
      setDocuments(response.data);
    } catch (err: any) {
      console.error('Error loading documents:', err);
      setError(t('document_gallery.load_error'));
    } finally {
      setLoading(false);
    }
  }, [patientId, t]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Manejar drag & drop
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
      }
    }
  };

  const validateFile = (file: File): boolean => {
    const allowedTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/gif',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];

    if (!allowedTypes.includes(file.type)) {
      setError(t('document_gallery.invalid_type'));
      return false;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB
      setError(t('document_gallery.size_limit'));
      return false;
    }

    setError(null);
    return true;
  };

  const handleUpload = async () => {
    if (!selectedFile || uploading) return;

    setUploading(true);
    setError(null);
    setSuccess(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('document_type', documentType);

    try {
      await api.post(`/admin/patients/${patientId}/documents`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setSuccess(t('document_gallery.upload_success'));
      setSelectedFile(null);
      await loadDocuments();

      // Limpiar mensaje después de 3 segundos
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Error uploading document:', err);
      setError(err.response?.data?.detail || t('document_gallery.upload_error'));
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: number) => {
    if (readOnly || !confirm(t('document_gallery.delete_confirm'))) return;

    setDeletingId(docId);
    try {
      await api.delete(`/admin/patients/${patientId}/documents/${docId}`);
      setDocuments(prev => prev.filter(doc => doc.id !== docId));
      setSuccess(t('document_gallery.delete_success'));
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Error deleting document:', err);
      setError(err.response?.data?.detail || t('document_gallery.delete_error'));
    } finally {
      setDeletingId(null);
    }
  };

  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const handlePreview = async (document: PatientDocument) => {
    if (document.mime_type?.startsWith('image/')) {
      try {
        setDownloadingId(document.id);
        const response = await api.get(`/admin/patients/${patientId}/documents/${document.id}/proxy`, {
          responseType: 'blob'
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        setPreviewUrl(url);
      } catch (err: any) {
        console.error('Error previewing document:', err);
        setError(t('document_gallery.download_error') || 'Error fetching preview');
      } finally {
        setDownloadingId(null);
      }
    } else {
      handleDownload(document);
    }
  };

  const handleDownload = async (document: PatientDocument) => {
    try {
      setDownloadingId(document.id);
      const response = await api.get(`/admin/patients/${patientId}/documents/${document.id}/proxy`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = window.document.createElement('a');
      link.href = url;
      link.setAttribute('download', document.filename);
      window.document.body.appendChild(link);
      link.click();
      window.document.body.removeChild(link);
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (err: any) {
      console.error('Error downloading document:', err);
      setError(t('document_gallery.download_error') || 'Error downloading the file');
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return t('document_gallery.size_not_available');
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (mimeType?: string): React.ReactNode => {
    if (!mimeType) return <FileText className="text-gray-400" size={24} />;
    if (mimeType.startsWith('audio/')) return <Activity className="text-orange-500" size={24} />;
    return MIME_TYPE_ICONS[mimeType] || <FileText className="text-gray-400" size={24} />;
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const handleClosePreview = () => {
    if (previewUrl && previewUrl.startsWith('blob:')) {
      window.URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-6 border-b">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{t('document_gallery.title')}</h3>
            <p className="text-sm text-gray-500">{t('document_gallery.subtitle')}</p>
          </div>
          <div className="text-sm text-gray-500">
            {t('document_gallery.count', { count: documents.length })}
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Mensajes de estado */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            <span className="text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg">
            <span className="text-sm">{success}</span>
          </div>
        )}

        {/* Área de upload */}
        {!readOnly && (
          <div className="mb-8">
            <div
              className={`
                border-2 border-dashed rounded-lg p-4 sm:p-8 text-center transition-colors
                ${dragActive ? 'border-primary bg-primary/5' : 'border-gray-300 hover:border-primary'}
                ${selectedFile ? 'bg-green-50 border-green-300' : ''}
              `}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              {selectedFile ? (
                <div className="space-y-4">
                  <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                    {getFileIcon(selectedFile.type)}
                    <div className="text-center sm:text-left break-all">
                      <p className="font-medium text-gray-800">{selectedFile.name}</p>
                      <p className="text-sm text-gray-500">
                        {formatFileSize(selectedFile.size)} • {selectedFile.type}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedFile(null)}
                      className="p-1 hover:bg-gray-100 rounded"
                    >
                      <X size={18} />
                    </button>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        {t('document_gallery.select_type')}
                      </label>
                      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                        {DOCUMENT_TYPES.map(type => (
                          <button
                            key={type.id}
                            onClick={() => setDocumentType(type.id)}
                            className={`
                              flex flex-col items-center p-3 rounded-lg border transition-colors
                              ${documentType === type.id
                                ? 'bg-primary text-white border-primary'
                                : 'bg-white border-gray-200 hover:bg-gray-50'
                              }
                            `}
                          >
                            <div className="mb-1">{type.icon}</div>
                            <span className="text-xs">{t(type.label)}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={handleUpload}
                      disabled={uploading}
                      className="w-full flex items-center justify-center gap-2 bg-primary text-white py-3 rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Upload size={18} />
                      {uploading ? t('document_gallery.uploading') : t('document_gallery.upload_button')}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="mx-auto mb-4 text-gray-400" size={48} />
                  <h4 className="text-lg font-medium text-gray-700 mb-2">
                    {t('document_gallery.drag_drop_title')}
                  </h4>
                  <p className="text-gray-500 mb-4">{t('document_gallery.drag_drop_desc')}</p>
                  <label className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 cursor-pointer">
                    <Upload size={16} />
                    {t('document_gallery.browse_files')}
                    <input
                      type="file"
                      className="hidden"
                      onChange={handleFileSelect}
                      accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx"
                    />
                  </label>
                  <p className="mt-3 text-xs text-gray-400">
                    {t('document_gallery.supported_formats')}
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {/* Lista de documentos */}
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
            <p className="mt-2 text-gray-500">{t('document_gallery.loading')}</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="mx-auto mb-4 text-gray-300" size={48} />
            <h4 className="text-lg font-medium text-gray-700 mb-2">
              {t('document_gallery.no_documents_title')}
            </h4>
            <p className="text-gray-500">{t('document_gallery.no_documents_desc')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map(document => (
              <div
                key={document.id}
                className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="shrink-0">
                      {getFileIcon(document.mime_type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-800 truncate" title={document.filename}>
                        {document.filename}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="inline-flex items-center px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                          {t(`document_gallery.types.${document.document_type}`)}
                        </span>
                        <span className="text-xs text-gray-500">
                          {formatFileSize(document.file_size)}
                        </span>
                        {document.source && (
                          <span className="inline-flex items-center px-1.5 py-0.5 bg-gray-100 text-gray-600 text-[10px] rounded uppercase font-bold">
                            {document.source}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-2">
                        {t('document_gallery.uploaded_on')} {formatDate(document.uploaded_at || document.created_at)}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="border-t px-4 py-3 bg-gray-50">
                  <div className="flex justify-end gap-2">
                    {document.mime_type?.startsWith('image/') && (
                      <button
                        onClick={() => handlePreview(document)}
                        disabled={downloadingId === document.id}
                        className={`p-2 text-gray-600 hover:text-primary hover:bg-gray-100 rounded ${downloadingId === document.id ? 'opacity-50 cursor-wait' : ''}`}
                        title={t('document_gallery.preview')}
                      >
                        <Eye size={16} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDownload(document)}
                      disabled={downloadingId === document.id}
                      className={`p-2 text-gray-600 hover:text-primary hover:bg-gray-100 rounded ${downloadingId === document.id ? 'opacity-50 cursor-wait' : ''}`}
                      title={t('document_gallery.download')}
                    >
                      <Download size={16} />
                    </button>
                    {!readOnly && (
                      <button
                        onClick={() => handleDelete(document.id)}
                        disabled={deletingId === document.id}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
                        title={t('document_gallery.delete')}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal de preview con Adaptación Mobile */}
      {previewUrl && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-end sm:items-center justify-center z-50">
          <div className="bg-white w-full sm:max-w-4xl h-[90vh] sm:h-auto sm:max-h-[90vh] rounded-t-xl sm:rounded-lg overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-4 border-b shrink-0 bg-white">
              <h3 className="font-semibold text-gray-800">{t('document_gallery.preview_title')}</h3>
              <button
                onClick={handleClosePreview}
                className="p-1 hover:bg-gray-100 rounded-full bg-gray-50"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-auto bg-gray-50 p-4 flex items-center justify-center">
              <img
                src={previewUrl}
                alt="Preview"
                className="max-w-full max-h-full object-contain mx-auto"
              />
            </div>

            <div className="p-4 border-t flex flex-col sm:flex-row justify-end gap-3 bg-white shrink-0">
              <button
                onClick={handleClosePreview}
                className="w-full sm:w-auto px-4 py-3 sm:py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 font-medium"
              >
                {t('common.close')}
              </button>
              <a
                href={previewUrl}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto flex justify-center items-center px-4 py-3 sm:py-2 text-white bg-primary rounded-lg hover:bg-primary-dark font-medium"
              >
                <Download size={16} className="mr-2" />
                {t('document_gallery.download')}
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}