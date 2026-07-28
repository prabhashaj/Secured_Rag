import React from 'react';
import {
  MessageSquare,
  Plus,
  FileText,
  ShieldCheck,
  History,
  Trash2,
  Briefcase
} from 'lucide-react';
import type { ChatSession } from '../types';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  sessions: ChatSession[];
  activeSessionId: string | null;
  setActiveSessionId: (sessionId: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  matterId: string;
  setMatterId: (matterId: string) => void;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  sessions,
  activeSessionId,
  setActiveSessionId,
  onCreateSession,
  onDeleteSession,
  matterId,
  setMatterId,
  pendingApprovalsCount,
}) => {
  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    setActiveTab('query');
  };

  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 flex flex-col fixed top-0 left-0 h-screen z-50 shadow-soft-sm">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-100 flex items-center gap-3">
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

      {/* New Chat Primary Button */}
      <div className="p-3 border-b border-slate-100">
        <button
          onClick={() => {
            setActiveTab('query');
            onCreateSession();
          }}
          className="w-full py-2.5 px-3 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-bold text-xs shadow-md shadow-brand-500/20 transition-all flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Recent Chat Sessions Section */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-2">
            Recent Conversations
          </div>
          <div className="space-y-1">
            {sessions.length === 0 ? (
              <div className="text-center py-4 px-2 text-slate-400 text-[11px] font-medium">
                No recent chats.
              </div>
            ) : (
              sessions.map((s) => {
                const isActive = activeTab === 'query' && s.session_id === activeSessionId;
                return (
                  <div
                    key={s.session_id}
                    onClick={() => handleSelectSession(s.session_id)}
                    className={`group flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium cursor-pointer transition-all ${
                      isActive
                        ? 'bg-brand-50 text-brand-800 border border-brand-200/60 font-semibold shadow-sm'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
                      <span className="truncate">{s.title}</span>
                    </div>
                    <button
                      onClick={(e) => onDeleteSession(s.session_id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-600 transition-all"
                      title="Delete Chat"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Navigation Features */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-2">
            Workspace
          </div>
          <div className="space-y-1">
            <button
              onClick={() => setActiveTab('documents')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'documents'
                  ? 'bg-brand-50 text-brand-700 border border-brand-200/60 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <FileText className={`w-3.5 h-3.5 ${activeTab === 'documents' ? 'text-brand-600' : 'text-slate-400'}`} />
                <span>My Documents</span>
              </div>
            </button>

            <button
              onClick={() => setActiveTab('approvals')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'approvals'
                  ? 'bg-brand-50 text-brand-700 border border-brand-200/60 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <ShieldCheck className={`w-3.5 h-3.5 ${activeTab === 'approvals' ? 'text-brand-600' : 'text-slate-400'}`} />
                <span>Approval Queue</span>
              </div>
              {Boolean(pendingApprovalsCount && pendingApprovalsCount > 0) && (
                <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200 rounded-full">
                  {pendingApprovalsCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('audit')}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'audit'
                  ? 'bg-brand-50 text-brand-700 border border-brand-200/60 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <History className={`w-3.5 h-3.5 ${activeTab === 'audit' ? 'text-brand-600' : 'text-slate-400'}`} />
                <span>Audit Traces</span>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Active Matter Selector Footer */}
      <div className="p-3 border-t border-slate-200/60 bg-slate-50/50">
        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1 flex items-center gap-1.5">
          <Briefcase className="w-3 h-3 text-brand-600" />
          Active Matter Scope
        </label>
        <select
          value={matterId}
          onChange={(e) => setMatterId(e.target.value)}
          className="w-full text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="Matter_101">Matter #101 (Acquisition)</option>
          <option value="Matter_102">Matter #102 (Regulatory)</option>
          <option value="Matter_103">Matter #103 (Disputes)</option>
          <option value="all">All Permitted Matters</option>
        </select>
      </div>
    </aside>
  );
};
