import React from 'react';
import { LogIn } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  activeTab: string;
  onOpenProfile: () => void;
  onOpenAuth: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onOpenProfile,
  onOpenAuth,
}) => {
  const { user } = useAuth();

  const titles: Record<string, string> = {
    query: 'AI Legal Assistant',
    documents: 'My Documents',
    approvals: 'Approval Queue',
    audit: 'Audit Traces',
  };

  const currentTitle = titles[activeTab] || 'Lexicon AI';

  return (
    <header className="h-14 bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-40 shadow-soft-sm">
      <div>
        <h1 className="text-sm font-extrabold text-slate-900 tracking-tight">
          {currentTitle}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        {user ? (
          <button
            onClick={onOpenProfile}
            className="flex items-center gap-2.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200/80 rounded-xl text-xs font-bold text-slate-900 transition-all shadow-sm"
          >
            <div className="w-6 h-6 rounded-lg bg-brand-600 text-white font-bold flex items-center justify-center text-[10px]">
              {user.full_name.slice(0, 2).toUpperCase()}
            </div>
            <div className="text-left hidden sm:block">
              <span className="block leading-none text-xs">{user.full_name}</span>
              <span className="text-[10px] text-slate-400 font-medium block leading-tight mt-0.5">{user.role}</span>
            </div>
          </button>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
