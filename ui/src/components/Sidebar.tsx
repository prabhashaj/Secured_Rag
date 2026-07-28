import React from 'react';
import { Search, FileText, FilePlus, ShieldCheck, History } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  pendingApprovalsCount,
}) => {
  const navItems = [
    { id: 'query', label: 'Query Assistant', icon: Search, category: 'Core Pipeline' },
    { id: 'documents', label: 'Uploaded Documents', icon: FileText, category: 'Core Pipeline' },
    { id: 'ingest', label: 'Document Ingestion', icon: FilePlus, category: 'Core Pipeline' },
    { id: 'approvals', label: 'Approval Gate', icon: ShieldCheck, category: 'Governance', badge: pendingApprovalsCount },
    { id: 'audit', label: 'Audit Logs & Traces', icon: History, category: 'Governance' },
  ];

  return (
    <aside className="w-72 bg-white border-r border-slate-200/80 flex flex-col fixed top-0 left-0 h-screen z-50 shadow-soft-sm">
      {/* Brand Header */}
      <div className="p-6 border-b border-slate-100 flex items-center gap-3.5">
        <div className="w-10 h-10 bg-gradient-to-br from-brand-600 to-brand-700 text-white rounded-xl flex items-center justify-center font-extrabold text-base shadow-md shadow-brand-500/20">
          LX
        </div>
        <div>
          <div className="font-extrabold text-base tracking-tight text-slate-900">
            LEXICON <span className="text-brand-600 font-bold text-xs ml-0.5">RAG</span>
          </div>
          <div className="text-[11px] text-slate-400 font-semibold tracking-wider uppercase">
            Legal Intelligence OS
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-7 overflow-y-auto">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 px-3 mb-3">
            Core Pipeline
          </div>
          <div className="space-y-1.5">
            {navItems.filter(i => i.category === 'Core Pipeline').map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 border border-brand-200/60 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400 px-3 mb-3">
            Governance & Audit
          </div>
          <div className="space-y-1.5">
            {navItems.filter(i => i.category === 'Governance').map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 border border-brand-200/60 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {Boolean(item.badge && item.badge > 0) && (
                    <span className="px-2 py-0.5 text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Footer Status */}
      <div className="p-5 border-t border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2.5 text-xs text-slate-600 font-medium">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-100"></span>
          <span>Trust Boundaries Enforced</span>
        </div>
      </div>
    </aside>
  );
};
