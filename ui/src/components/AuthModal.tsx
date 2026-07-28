import React, { useState } from 'react';
import { Shield, Lock, Mail, User, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, signup, error } = useAuth();
  const [isSignUp, setIsSignUp] = useState<boolean>(false);
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [fullName, setFullName] = useState<string>('');
  const [role, setRole] = useState<string>('Senior Attorney');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    let success = false;
    if (isSignUp) {
      success = await signup(email, fullName, password, role, ['Matter_101', 'Matter_102']);
    } else {
      success = await login(email, password);
    }
    setIsSubmitting(false);
    if (success) {
      onClose();
    }
  };

  const handleQuickDemoLogin = async (demoEmail: string) => {
    setIsSubmitting(true);
    const success = await login(demoEmail, 'Password123');
    setIsSubmitting(false);
    if (success) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-md w-full p-8 shadow-2xl border border-slate-200/80 space-y-6 relative overflow-hidden">
        {/* Top Gradient Banner */}
        <div className="absolute top-0 left-0 right-0 h-2 bg-gradient-to-r from-brand-600 via-indigo-600 to-purple-600"></div>

        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-brand-50 text-brand-600 rounded-2xl flex items-center justify-center font-black mx-auto shadow-inner">
            <Shield className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
            {isSignUp ? 'Create Legal Account' : 'Welcome to LEXICON RAG'}
          </h2>
          <p className="text-xs text-slate-500 font-medium">
            Multi-Tenant Legal Intelligence & Trust Boundary OS
          </p>
        </div>

        {/* Auth Toggle Tabs */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            type="button"
            onClick={() => setIsSignUp(false)}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
              !isSignUp
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => setIsSignUp(true)}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
              isSignUp
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Quick Demo Preset Buttons */}
        {!isSignUp && (
          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 text-center">
              Quick Demo Accounts
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              <button
                type="button"
                onClick={() => handleQuickDemoLogin('lawyer1@legal.com')}
                className="p-2.5 bg-slate-50 hover:bg-brand-50/60 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:text-brand-900 transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-brand-600"></span>
                  <span>Jane Doe (Senior Attorney)</span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">Matter_101, 102</span>
              </button>
              <button
                type="button"
                onClick={() => handleQuickDemoLogin('paralegal1@legal.com')}
                className="p-2.5 bg-slate-50 hover:bg-brand-50/60 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:text-brand-900 transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                  <span>Alex Smith (Paralegal)</span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">Matter_101 Only</span>
              </button>
            </div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {isSignUp && (
            <div>
              <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Eleanor Vance"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  required={isSignUp}
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@firm.com"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
          </div>

          {isSignUp && (
            <div>
              <label className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                Legal Role / Title
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="Senior Attorney">Senior Attorney</option>
                <option value="Associate Counsel">Associate Counsel</option>
                <option value="Paralegal">Paralegal</option>
                <option value="Compliance Auditor">Compliance Auditor</option>
              </select>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs flex items-center gap-2 text-red-800">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-bold text-xs shadow-md shadow-brand-500/20 transition-all flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <span>Authenticating...</span>
            ) : (
              <span>{isSignUp ? 'Create Account & Sign In' : 'Sign In to Portal'}</span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
