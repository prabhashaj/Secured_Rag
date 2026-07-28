import React from 'react';
import { User, Briefcase, Key, LogOut, X, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface UserProfileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UserProfileDrawer: React.FC<UserProfileDrawerProps> = ({ isOpen, onClose }) => {
  const { user, logout } = useAuth();

  if (!isOpen || !user) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex justify-end">
      <div className="w-full max-w-sm bg-white h-full shadow-2xl flex flex-col p-6 overflow-y-auto space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <h2 className="font-extrabold text-slate-900 text-base flex items-center gap-2">
            <User className="w-4 h-4 text-brand-600" />
            <span>User Profile & Security</span>
          </h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Card */}
        <div className="p-5 bg-gradient-to-br from-brand-50 to-indigo-50/60 border border-brand-100 rounded-2xl space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-brand-600 text-white font-extrabold text-lg flex items-center justify-center shadow-md shadow-brand-500/20">
              {user.full_name.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">{user.full_name}</h3>
              <p className="text-xs text-slate-500 font-medium">{user.email}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2 border-t border-brand-100/60">
            <span className="px-2.5 py-1 bg-brand-600 text-white font-bold text-[10px] rounded-lg uppercase tracking-wider shadow-sm">
              {user.role}
            </span>
            <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 font-bold text-[10px] rounded-lg border border-emerald-200 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" /> ACL Active
            </span>
          </div>
        </div>

        {/* Matter Access Permissions */}
        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400 block flex items-center gap-1.5">
            <Briefcase className="w-3.5 h-3.5 text-brand-600" />
            Assigned Matter Permission Groups
          </label>
          <div className="space-y-1.5">
            {user.permitted_matters.map((matter) => (
              <div
                key={matter}
                className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 flex items-center justify-between"
              >
                <span>{matter}</span>
                <span className="px-2 py-0.5 bg-brand-100 text-brand-800 text-[10px] font-bold rounded">
                  Full Access
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Security Info */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
            <Key className="w-3.5 h-3.5 text-brand-600" />
            <span>JWT Bearer Token Info</span>
          </div>
          <div className="text-[11px] font-mono text-slate-500 break-all bg-white p-2 rounded-lg border border-slate-200">
            {user.token.slice(0, 45)}...
          </div>
        </div>

        {/* Logout Action */}
        <div className="pt-6 border-t border-slate-100">
          <button
            onClick={() => {
              logout();
              onClose();
            }}
            className="w-full py-3 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-xl font-bold text-xs transition-all flex items-center justify-center gap-2"
          >
            <LogOut className="w-4 h-4 text-red-600" />
            <span>Log Out of Session</span>
          </button>
        </div>
      </div>
    </div>
  );
};
