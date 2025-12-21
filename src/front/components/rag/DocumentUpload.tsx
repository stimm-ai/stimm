'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Upload, X, FileText, FileType, File as FileIcon } from 'lucide-react';

interface DocumentUploadProps {
  ragConfigId: string;
  onUploadComplete?: () => void;
}

interface UploadingFile {
  file: File;
  progress: number;
  status: 'uploading' | 'success' | 'error';
  error?: string;
}

export function DocumentUpload({
  ragConfigId,
  onUploadComplete,
}: DocumentUploadProps) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return <FileText className="h-5 w-5" />;
      case 'docx':
      case 'doc':
        return <FileType className="h-5 w-5" />;
      default:
        return <FileIcon className="h-5 w-5" />;
    }
  };

  const uploadFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const filesArray = Array.from(files);
      const initialFiles: UploadingFile[] = filesArray.map((file) => ({
        file,
        progress: 0,
        status: 'uploading' as const,
      }));

      setUploadingFiles((prev) => [...prev, ...initialFiles]);

      for (let i = 0; i < filesArray.length; i++) {
        const file = filesArray[i];
        const formData = new FormData();
        // Validate file name before appending to form data
        if (file && file.name) {
          formData.append('files', file);
        } else {
          console.warn('Invalid file object:', file);
          continue;
        }

        try {
          const API_URL =
            process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
          const response = await fetch(
            `${API_URL}/api/rag-configs/${ragConfigId}/documents/upload`,
            {
              method: 'POST',
              body: formData,
            }
          );

          if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
          }

          await response.json();

          setUploadingFiles((prev) =>
            prev.map((f, idx) =>
              f.file === file
                ? { ...f, progress: 100, status: 'success' as const }
                : f
            )
          );
        } catch (error) {
          setUploadingFiles((prev) =>
            prev.map((f) =>
              f.file === file
                ? {
                    ...f,
                    status: 'error' as const,
                    error:
                      error instanceof Error ? error.message : 'Upload failed',
                  }
                : f
            )
          );
        }
      }

      // Notify parent component
      if (onUploadComplete) {
        setTimeout(onUploadComplete, 1000);
      }
    },
    [ragConfigId, onUploadComplete]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      uploadFiles(e.dataTransfer.files);
    },
    [uploadFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    uploadFiles(e.target.files);
  };

  const removeFile = (file: File) => {
    setUploadingFiles((prev) => prev.filter((f) => f.file !== file));
  };

  const clearCompleted = () => {
    setUploadingFiles((prev) => prev.filter((f) => f.status === 'uploading'));
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragging
            ? 'border-primary bg-primary/5'
            : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
        <p className="text-lg font-medium mb-2">Drag and drop files here</p>
        <p className="text-sm text-gray-500 mb-4">or click to browse</p>
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".pdf,.docx,.doc,.txt,.md"
          onChange={handleFileInput}
          className="hidden"
        />
        <Button asChild variant="outline">
          <label htmlFor="file-upload" className="cursor-pointer">
            Choose Files
          </label>
        </Button>
        <p className="text-xs text-gray-400 mt-4">
          Supported: PDF, DOCX, TXT, MD
        </p>
      </div>

      {/* Upload Progress */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h4 className="font-medium">
              Uploading {uploadingFiles.length} file(s)
            </h4>
            <Button variant="ghost" size="sm" onClick={clearCompleted}>
              Clear Completed
            </Button>
          </div>
          {uploadingFiles.map((uploadFile, idx) => (
            <div key={idx} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getFileIcon(uploadFile.file.name)}
                  <span className="text-sm font-medium truncate max-w-xs">
                    {uploadFile.file.name}
                  </span>
                  <span className="text-xs text-gray-500">
                    ({(uploadFile.file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {uploadFile.status === 'success' && (
                    <span className="text-xs text-green-600 font-medium">
                      ✓ Uploaded
                    </span>
                  )}
                  {uploadFile.status === 'error' && (
                    <span className="text-xs text-red-600 font-medium">
                      ✗ Failed
                    </span>
                  )}
                  {uploadFile.status !== 'uploading' && (
                    <button
                      onClick={() => removeFile(uploadFile.file)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
              {uploadFile.status === 'uploading' && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadFile.progress}%` }}
                  />
                </div>
              )}
              {uploadFile.error && (
                <p className="text-xs text-red-600 mt-1">{uploadFile.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
