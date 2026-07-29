import React, { useState, useEffect } from 'react';
import { History, Layers, ShieldCheck, Download, Search, CheckCircle } from 'lucide-react';
import type { TraceSummary } from '../types';

export const AuditPanel: React.FC = () => {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showRawJson, setShowRawJson] = useState<boolean>(false);

  useEffect(() => {
    loadTraces();
  }, []);

  const loadTraces = async () => {
    try {
      const res = await fetch('/audit/traces');
      if (res.ok) {
        const data = await res.json();
        setTraces(data || []);
      }
    } catch (e) {
      console.error('Error fetching traces', e);
    }
  };

  const loadTraceDetail = async (traceId: string) => {
    setSelectedTraceId(traceId);
    setTraceDetail(null);
    setShowRawJson(false);
    try {
      const res = await fetch(`/audit/trace/${traceId}`);
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
      const res = await fetch(`/audit/export?format=${format}`);
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

  const filteredTraces = traces.filter((t) => {
    return (
      t.trace_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.message_types && t.message_types.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  const totalTraces = traces.length;
  const totalMessages = traces.reduce((acc, t) => acc + (t.message_count || 0), 0);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
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

        <div className="bg-white border border-slate-200/80 rounded-2xl p-4.5 shadow-soft-sm flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Security Scans</div>
            <div className="text-xl font-extrabold text-slate-900">{totalMessages} Envelopes</div>
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
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Export Logs</div>
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
              className="text-[11px] text-brand-600 font-bold hover:underline"
            >
              Refresh
            </button>
          </div>

          {/* Search & Filters */}
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
          </div>

          {filteredTraces.length === 0 ? (
            <div className="text-xs text-slate-400 py-12 text-center font-medium">
              No matching audit traces found.
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {filteredTraces.map((t) => {
                const isSelected = selectedTraceId === t.trace_id;
                return (
                  <button
                    key={t.trace_id}
                    onClick={() => loadTraceDetail(t.trace_id)}
                    className={`w-full text-left p-3.5 rounded-xl text-xs transition-all border ${
                      isSelected
                        ? 'bg-brand-50 border-brand-300 text-brand-900 font-bold shadow-soft-sm'
                        : 'bg-slate-50/80 border-slate-200/80 text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono text-xs mb-1 font-bold">
                      <span className="text-brand-700">{t.trace_id.substring(0, 12)}...</span>
                      <span className="px-2 py-0.5 bg-slate-200/60 text-slate-700 rounded text-[10px]">
                        {t.message_count} msgs
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
                      <span>{new Date(t.started_at).toLocaleTimeString()}</span>
                      <span className="truncate max-w-[120px]">{t.message_types}</span>
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
              <span>Trace Trajectory & Payload Inspector</span>
            </div>
            {selectedTraceId && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg text-[11px] font-bold text-slate-700 border border-slate-200"
                >
                  {showRawJson ? 'Structured View' : 'Raw JSON'}
                </button>
                <span className="text-xs font-mono text-slate-500 font-medium hidden sm:inline">
                  {selectedTraceId.substring(0, 14)}...
                </span>
              </div>
            )}
          </div>

          {!selectedTraceId ? (
            <div className="py-24 text-center text-sm text-slate-400 font-medium">
              Select a trace from the log index on the left to reconstruct its full inter-agent message trajectory and audit payload evidence.
            </div>
          ) : !traceDetail ? (
            <div className="py-24 text-center text-sm text-slate-500 font-medium animate-pulse">
              Reconstructing trace trajectory graph...
            </div>
          ) : showRawJson ? (
            <div className="bg-slate-900 text-emerald-400 p-4 rounded-xl font-mono text-xs overflow-x-auto max-h-[500px]">
              <pre>{JSON.stringify(traceDetail, null, 2)}</pre>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Summary Header Bar */}
              <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between text-xs">
                <div>
                  <span className="text-slate-400 font-bold block mb-0.5">User Query:</span>
                  <span className="font-semibold text-slate-800">
                    "{traceDetail.user_query || 'System Query / Legal Search'}"
                  </span>
                </div>
                <div className="flex gap-2">
                  <span
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold uppercase border ${
                      traceDetail.security_verdict === 'clean'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                  >
                    Verdict: {traceDetail.security_verdict}
                  </span>
                </div>
              </div>

              {/* Trajectory Steps Timeline */}
              <div className="space-y-4 relative pl-5 border-l-2 border-slate-200">
                {traceDetail.stages.map((stage: any, idx: number) => {
                  const isTrusted = stage.trust_level === 'trusted';
                  return (
                    <div key={idx} className="relative">
                      <div
                        className={`absolute -left-[27px] top-2 w-3.5 h-3.5 rounded-full border-2 border-white shadow-sm ${
                          isTrusted
                            ? 'bg-emerald-500 ring-2 ring-emerald-100'
                            : 'bg-amber-500 ring-2 ring-amber-100'
                        }`}
                      />
                      <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-4 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-bold text-slate-900">
                            Step #{stage.step}: {stage.message_type}
                          </span>
                          <span
                            className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded-md border ${
                              isTrusted
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {stage.trust_level}
                          </span>
                        </div>

                        <div className="text-[11px] text-slate-600 font-medium">
                          Agent <code>{stage.sender}</code> &rarr; <code>{stage.recipient}</code>
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
