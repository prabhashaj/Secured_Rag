import React, { useState, useEffect } from 'react';
import { History, Layers } from 'lucide-react';
import type { TraceSummary } from '../types';

export const AuditPanel: React.FC = () => {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<any>(null);

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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Trace Index List */}
        <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-soft-md">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 mb-4 pb-3 border-b border-slate-100">
            <History className="w-4 h-4 text-brand-600" />
            <span>Audit Trace Log</span>
          </div>

          {traces.length === 0 ? (
            <div className="text-xs text-slate-400 py-8 text-center font-medium">
              No audit traces logged.
            </div>
          ) : (
            <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
              {traces.map(t => {
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
                    <div className="flex items-center justify-between font-mono text-xs mb-1.5 font-bold">
                      <span className="text-brand-700">{t.trace_id.substring(0, 12)}...</span>
                      <span className="text-slate-400 font-medium">{t.message_count} msgs</span>
                    </div>
                    <div className="text-[11px] text-slate-500 font-medium">
                      {new Date(t.started_at).toLocaleTimeString()}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Trace Inspector */}
        <div className="md:col-span-2 bg-white border border-slate-200/80 rounded-2xl p-7 shadow-soft-md">
          <div className="flex items-center justify-between mb-6 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              <Layers className="w-4 h-4 text-brand-600" />
              <span>Trace Graph Trajectory</span>
            </div>
            {selectedTraceId && (
              <span className="text-xs font-mono text-slate-500 font-medium">
                Trace ID: {selectedTraceId}
              </span>
            )}
          </div>

          {!selectedTraceId ? (
            <div className="py-20 text-center text-sm text-slate-400 font-medium">
              Select a trace from the log index on the left to reconstruct its full inter-agent message trajectory.
            </div>
          ) : !traceDetail ? (
            <div className="py-20 text-center text-sm text-slate-500 font-medium">
              Loading trace trajectory graph...
            </div>
          ) : (
            <div className="space-y-5 relative pl-5 border-l-2 border-slate-200">
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
                    <div className="bg-slate-50/80 border border-slate-200/80 rounded-xl p-4.5 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-slate-900">
                          {stage.message_type}
                        </span>
                        <span
                          className={`px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase rounded-lg border ${
                            isTrusted
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {stage.trust_level}
                        </span>
                      </div>

                      <div className="text-xs text-slate-600">
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
          )}
        </div>
      </div>
    </div>
  );
};
