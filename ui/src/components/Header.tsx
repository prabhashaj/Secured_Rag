import React, { useState } from 'react';
import { LogIn, Info, ShieldCheck, Wrench, BookOpen, X } from 'lucide-react';
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
  const [showInfoModal, setShowInfoModal] = useState<boolean>(false);

  const titles: Record<string, string> = {
    query: 'AI Legal Assistant',
    documents: 'My Documents',
    approvals: 'Approval Queue',
    audit: 'Audit Traces',
  };

  const currentTitle = titles[activeTab] || 'Lexicon AI';

  return (
    <>
      <header className="h-14 bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-40 shadow-soft-sm">
        <div>
          <h1 className="text-sm font-extrabold text-slate-900 tracking-tight">
            {currentTitle}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowInfoModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all border border-slate-200"
            title="View Security Guidelines, Tools & Law Categories"
          >
            <Info className="w-3.5 h-3.5 text-brand-600" />
            <span className="hidden sm:inline">System & Tools Info</span>
          </button>

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

      {/* System & Tools Info Modal */}
      {showInfoModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 border border-slate-200 shadow-2xl space-y-6 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-brand-600" />
                <h3 className="font-bold text-slate-900 text-base">
                  Lexicon AI — System Architecture & Security Guidelines
                </h3>
              </div>
              <button
                onClick={() => setShowInfoModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 font-bold"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Section 1: Security Guidelines */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-700 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" />
                Enterprise Security Guidelines & Operational Guardrails
              </h4>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 text-xs text-slate-700 space-y-2">
                <p>• <strong>Role-Based Access Control (RBAC):</strong> Multi-tenant isolation ensuring users only access documents within permitted matter IDs.</p>
                <p>• <strong>Isolated Injection Scanning:</strong> Multi-layer LLM and pattern-based classifier scanning retrieved text for prompt injections.</p>
                <p>• <strong>Zero Tool-Binding Sandbox:</strong> Document synthesis agent runs without execution permissions to prevent unauthorized execution vectors.</p>
                <p>• <strong>Human-in-the-Loop Gate:</strong> Privileged external actions require explicit compliance officer sign-off in the Approval Queue.</p>
                <p>• <strong>Append-Only Audit Ledger:</strong> Every turn and envelope logged immutably in SQLite audit database.</p>
              </div>
            </div>

            {/* Section 2: Active Tools */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-700 flex items-center gap-1.5">
                <Wrench className="w-4 h-4" />
                Registered System Tools & Functions
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">🔍 legal_web_search</span>
                  <span className="text-slate-600 text-[11px]">Searches SEC filings, public dockets & statutory codes (HITL Gated & Injection Scanned).</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">📖 citation_lookup</span>
                  <span className="text-slate-600 text-[11px]">Looks up statutory codes, page references, and cross-references in matter docs.</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">📄 document_export</span>
                  <span className="text-slate-600 text-[11px]">Exports validated legal analyses to Markdown/PDF/DOCX with cryptographic hashes.</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="font-bold text-slate-900 block mb-0.5">📁 file_extractor</span>
                  <span className="text-slate-600 text-[11px]">Multi-format parser for PDF, DOCX, TXT, MD, CSV, and JSON uploads.</span>
                </div>
              </div>
            </div>

            {/* Section 3: Supported Law Categories */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-700 flex items-center gap-1.5">
                <BookOpen className="w-4 h-4" />
                Supported Legal Domain Sectors
              </h4>
              <div className="flex flex-wrap gap-1.5 text-xs">
                {[
                  'Corporate Law & Governance',
                  'Tax Law & Compliance',
                  'Employment & Labor Law',
                  'IP & Licensing',
                  'Privacy & Data Protection (GDPR/CCPA)',
                  'Commercial Contracts & M&A',
                  'Litigation & Dispute Resolution',
                ].map((cat, idx) => (
                  <span key={idx} className="px-2.5 py-1 bg-brand-50 text-brand-800 font-bold border border-brand-200 rounded-lg text-[11px]">
                    {cat}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
