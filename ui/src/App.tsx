import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { QueryPanel } from './components/QueryPanel';
import { IngestPanel } from './components/IngestPanel';
import { ApprovalsPanel } from './components/ApprovalsPanel';
import { AuditPanel } from './components/AuditPanel';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('query');
  const [vectorCount, setVectorCount] = useState<number>(0);
  const [auditCount, setAuditCount] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchHealth = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        setVectorCount(data.vector_store_count || 0);
        setAuditCount(data.audit_log_count || 0);
      }
    } catch (e) {
      console.error('Health fetch error', e);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="app-layout min-h-screen bg-slate-50 text-slate-900 font-sans">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingApprovalsCount={0}
      />

      <div className="main-content flex-1 ml-72 flex flex-col min-h-screen">
        <Header
          activeTab={activeTab}
          vectorCount={vectorCount}
          auditCount={auditCount}
          onRefresh={fetchHealth}
          isRefreshing={isRefreshing}
        />

        <main className="p-8 flex-1">
          {activeTab === 'query' && <QueryPanel />}
          {activeTab === 'ingest' && <IngestPanel />}
          {activeTab === 'approvals' && <ApprovalsPanel />}
          {activeTab === 'audit' && <AuditPanel />}
        </main>
      </div>
    </div>
  );
};

export default App;
