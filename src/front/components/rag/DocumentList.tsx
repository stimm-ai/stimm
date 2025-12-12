'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Trash2, FileText, FileType, File as FileIcon } from 'lucide-react';

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  chunk_count: number;
  created_at: string;
}

interface DocumentListProps {
  ragConfigId: string;
  refreshTrigger?: number;
}

export function DocumentList({
  ragConfigId,
  refreshTrigger,
}: DocumentListProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `http://localhost:8001/api/rag-configs/${ragConfigId}/documents`
      );
      if (!response.ok) {
        throw new Error(`Failed to load documents: ${response.statusText}`);
      }

      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [ragConfigId]);

  useEffect(() => {
    loadDocuments();
  }, [ragConfigId, refreshTrigger, loadDocuments]);

  const handleDelete = async (documentId: string) => {
    if (
      !confirm(
        'Are you sure you want to delete this document? This will remove all its chunks from the vector database.'
      )
    ) {
      return;
    }

    try {
      setDeleting(documentId);

      const response = await fetch(
        `http://localhost:8001/api/rag-configs/${ragConfigId}/documents/${documentId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        throw new Error('Failed to delete document');
      }

      // Reload documents after deletion
      await loadDocuments();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to delete document'
      );
    } finally {
      setDeleting(null);
    }
  };

  const getFileIcon = (fileType: string) => {
    switch (fileType) {
      case 'pdf':
        return <FileText className="h-4 w-4" />;
      case 'docx':
        return <FileType className="h-4 w-4" />;
      default:
        return <FileIcon className="h-4 w-4" />;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Loading documents...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600">{error}</p>
        <Button variant="outline" onClick={loadDocuments} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 border-2 border-dashed rounded-lg">
        <FileIcon className="h-12 w-12 mx-auto mb-4 text-gray-300" />
        <h3 className="text-lg font-semibold mb-2">No documents yet</h3>
        <p className="text-muted-foreground">
          Upload your first document to get started
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h4 className="font-medium">{documents.length} document(s)</h4>
        <Button variant="ghost" size="sm" onClick={loadDocuments}>
          Refresh
        </Button>
      </div>

      <div className="space-y-2">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div className="mt-1 text-gray-600">
                  {getFileIcon(doc.file_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <h5 className="font-medium truncate">{doc.filename}</h5>
                  <div className="flex flex-wrap gap-3 mt-1 text-sm text-gray-500">
                    <span className="capitalize">{doc.file_type}</span>
                    <span>•</span>
                    <span>{formatFileSize(doc.file_size_bytes)}</span>
                    <span>•</span>
                    <span>
                      {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Uploaded {formatDate(doc.created_at)}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDelete(doc.id)}
                disabled={deleting === doc.id}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                {deleting === doc.id ? (
                  'Deleting...'
                ) : (
                  <>
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete
                  </>
                )}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
