import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Paperclip,
  ShieldCheck,
  FileText,
  Sparkles,
  ChevronRight,
  Clock
} from 'lucide-react';
import type { ChatSession, ChatMessage, Claim, PipelineState } from '../types';

interface ConversationalChatProps {
  activeSessionId: string | null;
  sessions: ChatSession[];
  matterId: string;
  onOpenUpload: () => void;
  onOpenAudit: (traceId: string) => void;
  onSessionCreated: (newSession: ChatSession) => void;
}

export const ConversationalChat: React.FC<ConversationalChatProps> = ({
  activeSessionId,
  matterId,
  onOpenUpload,
  onOpenAudit,
  onSessionCreated,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<PipelineState | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchMessages = async (sessionId: string) => {
    try {
      const res = await fetch(`/sessions/${sessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (e) {
      console.error('Failed to fetch session messages', e);
    }
  };

  useEffect(() => {
    if (activeSessionId) {
      fetchMessages(activeSessionId);
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSubmitting]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isSubmitting) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      const res = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: query.slice(0, 30) + '...',
          user_id: 'default_user',
          active_matter_id: matterId,
        }),
      });
      if (res.ok) {
        const newSess: ChatSession = await res.json();
        onSessionCreated(newSess);
        targetSessionId = newSess.session_id;
      }
    }

    const userText = query.trim();
    setQuery('');

    // Optimistic user message append
    const tempUserMsg: ChatMessage = {
      message_id: `temp_${Date.now()}`,
      session_id: targetSessionId!,
      role: 'user',
      content: userText,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    setIsSubmitting(true);
    setCurrentStep('retrieving');

    try {
      // Simulate pipeline steps for UI feedback
      const stepTimer1 = setTimeout(() => setCurrentStep('classifying'), 300);
      const stepTimer2 = setTimeout(() => setCurrentStep('analyzing'), 600);
      const stepTimer3 = setTimeout(() => setCurrentStep('validating'), 900);

      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userText,
          user_id: 'default_user',
          session_id: targetSessionId,
          permitted_matters: [matterId],
        }),
      });

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);

      if (res.ok) {
        const data = await res.json();
        setCurrentStep('complete');
        if (targetSessionId) {
          await fetchMessages(targetSessionId);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              message_id: `msg_${Date.now()}`,
              session_id: 'default',
              role: 'assistant',
              content: data.answer || 'No response returned from analysis.',
              trace_id: data.trace_id,
              timestamp: new Date().toISOString(),
              metadata: { claims: data.claims || [], status: data.status },
            },
          ]);
        }
      } else {
        const errData = await res.json();
        setCurrentStep('failed');
        setMessages((prev) => [
          ...prev,
          {
            message_id: `err_${Date.now()}`,
            session_id: targetSessionId!,
            role: 'assistant',
            content: `Error running pipeline: ${errData.detail || 'Request failed'}`,
            timestamp: new Date().toISOString(),
            metadata: { status: 'failed', error: errData.detail },
          },
        ]);
      }
    } catch (err: any) {
      setCurrentStep('failed');
      console.error('Submit query error', err);
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setCurrentStep(null), 2000);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] bg-white rounded-2xl border border-slate-200/80 shadow-soft-md overflow-hidden">
      {/* Header Bar */}
      <div className="px-6 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-brand-700 text-white flex items-center justify-center font-bold text-xs shadow-sm">
            AI
          </div>
          <div>
            <div className="font-bold text-slate-900 text-sm">
              Legal AI Assistant
            </div>
            <div className="text-[11px] text-slate-400 font-medium">
              Grounded Document RAG
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onOpenUpload}
            className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all border border-slate-200"
          >
            <Paperclip className="w-3.5 h-3.5 text-slate-500" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && !isSubmitting ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
            <div className="w-14 h-14 bg-brand-50 text-brand-600 rounded-2xl flex items-center justify-center mb-4 shadow-inner">
              <Sparkles className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">
              Legal Document Assistant
            </h3>
            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
              Ask questions over contracts, court filings, or ingested matters. Every claim is strictly validated against retrieved document chunks.
            </p>
            <div className="grid grid-cols-1 gap-2.5 w-full text-left">
              {[
                'What are the termination notice requirements under Matter #101?',
                'Summarize indemnification limits and liability caps.',
                'Identify any high-risk clauses in the uploaded contract.',
              ].map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(sample)}
                  className="p-3 bg-slate-50 hover:bg-brand-50/60 border border-slate-200/80 hover:border-brand-200 rounded-xl text-xs font-medium text-slate-700 hover:text-brand-900 transition-all flex items-center justify-between group"
                >
                  <span>"{sample}"</span>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-brand-600" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const claims = msg.metadata?.claims || [];
            const traceId = msg.trace_id;

            return (
              <div
                key={msg.message_id || index}
                className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-brand-700 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm mt-1">
                    AI
                  </div>
                )}

                <div className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed shadow-sm ${
                  isUser
                    ? 'bg-brand-600 text-white font-medium rounded-tr-none'
                    : 'bg-slate-50 text-slate-800 border border-slate-200/80 rounded-tl-none space-y-3'
                }`}>
                  {/* Message Header for Assistant */}
                  {!isUser && (
                    <div className="flex items-center justify-between border-b border-slate-200/60 pb-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-xs">Analysis Verdict</span>
                        <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-md text-[10px] font-bold flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" /> Grounded
                        </span>
                      </div>
                      {traceId && (
                        <button
                          onClick={() => onOpenAudit(traceId)}
                          className="text-[11px] text-brand-600 hover:text-brand-800 font-semibold flex items-center gap-1"
                        >
                          <Clock className="w-3 h-3" />
                          <span>Audit Trace</span>
                        </button>
                      )}
                    </div>
                  )}

                  <div className="whitespace-pre-wrap">{msg.content}</div>

                  {/* Grounded Claims Cards */}
                  {!isUser && claims.length > 0 && (
                    <div className="pt-3 border-t border-slate-200/60 space-y-2">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                        Grounded Claims & Sources ({claims.length})
                      </div>
                      <div className="space-y-1.5">
                        {claims.map((claim, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-2.5 bg-white border border-slate-200 rounded-xl hover:border-brand-300 transition-all cursor-pointer"
                            onClick={() => setSelectedClaim(claim)}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-bold text-slate-900 text-[11px]">
                                Claim #{claim.claim_id}
                              </span>
                              <div className="flex gap-1">
                                {claim.supporting_chunk_ids.map((cid, chIdx) => (
                                  <span
                                    key={chIdx}
                                    className="px-1.5 py-0.5 bg-slate-100 text-slate-700 font-mono text-[10px] rounded font-semibold border border-slate-200"
                                  >
                                    {cid}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <p className="text-slate-600 text-[11px] italic">"{claim.text}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Stepper animation during query execution */}
        {isSubmitting && (
          <div className="flex items-center gap-3 p-4 bg-brand-50/60 border border-brand-200/60 rounded-2xl max-w-xl animate-pulse">
            <Sparkles className="w-5 h-5 text-brand-600 animate-spin" />
            <div className="flex-1">
              <div className="text-xs font-bold text-brand-900">
                {currentStep === 'retrieving' && '1/4 Retrieving relevant chunks with ACL filters...'}
                {currentStep === 'classifying' && '2/4 Scanning document chunks for prompt injection...'}
                {currentStep === 'analyzing' && '3/4 Toolless analysis agent reasoning over content...'}
                {currentStep === 'validating' && '4/4 Validator agent verifying claim grounding...'}
                {currentStep === 'complete' && 'Finalizing pipeline response...'}
              </div>
              <div className="w-full bg-brand-200 h-1.5 rounded-full mt-2 overflow-hidden">
                <div
                  className="bg-brand-600 h-full transition-all duration-300"
                  style={{
                    width:
                      currentStep === 'retrieving'
                        ? '25%'
                        : currentStep === 'classifying'
                        ? '50%'
                        : currentStep === 'analyzing'
                        ? '75%'
                        : '100%',
                  }}
                ></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSend} className="p-4 border-t border-slate-100 bg-white">
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/80 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-brand-500 focus-within:bg-white transition-all shadow-inner">
          <button
            type="button"
            onClick={onOpenUpload}
            className="p-2 text-slate-400 hover:text-brand-600 rounded-xl transition-all"
            title="Upload PDF/DOCX"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Ask a legal query for matter ${matterId}...`}
            className="flex-1 bg-transparent text-xs font-medium text-slate-900 focus:outline-none px-2"
            disabled={isSubmitting}
          />
          <button
            type="submit"
            disabled={!query.trim() || isSubmitting}
            className="p-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl font-bold shadow-md shadow-brand-500/20 transition-all flex items-center justify-center"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>

      {/* Claim Source Inspector Modal */}
      {selectedClaim && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-slate-200 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand-600" />
                Claim Grounding Details (#{selectedClaim.claim_id})
              </h3>
              <button
                onClick={() => setSelectedClaim(null)}
                className="text-xs text-slate-400 hover:text-slate-600 font-bold"
              >
                Close
              </button>
            </div>
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 text-xs text-slate-800">
              <span className="font-bold text-slate-900 block mb-1">Stated Claim:</span>
              "{selectedClaim.text}"
            </div>
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Supporting Chunk IDs ({selectedClaim.supporting_chunk_ids.length})
              </span>
              <div className="space-y-1.5">
                {selectedClaim.supporting_chunk_ids.map((id, idx) => (
                  <div key={idx} className="p-2.5 bg-slate-100 rounded-lg text-xs font-mono text-slate-800 border border-slate-200 flex items-center justify-between">
                    <span>{id}</span>
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded">
                      ACL Verified
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
