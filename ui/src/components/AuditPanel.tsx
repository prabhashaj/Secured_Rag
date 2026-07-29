import React, { useState, useEffect } from 'react';
import {
  History,
  Layers,
  ShieldCheck,
  Download,
  Search,
  CheckCircle,
  Lock,
  Unlock,
  Copy,
  Check,
  RefreshCw,
  AlertCircle,
  FileCode,
} from 'lucide-react';
import type { TraceSummary } from '../types';
import { apiFetch } from '../lib/api';

export const AuditPanel: React.FC = () => {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedExecutionPath, setSelectedExecutionPath] = useState<string>('all');
  const [selectedVerdict, setSelectedVerdict] = useState<string>('all');
  const [showRawJson, setShowRawJson] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedTraceId, setCopiedTraceId] = useState<string | null>(null);

  useEffect(() => {
    loadTraces();
  }, []);

  const loadTraces = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiFetch('/audit/traces');
      if (res.ok) {
        const data = await res.json();
        setTraces(data || []);
        if (data && data.length > 0 && !selectedTraceId) {
          loadTraceDetail(data[0].trace_id);
        }
      } else {
        setErrorMessage(`Couldn't load audit traces (HTTP ${res.status}). Try refreshing.`);
      }
    } catch (e: any) {
      console.error('Error fetching traces', e);
      setErrorMessage(e.message || "Couldn't load audit traces — try refreshing.");
    } finally {
      setIsLoading(false);
    }
  };

  const loadTraceDetail = async (traceId: string) => {
    setSelectedTraceId(traceId);
    setTraceDetail(null);
    setShowRawJson(false);
    try {
      const res = await apiFetch(`/audit/trace/${traceId}`);
      if (res.ok) {
        const data = await res.json();
        setTraceDetail(data);
      }
    } catch (e) {
      console.error('Error loading trace detail', e);
    }
  };

  const handleExport = async (format: 'json' | 'csv') => {
    try {
      const res = await apiFetch(`/audit/export?format=${format}`);
      if (res.ok) {
        const result = await res.json();
        const blob = new Blob([result.data], {
          type: format === 'csv' ? 'text/csv' : 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `lexicon_audit_log.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error('Failed to export audit log', e);
    }
  };

  const handleCopyTraceId = (traceId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(traceId);
    setCopiedTraceId(traceId);
    setTimeout(() => setCopiedTraceId(null), 2000);
  };

  // Filter traces by search query, execution path, and verdict
  const filteredTraces = traces.filter((t) => {
    const matchesSearch =
      t.trace_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.message_types && t.message_types.toLowerCase().includes(searchQuery.toLowerCase()));

    const execPath = t.execution_path || 'pipeline';
    const matchesPath = selectedExecutionPath === 'all' || execPath === selectedExecutionPath;

    const verdict = t.security_verdict || 'clean';
    const matchesVerdict = selectedVerdict === 'all' || verdict === selectedVerdict;

    return matchesSearch && matchesPath && matchesVerdict;
  });

  const totalTraces = traces.length;
  const cleanCount = traces.filter((t) => (t.security_verdict || 'clean') === 'clean').length;
  const suspiciousCount = traces.filter((t) => t.security_verdict === 'suspicious').length;
  const blockedCount = traces.filter((t) => t.security_verdict === 'blocked').length;

  const renderPathBadge = (path?: string) => {
    const p = path || 'pipeline';
    if (p === 'websearch_llm') {
      return (
        <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded font-mono text-[10px] font-bold">
          websearch_llm
        </span>
      );
    }
    if (p === 'direct_llm') {
      return (
        <span className="px-2 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded font-mono text-[10px] font-bold">
          direct_llm
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded font-mono text-[10px] font-bold">
        pipeline
      </span>
    );
  };

  const renderVerdictBadge = (verdict?: string) => {
    const v = verdict || 'clean';
    if (v === 'blocked') {
      return (
        <span className="px-2 py-0.5 bg-red-50 text-red-700 border border-red-200 rounded text-[10px] font-bold uppercase">
          blocked
        </span>
      );
    }
    if (v === 'suspicious') {
      return (
        <span className="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[10px] font-bold uppercase">
          suspicious
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-bold uppercase">
        clean
      </span>
    );
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center justify-between text-xs text-red-800">
          <div className="flex items-center gap-2 font-semibold">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={loadTraces}
            className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white font-bold rounded-lg transition-all"
          >
            Retry
          </button>
        </div>
      )}

      {/* Top Overview Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200/80 rounded-2xl p-4.5 shadow-soft-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center font-bold">
            <History className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Traces</div>
            <div className="text-xl font-extrabold text-slate-900">{totalTraces}</div>
          </div>
        </div>

        {/* Security Scans breakdown card */}
        <div className="bg-white border border-slate-200/80 rounded-2xl p-4.5 shadow-soft-sm flex items-center gap-4 group relative cursor-pointer">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Security Scans</div>
            <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5 mt-0.5">
              <span className="text-emerald-600">{cleanCount} Clean</span>
              <span className="text-slate-300">•</span>
              <span className="text-amber-600">{suspiciousCount} Susp.</span>
              <span className="text-slate-300">•</span>
              <span className="text-red-600">{blockedCount} Blocked</span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200/80 rounded-2xl p-4.5 shadow-soft-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <CheckCircle className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Trust Level</div>
            <div className="text-xl font-extrabold text-slate-900">100% Audited</div>
          </div>
        </div>

        <div className="bg-white border border-slate-200/80 rounded-2xl p-4.5 shadow-soft-sm flex items-center gap-4 justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Export Audit Logs</div>
              <div className="text-xs font-bold text-slate-700">JSON / CSV</div>
            </div>
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => handleExport('json')}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-[11px] font-bold border border-slate-200"
            >
              JSON
            </button>
            <button
              onClick={() => handleExport('csv')}
              className="px-2.5 py-1 bg-brand-50 hover:bg-brand-100 text-brand-700 rounded-lg text-[11px] font-bold border border-brand-200"
            >
              CSV
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Trace Index List & Filters */}
        <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-soft-md space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <History className="w-4 h-4 text-brand-600" />
              <span>Audit Trace Index ({filteredTraces.length})</span>
            </div>
            <button
              onClick={loadTraces}
              disabled={isLoading}
              className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-all border border-slate-200"
              title="Refresh Traces"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-slate-600 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Search & Filters Toolbar */}
          <div className="space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search trace ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={selectedExecutionPath}
                onChange={(e) => setSelectedExecutionPath(e.target.value)}
                className="w-1/2 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-[11px] font-semibold text-slate-700 focus:outline-none"
              >
                <option value="all">All Paths</option>
                <option value="pipeline">Pipeline</option>
                <option value="direct_llm">Direct LLM</option>
                <option value="websearch_llm">Web Search</option>
              </select>

              <select
                value={selectedVerdict}
                onChange={(e) => setSelectedVerdict(e.target.value)}
                className="w-1/2 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-[11px] font-semibold text-slate-700 focus:outline-none"
              >
                <option value="all">All Verdicts</option>
                <option value="clean">Clean</option>
                <option value="suspicious">Suspicious</option>
                <option value="blocked">Blocked</option>
              </select>
            </div>
          </div>

          {filteredTraces.length === 0 ? (
            <div className="text-xs text-slate-400 py-12 text-center font-medium">
              {errorMessage ? (
                "Couldn't load audit traces — try refreshing."
              ) : (
                "No traces recorded yet — traces appear here after your first query."
              )}
            </div>
          ) : (
            <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
              {filteredTraces.map((t) => {
                const isSelected = selectedTraceId === t.trace_id;
                const isCopied = copiedTraceId === t.trace_id;
                return (
                  <button
                    key={t.trace_id}
                    onClick={() => loadTraceDetail(t.trace_id)}
                    className={`w-full text-left p-3.5 rounded-xl text-xs transition-all border ${
                      isSelected
                        ? 'bg-brand-50/70 border-brand-400 text-brand-900 font-bold shadow-soft-sm ring-1 ring-brand-300'
                        : 'bg-slate-50/80 border-slate-200/80 text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-xs mb-1.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-brand-700 font-bold truncate">
                          {t.trace_id.substring(0, 10)}...
                        </span>
                        <span
                          onClick={(e) => handleCopyTraceId(t.trace_id, e)}
                          className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-700 transition-colors"
                          title="Copy full trace_id"
                        >
                          {isCopied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 bg-slate-200/60 text-slate-700 rounded text-[10px] font-semibold">
                        {t.message_count || 0} msgs
                      </span>
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-200/50 text-[11px]">
                      {renderPathBadge(t.execution_path)}
                      {renderVerdictBadge(t.security_verdict)}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Trace Graph Trajectory Inspector */}
        <div className="md:col-span-2 bg-white border border-slate-200/80 rounded-2xl p-6 shadow-soft-md space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <Layers className="w-4 h-4 text-brand-600" />
              <span>Trace Trajectory Inspector</span>
            </div>
            {selectedTraceId && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-xl text-xs font-bold text-slate-700 border border-slate-200 flex items-center gap-1.5 transition-all"
                >
                  <FileCode className="w-3.5 h-3.5 text-slate-500" />
                  <span>{showRawJson ? 'Timeline View' : 'View Raw JSON'}</span>
                </button>
              </div>
            )}
          </div>

          {!selectedTraceId ? (
            <div className="py-24 text-center text-sm text-slate-400 font-medium">
              Select a trace from the index on the left to inspect its hop-by-hop agent trajectory and security evidence.
            </div>
          ) : !traceDetail ? (
            <div className="py-24 text-center text-sm text-slate-500 font-medium animate-pulse">
              Reconstructing trace trajectory...
            </div>
          ) : showRawJson ? (
            <div className="bg-slate-900 text-emerald-400 p-4 rounded-xl font-mono text-xs overflow-x-auto max-h-[520px]">
              <pre>{JSON.stringify(traceDetail, null, 2)}</pre>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Summary Header Bar */}
              <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <span className="text-slate-400 font-bold block mb-0.5">User Query:</span>
                  <span className="font-semibold text-slate-900">
                    "{traceDetail.user_query || 'System Query / Legal Search'}"
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {renderPathBadge(traceDetail.execution_path)}
                  {renderVerdictBadge(traceDetail.security_verdict)}
                </div>
              </div>

              {/* Trajectory Steps Timeline (Hop-by-hop) */}
              <div className="space-y-4 relative pl-6 border-l-2 border-slate-200">
                {(traceDetail.stages || []).map((stage: any, idx: number) => {
                  const isTrusted = stage.trust_level === 'trusted';
                  return (
                    <div key={idx} className="relative">
                      <div
                        className={`absolute -left-[31px] top-2 w-4 h-4 rounded-full border-2 border-white shadow-sm flex items-center justify-center ${
                          isTrusted
                            ? 'bg-emerald-500 text-white ring-2 ring-emerald-100'
                            : 'bg-amber-500 text-white ring-2 ring-amber-100'
                        }`}
                      >
                        {isTrusted ? <Lock className="w-2.5 h-2.5" /> : <Unlock className="w-2.5 h-2.5" />}
                      </div>
                      <div className="bg-slate-50/90 border border-slate-200/90 rounded-xl p-4 space-y-2.5 shadow-soft-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-bold text-slate-900">
                            Hop #{stage.step || idx + 1}: {stage.message_type}
                          </span>
                          <span
                            className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded-md border flex items-center gap-1 ${
                              isTrusted
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {isTrusted ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                            <span>{stage.trust_level}</span>
                          </span>
                        </div>

                        <div className="text-xs text-slate-600 font-medium flex items-center gap-2">
                          <span className="px-2 py-0.5 bg-slate-200/70 rounded font-mono text-[11px] text-slate-800">
                            {stage.sender}
                          </span>
                          <span>&rarr;</span>
                          <span className="px-2 py-0.5 bg-slate-200/70 rounded font-mono text-[11px] text-slate-800">
                            {stage.recipient}
                          </span>
                        </div>

                        <div className="bg-white p-3 rounded-lg border border-slate-200 font-mono text-xs text-slate-800 overflow-x-auto shadow-soft-sm">
                          <pre>{JSON.stringify(stage.payload_summary || {}, null, 2)}</pre>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
