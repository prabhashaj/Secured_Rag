import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, X, FileCheck } from 'lucide-react';

interface FileUploadDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const FileUploadDrawer: React.FC<FileUploadDrawerProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [matterId, setMatterId] = useState<string>('Matter_101');
  const [confidentialityTag, setConfidentialityTag] = useState<string>('public');
  const [title, setTitle] = useState<string>('');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      if (!title) {
        setTitle(selectedFile.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('matter_id', matterId);
    formData.append('confidentiality_tag', confidentialityTag);
    if (title) formData.append('title', title);

    try {
      const res = await fetch('/ingest/file', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setResult(data);
        onSuccess();
      } else {
        const err = await res.json();
        setError(err.detail || 'Upload failed');
      }
    } catch (e: any) {
      setError(e.message || 'Upload error');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex justify-end">
      <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col p-6 overflow-y-auto space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center font-bold">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-extrabold text-slate-900 text-base">Ingest Document</h2>
              <p className="text-xs text-slate-400">PDF, DOCX, TXT, MD, CSV, JSON</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleUpload} className="space-y-4 flex-1">
          {/* File Picker */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Select Document File
            </label>
            <div className="border-2 border-dashed border-slate-200 hover:border-brand-400 rounded-2xl p-6 text-center bg-slate-50/50 hover:bg-brand-50/30 transition-all cursor-pointer relative">
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.csv,.json"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <FileCheck className="w-8 h-8 text-brand-600 mx-auto mb-2" />
              {file ? (
                <div>
                  <span className="font-bold text-slate-900 text-xs block truncate">{file.name}</span>
                  <span className="text-[11px] text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
                </div>
              ) : (
                <div>
                  <span className="font-semibold text-slate-700 text-xs block mb-1">
                    Click to browse or drag file here
                  </span>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider font-bold">
                    PDF • DOCX • TXT • MD • CSV • JSON
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Document Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Master Services Agreement 2026"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Matter ID */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Matter ID (ACL Group)
            </label>
            <input
              type="text"
              value={matterId}
              onChange={(e) => setMatterId(e.target.value)}
              placeholder="e.g. Matter_101"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>

          {/* Confidentiality Level */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Confidentiality Tag
            </label>
            <select
              value={confidentialityTag}
              onChange={(e) => setConfidentialityTag(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="public">Public (All internal staff)</option>
              <option value="confidential">Confidential (Matter members only)</option>
              <option value="privileged">Privileged (Attorney-Client privilege)</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={!file || isUploading}
            className="w-full py-3 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl font-bold text-xs shadow-md shadow-brand-500/20 transition-all flex items-center justify-center gap-2 mt-4"
          >
            {isUploading ? (
              <>
                <Upload className="w-4 h-4 animate-bounce" />
                <span>Extracting & Ingesting Chunks...</span>
              </>
            ) : (
              <>
                <FileText className="w-4 h-4" />
                <span>Extract & Index Document</span>
              </>
            )}
          </button>
        </form>

        {/* Upload Success Alert */}
        {result && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs space-y-2">
            <div className="flex items-center gap-2 font-bold text-emerald-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Document Ingested Successfully!</span>
            </div>
            <div className="text-emerald-800 space-y-0.5 text-[11px]">
              <div>Doc ID: <span className="font-mono font-semibold">{result.doc_id}</span></div>
              <div>Chunks Created: <span className="font-bold">{result.chunks_count}</span></div>
              <div>Pages Extracted: <span className="font-bold">{result.pages_extracted}</span></div>
            </div>
          </div>
        )}

        {/* Upload Error Alert */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-2xl text-xs flex items-start gap-2.5 text-red-900">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block">Ingestion Failed</span>
              <span className="text-[11px] text-red-700">{error}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
