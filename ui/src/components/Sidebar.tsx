import React from 'react';
import { MessageSquare, FileText, ShieldCheck, History } from 'lucide-react';

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
    { id: 'query', label: 'AI Assistant', icon: MessageSquare },
    { id: 'documents', label: 'My Documents', icon: FileText },
    { id: 'approvals', label: 'Approval Queue', icon: ShieldCheck, badge: pendingApprovalsCount },
    { id: 'audit', label: 'Audit Traces', icon: History },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 flex flex-col fixed top-0 left-0 h-screen z-50 shadow-soft-sm">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-100 flex items-center gap-3">
        <div className="w-9 h-9 bg-gradient-to-br from-brand-600 to-brand-700 text-white rounded-xl flex items-center justify-center font-extrabold text-sm shadow-md shadow-brand-500/20">
          LX
        </div>
        <div>
          <div className="font-extrabold text-base tracking-tight text-slate-900">
            LEXICON <span className="text-brand-600 font-bold text-xs">AI</span>
          </div>
          <div className="text-[10px] text-slate-400 font-bold tracking-wider uppercase">
            Legal Assistant
          </div>
        </div>
      </div>

      {/* Clean Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
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
                <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200 rounded-full">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </aside>
  );
};
