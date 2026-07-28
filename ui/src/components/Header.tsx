import React from 'react';
import { RefreshCw, Server, Database, LogIn } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  activeTab: string;
  vectorCount: number;
  auditCount: number;
  onRefresh: () => void;
  isRefreshing: boolean;
  onOpenProfile: () => void;
  onOpenAuth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  vectorCount,
  auditCount,
  onRefresh,
  isRefreshing,
  onOpenProfile,
  onOpenAuth,
}) => {
  const { user } = useAuth();

  const titles: Record<string, { main: string; sub: string }> = {
    query: { main: 'Query Assistant', sub: 'ACL-Filtered Multi-Agent RAG Pipeline' },
    documents: { main: 'Uploaded Documents', sub: 'Multi-Format Legal File Repository' },
    ingest: { main: 'Document Ingestion', sub: 'Embed, Tag Scope & Ingestion Scan' },
    approvals: { main: 'Human Approval Gate', sub: 'Manual Compliance Sign-Off Queue' },
    audit: { main: 'Audit Log & Trace Inspection', sub: 'Full Message Trajectory Reconstruction' },
  };

  const current = titles[activeTab] || { main: 'Legal RAG', sub: 'Multi-Agent System' };

  return (
    <header className="h-16 bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-8 flex items-center justify-between sticky top-0 z-40 shadow-soft-sm">
      <div>
        <h1 className="text-base font-bold text-slate-900 flex items-center gap-2.5">
          {current.main}
          <span className="text-xs font-normal text-slate-500">• {current.sub}</span>
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-4 text-xs font-medium text-slate-600 bg-slate-100/70 px-3.5 py-2 rounded-xl border border-slate-200/60">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-brand-600" />
            <span>Vector Chunks: <strong className="text-slate-900 font-bold text-xs">{vectorCount}</strong></span>
          </div>
          <span className="text-slate-300">|</span>
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-brand-600" />
            <span>Audit Entries: <strong className="text-slate-900 font-bold text-xs">{auditCount}</strong></span>
          </div>
        </div>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 shadow-soft-sm transition-all active:scale-95 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-brand-600' : ''}`} />
          <span>Refresh</span>
        </button>

        {user ? (
          <button
            onClick={onOpenProfile}
            className="flex items-center gap-2.5 px-3.5 py-1.5 bg-brand-50 hover:bg-brand-100/80 border border-brand-200 rounded-xl text-xs font-bold text-brand-900 transition-all shadow-sm"
          >
            <div className="w-7 h-7 rounded-lg bg-brand-600 text-white font-bold flex items-center justify-center text-xs">
              {user.full_name.slice(0, 2).toUpperCase()}
            </div>
            <div className="text-left hidden sm:block">
              <span className="block leading-tight">{user.full_name}</span>
              <span className="text-[10px] text-brand-700 font-medium block leading-tight">{user.role}</span>
            </div>
          </button>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-bold shadow-md shadow-brand-500/20 transition-all"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
