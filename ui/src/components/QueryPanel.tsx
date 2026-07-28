import React, { useState } from 'react';
import { Send, FileText, CheckCircle2, AlertTriangle, Lock } from 'lucide-react';
import type { QueryResponse, PipelineState } from '../types';

export const QueryPanel: React.FC = () => {
  const [query, setQuery] = useState('');
  const [userId, setUserId] = useState('lawyer_alice');
  const [permittedMatters, setPermittedMatters] = useState('matter-001, matter-002');
  const [isLoading, setIsLoading] = useState(false);
  const [currentStage, setCurrentStage] = useState<PipelineState | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [traceData, setTraceData] = useState<any>(null);

  const stages: { id: PipelineState; label: string }[] = [
    { id: 'received', label: 'Received' },
    { id: 'retrieving', label: 'ACL Retrieval' },
    { id: 'classifying', label: 'Injection Scan' },
    { id: 'analyzing', label: 'Analysis Agent' },
    { id: 'validating', label: 'Validator Gate' },
    { id: 'complete', label: 'Complete' },
  ];

  const handleRunQuery = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setResult(null);
    setTraceData(null);
    setCurrentStage('retrieving');

    try {
      const mattersList = permittedMatters
        .split(',')
        .map(m => m.trim())
        .filter(Boolean);

      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          user_id: userId.trim() || 'default_user',
          permitted_matters: mattersList,
        }),
      });

      const data: QueryResponse = await res.json();
      if (!res.ok) throw new Error((data as any).detail || 'Query execution failed');

      setResult(data);
      setCurrentStage(data.status);

      try {
        const traceRes = await fetch(`/audit/trace/${data.trace_id}`);
        if (traceRes.ok) {
          const tData = await traceRes.json();
          setTraceData(tData);
        }
      } catch (e) {
        console.warn('Trace fetch error', e);
      }

    } catch (err: any) {
      setResult({
        trace_id: 'error',
        status: 'failed',
        error: err.message || 'Pipeline execution failed',
      });
      setCurrentStage('failed');
    } finally {
      setIsLoading(false);
    }
  };

  const getStageStatus = (stageId: PipelineState) => {
    if (!currentStage) return 'pending';
    if (currentStage === 'failed') return stageId === currentStage ? 'failed' : 'pending';
    
    const stageOrder: PipelineState[] = ['received', 'retrieving', 'classifying', 'analyzing', 'validating', 'complete'];
    const currentIndex = stageOrder.indexOf(currentStage);
    const stageIndex = stageOrder.indexOf(stageId);

    if (stageIndex < currentIndex) return 'completed';
    if (stageIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Query Input Card */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-7 shadow-soft-md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
            <Lock className="w-4 h-4 text-brand-600" />
            <span>Secure Query Execution</span>
          </div>
          <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg">
            ACL Filtering Active
          </span>
        </div>

        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter legal question or contract clause analysis request (e.g. What are the indemnification terms in Section 4?)..."
          className="w-full bg-slate-50 border border-slate-200 focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10 rounded-xl p-4 text-base text-slate-900 placeholder-slate-400 outline-none transition-all resize-none min-h-[120px] leading-relaxed"
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
              User Identity
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/10 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
              Permitted Matter Scopes (ACL Filter)
            </label>
            <input
              type="text"
              value={permittedMatters}
              onChange={(e) => setPermittedMatters(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/10 rounded-xl p-3 text-sm text-slate-900 font-medium outline-none"
            />
          </div>
        </div>

        <div className="flex justify-end mt-6 pt-4 border-t border-slate-100">
          <button
            onClick={handleRunQuery}
            disabled={isLoading || !query.trim()}
            className="flex items-center gap-2.5 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm rounded-xl transition-all shadow-md shadow-brand-500/20 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>Executing Pipeline...</span>
              </>
            ) : (
              <>
                <span>Run Analysis Pipeline</span>
                <Send className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Steps Tracker */}
      {currentStage && (
        <div className="bg-white border border-slate-200/80 rounded-2xl p-5 flex items-center justify-between shadow-soft-sm overflow-x-auto">
          {stages.map((stage, idx) => {
            const status = getStageStatus(stage.id);
            return (
              <React.Fragment key={stage.id}>
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                      status === 'completed'
                        ? 'bg-emerald-500 text-white shadow-sm'
                        : status === 'active'
                        ? 'bg-brand-600 text-white shadow-md shadow-brand-500/30 animate-pulse'
                        : status === 'failed'
                        ? 'bg-rose-500 text-white'
                        : 'bg-slate-100 border border-slate-200 text-slate-400'
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <span
                    className={`text-xs font-semibold ${
                      status === 'completed'
                        ? 'text-emerald-700'
                        : status === 'active'
                        ? 'text-brand-600 font-bold'
                        : status === 'failed'
                        ? 'text-rose-600'
                        : 'text-slate-400'
                    }`}
                  >
                    {stage.label}
                  </span>
                </div>
                {idx < stages.length - 1 && (
                  <div className={`h-[2px] w-8 flex-shrink-0 ${status === 'completed' ? 'bg-emerald-400' : 'bg-slate-200'}`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {/* Result Display Card */}
      {result && (
        <div className={`bg-white border rounded-2xl overflow-hidden shadow-soft-lg ${
          result.status === 'failed' ? 'border-rose-300' : 'border-slate-200'
        }`}>
          <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <FileText className="w-4 h-4 text-brand-600" />
              <span>{result.status === 'failed' ? 'Pipeline Halted' : 'Grounded Legal Analysis'}</span>
            </div>
            <span className="text-xs font-mono text-slate-500 font-medium">
              Trace: {result.trace_id}
            </span>
          </div>

          <div className="p-7 space-y-6">
            {result.error ? (
              <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm font-medium">
                {result.error}
              </div>
            ) : (
              <div className="text-base text-slate-800 leading-relaxed whitespace-pre-wrap font-normal">
                {result.answer}
              </div>
            )}

            {/* Claims & Citations */}
            {result.claims && result.claims.length > 0 && (
              <div className="pt-5 border-t border-slate-100 space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Validated Claims & Chunk Provenance
                </div>
                <div className="space-y-2.5">
                  {result.claims.map((claim, idx) => (
                    <div key={idx} className="p-4 bg-slate-50 border border-slate-200/70 rounded-xl">
                      <p className="text-sm text-slate-900 mb-2.5 font-medium leading-relaxed">"{claim.text}"</p>
                      <div className="flex flex-wrap gap-2">
                        {claim.supporting_chunk_ids.map(cid => (
                          <span key={cid} className="px-2.5 py-1 text-xs font-mono font-semibold bg-white text-brand-700 border border-brand-200 rounded-lg shadow-soft-sm">
                            {cid}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Injection Scan Badges */}
            {traceData && traceData.stages && (
              <div className="pt-5 border-t border-slate-100 space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Isolated Context Classifier Verdicts
                </div>
                <div className="flex flex-wrap gap-2">
                  {traceData.stages
                    .filter((s: any) => s.message_type === 'injection_scan_result')
                    .map((s: any, idx: number) => {
                      const p = s.payload_summary || {};
                      const verdict = (p.verdict || 'clean').toLowerCase();
                      const isClean = verdict === 'clean';
                      return (
                        <span
                          key={idx}
                          className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg border flex items-center gap-1.5 ${
                            isClean
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {isClean ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />}
                          {verdict.toUpperCase()}: {p.chunk_id}
                        </span>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
