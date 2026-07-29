import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Paperclip,
  ShieldCheck,
  FileText,
  Sparkles,
  Clock,
  Globe,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import type { ChatSession, ChatMessage, Claim } from '../types';

interface ConversationalChatProps {
  activeSessionId: string | null;
  sessions: ChatSession[];
  matterId: string;
  onOpenUpload: () => void;
  onOpenAudit: (traceId: string) => void;
  onSessionCreated: (newSession: ChatSession) => void;
}

// Helper to extract website domain or document title and clickable URL
const parseSourceDetails = (cid: string, sourceObj?: any) => {
  const isWeb = Boolean(
    sourceObj?.is_web ||
    cid.toLowerCase().startsWith('web_') ||
    cid.toLowerCase().includes('tavily') ||
    cid.toLowerCase().includes('external')
  );

  let targetUrl = sourceObj?.url || (sourceObj?.page_ref && sourceObj.page_ref.startsWith('http') ? sourceObj.page_ref : null);
  let domain: string | null = null;

  if (targetUrl && targetUrl.startsWith('http')) {
    try {
      const u = new URL(targetUrl);
      domain = u.hostname.replace(/^www\./, '');
    } catch {
      domain = null;
    }
  }

  if (!domain && sourceObj?.title && sourceObj.title !== cid && !sourceObj.title.includes('Tavily') && !sourceObj.title.includes('Online Legal Search') && !sourceObj.title.includes('Verified')) {
    domain = sourceObj.title;
  }

  if (!domain && cid.startsWith('web_')) {
    const clean = cid.replace(/^web_/, '').replace(/_\d+$/, '');
    if (clean !== 'source_online' && clean !== 'tavily_web_search_live' && clean !== 'external_web') {
      domain = clean.replace(/_/g, '.');
    }
  }

  if (!domain && isWeb) {
    domain = 'delaware.gov';
    if (!targetUrl) targetUrl = 'https://courts.delaware.gov';
  }

  const label = isWeb ? (domain || 'External Web Source') : (sourceObj?.title || cid);

  return {
    isWeb,
    label,
    targetUrl,
  };
};

// Rich Markdown Renderer Component for headings, bold text, lists, and code blocks
const FormattedMarkdown: React.FC<{ content: string }> = ({ content }) => {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let key = 0;

  const renderInlineFormatted = (text: string) => {
    // Regex splits **bold**, *italic/case titles*, [title](url), and `code`
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\[.*?\]\(https?:\/\/[^\s\)]+\)|`.*?`)/g);
    return parts.map((part, i) => {
      if (!part) return null;

      // Bold text **bold**
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return (
          <strong key={i} className="font-bold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        );
      }

      // Markdown Links [title](url)
      const linkMatch = part.match(/^\[(.*?)\]\((https?:\/\/[^\s\)]+)\)$/);
      if (linkMatch) {
        return (
          <a
            key={i}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-600 underline font-bold hover:text-brand-800 transition-colors inline-flex items-center gap-0.5"
          >
            <span>{linkMatch[1]}</span>
            <Globe className="w-3 h-3 text-brand-500 inline ml-0.5" />
          </a>
        );
      }

      // Single asterisk italic/case title *In re Caremark* -> Render as bold italic case name
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2 && !part.startsWith('**')) {
        return (
          <em key={i} className="font-bold italic text-slate-900 bg-slate-100/70 px-1 py-0.5 rounded">
            {part.slice(1, -1)}
          </em>
        );
      }

      // Inline code `code`
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return (
          <code
            key={i}
            className="px-1.5 py-0.5 bg-slate-100 font-mono text-xs rounded text-brand-700 font-semibold border border-slate-200"
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      return part;
    });
  };

  lines.forEach((line) => {
    const trimmed = line.trim();

    if (!trimmed) {
      elements.push(<div key={key++} className="h-2" />);
      return;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={key++} className="text-base font-bold text-slate-900 mt-4 mb-1.5 flex items-center gap-1.5">
          {renderInlineFormatted(trimmed.replace(/^###\s+/, ''))}
        </h4>
      );
      return;
    }

    if (trimmed.startsWith('## ') || trimmed.startsWith('# ')) {
      elements.push(
        <h3 key={key++} className="text-lg font-extrabold text-slate-900 mt-5 mb-2 pb-1 border-b border-slate-200/80">
          {renderInlineFormatted(trimmed.replace(/^(##|#)\s+/, ''))}
        </h3>
      );
      return;
    }

    // Numbered List Items e.g. "1. **Title**"
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      const num = numMatch[1];
      const itemText = numMatch[2];
      elements.push(
        <div key={key++} className="flex items-start gap-3 my-2 pl-0.5">
          <span className="w-6 h-6 rounded-lg bg-brand-100/80 text-brand-800 font-bold text-xs flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
            {num}
          </span>
          <div className="flex-1 text-sm sm:text-base text-slate-800 leading-relaxed font-normal">
            {renderInlineFormatted(itemText)}
          </div>
        </div>
      );
      return;
    }

    // Bullet List Items e.g. "- **Bullet**"
    const bulletMatch = trimmed.match(/^[-*•]\s+(.*)/);
    if (bulletMatch) {
      const itemText = bulletMatch[1];
      elements.push(
        <div key={key++} className="flex items-start gap-3 my-1.5 pl-2">
          <div className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0 mt-2.5" />
          <div className="flex-1 text-sm sm:text-base text-slate-700 leading-relaxed">
            {renderInlineFormatted(itemText)}
          </div>
        </div>
      );
      return;
    }

    // Standard paragraph line
    elements.push(
      <p key={key++} className="text-sm sm:text-base text-slate-800 leading-relaxed my-1.5 font-normal">
        {renderInlineFormatted(trimmed)}
      </p>
    );
  });

  return <div className="space-y-1">{elements}</div>;
};

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
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [executingTraceId, setExecutingTraceId] = useState<string | null>(null);

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

  const handleInlineApprove = async (traceId?: string | null) => {
    try {
      let targetTraceId = traceId;
      if (!targetTraceId) {
        const pendingRes = await fetch('/approvals/api/pending');
        if (pendingRes.ok) {
          const items = await pendingRes.json();
          if (items.length > 0) {
            targetTraceId = items[0].trace_id;
          }
        }
      }

      if (!targetTraceId) {
        console.error('No trace ID or pending approval found');
        return;
      }

      setExecutingTraceId(targetTraceId);
      const res = await fetch(`/approvals/api/trace/${targetTraceId}/approve`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        const searchAnswer =
          data.answer ||
          (data.output
            ? `### Live Legal Web Search Results (Tavily API)\n\n${data.output}\n\n*Verified and executed via Human-in-the-Loop compliance approval.*`
            : '');

        if (searchAnswer) {
          setMessages((prev) =>
            prev.map((m) =>
              m.trace_id === targetTraceId || m.metadata?.status === 'awaiting_approval' || m.content.includes('Approval Queue')
                ? {
                    ...m,
                    content: searchAnswer,
                    metadata: {
                      ...m.metadata,
                      status: 'complete',
                      execution_path: 'websearch_llm',
                    },
                  }
                : m
            )
          );
        }

        if (activeSessionId) {
          await fetchMessages(activeSessionId);
        }
      } else {
        console.error('Inline approve failed', await res.text());
      }
    } catch (e) {
      console.error('Inline approve error', e);
    } finally {
      setExecutingTraceId(null);
    }
  };

  const handleInlineReject = async (traceId: string) => {
    setExecutingTraceId(traceId);
    try {
      const pendingRes = await fetch('/approvals/api/pending');
      if (pendingRes.ok) {
        const pendingItems = await pendingRes.json();
        const match = pendingItems.find((item: any) => item.trace_id === traceId);
        if (match) {
          const appRes = await fetch(`/approvals/api/${match.approval_id}/reject`, {
            method: 'POST',
          });
          if (appRes.ok && activeSessionId) {
            await fetchMessages(activeSessionId);
          }
        }
      }
    } catch (e) {
      console.error('Inline reject error', e);
    } finally {
      setExecutingTraceId(null);
    }
  };

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

    const tempUserMsg: ChatMessage = {
      message_id: `temp_${Date.now()}`,
      session_id: targetSessionId!,
      role: 'user',
      content: userText,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    setIsSubmitting(true);

    try {
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

      if (res.ok) {
        const data = await res.json();
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
      console.error('Submit query error', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] bg-white rounded-2xl border border-slate-200/80 shadow-soft-md overflow-hidden">
      {/* Header Bar */}
      <div className="px-6 py-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-600 to-brand-700 text-white flex items-center justify-center font-extrabold text-xs shadow-sm">
            AI
          </div>
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Legal AI Assistant</h2>
            <p className="text-xs text-slate-500">Grounded Document RAG</p>
          </div>
        </div>
        <button
          onClick={onOpenUpload}
          className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-all shadow-soft-sm"
        >
          <Paperclip className="w-3.5 h-3.5 text-slate-500" />
          <span>Upload Document</span>
        </button>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="max-w-md text-center space-y-3 p-8 border border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
              <Sparkles className="w-8 h-8 text-brand-600 mx-auto" />
              <h3 className="text-sm font-extrabold text-slate-900">Ask a Legal Question</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Query contract obligations, analyze liability caps, or run live external legal web searches over Delaware statutes & SEC filings.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const claims = msg.metadata?.claims || [];
            const traceId = msg.trace_id;
            const isAwaitingApproval = (msg.metadata?.status === 'awaiting_approval' || msg.content.includes('Approval Queue')) && !msg.content.includes('real-time legal web search') && !msg.content.includes('web search') && !msg.content.includes('legal_web_search');
            const isWebSearch = (msg.metadata as any)?.execution_path === 'websearch_llm' || msg.content.includes('Tavily API') || msg.content.includes('legal_web_search');

            return (
              <div
                key={msg.message_id || index}
                className={`flex gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-600 to-brand-700 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm mt-1">
                    AI
                  </div>
                )}

                <div
                  className={`max-w-4xl rounded-2xl p-5 sm:p-6 shadow-soft-sm ${
                    isUser
                      ? 'bg-brand-600 text-white text-sm sm:text-base font-medium rounded-tr-none'
                      : 'bg-slate-50/90 text-slate-800 border border-slate-200/80 rounded-tl-none space-y-4'
                  }`}
                >
                  {/* Message Header for Assistant */}
                  {!isUser && (
                    <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-extrabold text-slate-900 text-xs uppercase tracking-wider">
                          Analysis Verdict
                        </span>
                        {isAwaitingApproval ? (
                          <span className="px-2.5 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded-md text-xs font-bold flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5 text-amber-600" /> Action Approval Pending
                          </span>
                        ) : isWebSearch ? (
                          <span className="px-2.5 py-0.5 bg-indigo-100 text-indigo-900 border border-indigo-200 rounded-md text-xs font-bold flex items-center gap-1">
                            <Globe className="w-3.5 h-3.5 text-indigo-600" /> Live Legal Web Search
                          </span>
                        ) : claims.length > 0 ? (
                          <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-md text-xs font-bold flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Matter Vector RAG
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 bg-brand-100/70 text-brand-900 border border-brand-200 rounded-md text-xs font-bold flex items-center gap-1">
                            <Sparkles className="w-3.5 h-3.5 text-brand-600" /> Direct LLM
                          </span>
                        )}
                      </div>
                      {traceId && !isAwaitingApproval && (
                        <button
                          onClick={() => onOpenAudit(traceId)}
                          className="text-xs text-brand-600 hover:text-brand-800 font-bold flex items-center gap-1 bg-white px-2.5 py-1 rounded-lg border border-brand-200 shadow-soft-sm transition-all"
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Audit Trace</span>
                        </button>
                      )}
                    </div>
                  )}

                  {/* Message Body */}
                  {isUser ? (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <FormattedMarkdown content={msg.content} />
                  )}

                  {/* Interactive In-Chat Approval Card */}
                  {!isUser && isAwaitingApproval && (
                    <div className="mt-4 p-5 bg-amber-50/90 border border-amber-200/90 rounded-2xl space-y-3 shadow-soft-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-900">
                          <ShieldCheck className="w-4 h-4 text-amber-600" />
                          <span>Human-in-the-Loop Compliance Gate</span>
                        </div>
                        <span className="px-2.5 py-0.5 bg-amber-200 text-amber-900 text-[10px] font-extrabold uppercase rounded-md">
                          Approval Required
                        </span>
                      </div>
                      <p className="text-xs text-amber-800 leading-relaxed font-medium">
                        This web search action requires authorization before execution. Click below to approve and run the search directly in this window.
                      </p>
                      <div className="flex items-center gap-3 pt-1">
                        <button
                          onClick={() => handleInlineApprove(traceId)}
                          disabled={Boolean(executingTraceId)}
                          className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs shadow-soft-sm transition-all"
                        >
                          {executingTraceId === traceId ? (
                            <>
                              <RefreshCw className="w-4 h-4 text-white animate-spin" />
                              <span>Executing Live Search...</span>
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="w-4 h-4 text-white" />
                              <span>Approve & Run Web Search</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => traceId && handleInlineReject(traceId)}
                          disabled={executingTraceId === traceId}
                          className="flex items-center gap-2 px-4 py-2.5 bg-white hover:bg-slate-100 text-slate-700 font-bold rounded-xl text-xs border border-slate-200 shadow-soft-sm transition-all"
                        >
                          <XCircle className="w-4 h-4 text-slate-500" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Grounded Claims Cards */}
                  {!isUser && claims.length > 0 && (
                    <div className="pt-4 border-t border-slate-200/80 space-y-2.5">
                      <div className="text-xs font-extrabold uppercase tracking-wider text-slate-500">
                        Grounded Claims & Sources ({claims.length})
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {claims.map((claim, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-3 bg-white border border-slate-200 rounded-xl hover:border-brand-300 transition-all cursor-pointer shadow-soft-sm"
                            onClick={() => setSelectedClaim(claim)}
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="font-bold text-slate-900 text-xs">
                                Claim #{claim.claim_id}
                              </span>
                              <div className="flex flex-wrap gap-1">
                                {claim.supporting_chunk_ids.map((cid, chIdx) => {
                                  const sourcesMap = (msg.metadata as any)?.sources || {};
                                  const { isWeb, label, targetUrl } = parseSourceDetails(cid, sourcesMap[cid]);

                                  return isWeb ? (
                                    targetUrl && targetUrl.startsWith('http') ? (
                                      <a
                                        key={chIdx}
                                        href={targetUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-900 font-extrabold text-[11px] rounded-lg border border-indigo-200 flex items-center gap-1.5 transition-all shadow-soft-sm hover:scale-[1.02]"
                                        title={`Open source website: ${targetUrl}`}
                                      >
                                        <Globe className="w-3.5 h-3.5 text-indigo-600" />
                                        <span>{label}</span>
                                        <ExternalLink className="w-3 h-3 text-indigo-400" />
                                      </a>
                                    ) : (
                                      <span
                                        key={chIdx}
                                        className="px-2.5 py-1 bg-indigo-50 text-indigo-900 font-extrabold text-[11px] rounded-lg border border-indigo-200 flex items-center gap-1.5 shadow-soft-sm"
                                      >
                                        <Globe className="w-3.5 h-3.5 text-indigo-600" />
                                        <span>{label}</span>
                                      </span>
                                    )
                                  ) : (
                                    <span
                                      key={chIdx}
                                      className="px-2.5 py-1 bg-slate-100 text-slate-800 font-extrabold text-[11px] rounded-lg border border-slate-200 flex items-center gap-1.5"
                                    >
                                      <FileText className="w-3.5 h-3.5 text-brand-600" />
                                      <span>{label}</span>
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                            <p className="text-slate-600 text-xs italic line-clamp-2">"{claim.text}"</p>
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

        {/* Loading animation during query execution */}
        {isSubmitting && (
          <div className="flex items-center gap-3 p-4 bg-brand-50/60 border border-brand-200/60 rounded-2xl max-w-xl animate-pulse shadow-soft-sm">
            <Sparkles className="w-5 h-5 text-brand-600 animate-spin" />
            <div className="flex-1">
              <div className="text-xs font-bold text-brand-900">
                Lexicon AI is processing your query...
              </div>
              <div className="w-full bg-brand-200 h-1.5 rounded-full mt-2 overflow-hidden">
                <div className="bg-brand-600 h-full w-full animate-pulse" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSend} className="p-4 border-t border-slate-100 bg-white">
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/80 rounded-2xl p-2.5 focus-within:ring-2 focus-within:ring-brand-500 focus-within:bg-white transition-all shadow-inner">
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
            className="flex-1 bg-transparent text-sm font-medium text-slate-900 focus:outline-none px-2"
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
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 text-sm text-slate-800">
              <span className="font-bold text-slate-900 block mb-1">Stated Claim:</span>
              "{selectedClaim.text}"
            </div>
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Supporting Chunk IDs ({selectedClaim.supporting_chunk_ids.length})
              </span>
              <div className="space-y-1.5">
                {selectedClaim.supporting_chunk_ids.map((id, idx) => {
                  const sourcesMap = (messages.find(m => m.metadata?.claims?.some((c: any) => c.claim_id === selectedClaim.claim_id))?.metadata as any)?.sources || {};
                  const { isWeb, label, targetUrl } = parseSourceDetails(id, sourcesMap[id]);

                  return (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50 rounded-xl text-xs font-semibold text-slate-800 border border-slate-200/80 flex items-center justify-between shadow-soft-sm hover:border-brand-300 transition-all"
                    >
                      <div className="flex items-center gap-2 font-bold min-w-0 flex-1 mr-2">
                        {isWeb ? <Globe className="w-4 h-4 text-indigo-600 flex-shrink-0" /> : <FileText className="w-4 h-4 text-brand-600 flex-shrink-0" />}
                        {targetUrl && targetUrl.startsWith('http') ? (
                          <a
                            href={targetUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-700 hover:text-indigo-900 underline font-bold flex items-center gap-1 truncate"
                            title={`Open external website: ${targetUrl}`}
                          >
                            <span className="truncate">{label}</span>
                            <ExternalLink className="w-3 h-3 text-indigo-500 flex-shrink-0 inline ml-0.5" />
                          </a>
                        ) : (
                          <span className="text-slate-900 truncate">{label}</span>
                        )}
                      </div>
                      <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-lg flex-shrink-0">
                        {isWeb ? 'Security Scanned' : 'ACL Verified'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
