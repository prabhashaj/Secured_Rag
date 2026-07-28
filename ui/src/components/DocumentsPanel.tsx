import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Filter,
  Trash2,
  Upload,
  ShieldCheck,
  AlertTriangle,
  Database,
  Layers,
  RefreshCw,
  Briefcase
} from 'lucide-react';

interface DocumentItem {
  source_doc_id: string;
  source_doc_title: string;
  matter_id: string;
  confidentiality_tag: 'public' | 'confidential' | 'privileged' | string;
  chunks_count: number;
  injection_flagged: boolean;
}

interface DocumentsPanelProps {
  onOpenUpload: () => void;
  onSelectMatterForQuery?: (matterId: string) => void;
}

export const DocumentsPanel: React.FC<DocumentsPanelProps> = ({
  onOpenUpload,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedMatter, setSelectedMatter] = useState<string>('all');
  const [selectedTag, setSelectedTag] = useState<string>('all');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/documents');
      if (res.ok) {
        const data: DocumentItem[] = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error('Failed to fetch documents', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete document '${docId}'?`)) return;

    try {
      const res = await fetch(`/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.source_doc_id !== docId));
      }
    } catch (e) {
      console.error('Failed to delete document', e);
    }
  };

  // Extract unique matters
  const uniqueMatters = Array.from(new Set(documents.map((d) => d.matter_id)));

  // Filtered documents
  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      doc.source_doc_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.source_doc_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.matter_id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesMatter = selectedMatter === 'all' || doc.matter_id === selectedMatter;
    const matchesTag = selectedTag === 'all' || doc.confidentiality_tag === selectedTag;

    return matchesSearch && matchesMatter && matchesTag;
  });

  const totalChunks = documents.reduce((acc, curr) => acc + curr.chunks_count, 0);
  const flaggedCount = documents.filter((d) => d.injection_flagged).length;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-soft-sm">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center font-extrabold shadow-sm">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
                Uploaded Documents Repository
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                View, filter, and manage ingested legal files across all matter permission groups
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchDocuments}
            disabled={isLoading}
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all border border-slate-200"
            title="Refresh List"
          >
            <RefreshCw className={`w-4 h-4 text-slate-500 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onOpenUpload}
            className="px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-bold shadow-md shadow-brand-500/20 transition-all flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            <span>Upload New Document</span>
          </button>
        </div>
      </div>

      {/* Analytics Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft-sm flex items-center gap-4">
          <div className="w-11 h-11 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center font-bold">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-bold uppercase tracking-wider block">
              Total Documents
            </span>
            <span className="text-2xl font-extrabold text-slate-900">{documents.length}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft-sm flex items-center gap-4">
          <div className="w-11 h-11 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center font-bold">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-bold uppercase tracking-wider block">
              Total Indexed Chunks
            </span>
            <span className="text-2xl font-extrabold text-slate-900">{totalChunks}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft-sm flex items-center gap-4">
          <div className="w-11 h-11 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center font-bold">
            <Briefcase className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-bold uppercase tracking-wider block">
              Active Matter Groups
            </span>
            <span className="text-2xl font-extrabold text-slate-900">{uniqueMatters.length}</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-soft-sm flex items-center gap-4">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center font-bold ${
            flaggedCount > 0 ? 'bg-amber-50 text-amber-600' : 'bg-slate-50 text-slate-400'
          }`}>
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-bold uppercase tracking-wider block">
              Injection Flagged Docs
            </span>
            <span className={`text-2xl font-extrabold ${flaggedCount > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
              {flaggedCount}
            </span>
          </div>
        </div>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-soft-sm flex flex-col md:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by title, doc_id, or matter..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          <select
            value={selectedMatter}
            onChange={(e) => setSelectedMatter(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">All Matters</option>
            {uniqueMatters.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>

          <select
            value={selectedTag}
            onChange={(e) => setSelectedTag(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">All Confidentiality Tags</option>
            <option value="public">Public</option>
            <option value="confidential">Confidential</option>
            <option value="privileged">Privileged</option>
          </select>
        </div>
      </div>

      {/* Document Grid / Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-soft-sm overflow-hidden">
        {filteredDocuments.length === 0 ? (
          <div className="text-center py-16 px-4">
            <Database className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-sm font-bold text-slate-800 mb-1">No Documents Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mb-4">
              No ingested documents match your current filter criteria. Upload new files to populate the repository.
            </p>
            <button
              onClick={onOpenUpload}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-bold shadow-md shadow-brand-500/20 transition-all inline-flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Document</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3.5 px-6">Document Details</th>
                  <th className="py-3.5 px-4">Matter Group</th>
                  <th className="py-3.5 px-4">Confidentiality</th>
                  <th className="py-3.5 px-4">Indexed Chunks</th>
                  <th className="py-3.5 px-4">Security Scan</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {filteredDocuments.map((doc) => (
                  <tr key={doc.source_doc_id} className="hover:bg-slate-50/80 transition-all group">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center font-bold flex-shrink-0 group-hover:bg-brand-50 group-hover:text-brand-600 transition-all">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <span className="font-bold text-slate-900 text-xs block truncate max-w-xs">
                            {doc.source_doc_title}
                          </span>
                          <span className="text-[11px] font-mono text-slate-400 block truncate">
                            ID: {doc.source_doc_id}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-4 px-4">
                      <span className="px-2.5 py-1 bg-slate-100 text-slate-800 font-semibold rounded-lg border border-slate-200 text-[11px]">
                        {doc.matter_id}
                      </span>
                    </td>

                    <td className="py-4 px-4">
                      <span className={`px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase tracking-wider border ${
                        doc.confidentiality_tag === 'privileged'
                          ? 'bg-purple-50 text-purple-800 border-purple-200'
                          : doc.confidentiality_tag === 'confidential'
                          ? 'bg-amber-50 text-amber-800 border-amber-200'
                          : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      }`}>
                        {doc.confidentiality_tag}
                      </span>
                    </td>

                    <td className="py-4 px-4">
                      <span className="font-bold text-slate-900 text-xs">{doc.chunks_count} chunks</span>
                    </td>

                    <td className="py-4 px-4">
                      {doc.injection_flagged ? (
                        <span className="px-2.5 py-1 bg-red-100 text-red-800 border border-red-200 rounded-lg text-[11px] font-bold flex items-center gap-1.5 w-fit">
                          <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                          <span>Flagged Injection</span>
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-[11px] font-bold flex items-center gap-1.5 w-fit">
                          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Clean</span>
                        </span>
                      )}
                    </td>

                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={(e) => handleDelete(doc.source_doc_id, e)}
                        className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                        title="Delete Document"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
