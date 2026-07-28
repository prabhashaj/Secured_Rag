import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ConversationalChat } from './components/ConversationalChat';
import { FileUploadDrawer } from './components/FileUploadDrawer';
import { IngestPanel } from './components/IngestPanel';
import { ApprovalsPanel } from './components/ApprovalsPanel';
import { AuditPanel } from './components/AuditPanel';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('query');
  const [vectorCount, setVectorCount] = useState<number>(0);
  const [auditCount, setAuditCount] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);

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

  const handleOpenAuditTrace = (_traceId: string) => {
    setActiveTab('audit');
  };

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

        <main className="p-6 flex-1 flex flex-col">
          {activeTab === 'query' && (
            <ConversationalChat
              onOpenUpload={() => setIsUploadOpen(true)}
              onOpenAudit={handleOpenAuditTrace}
            />
          )}
          {activeTab === 'ingest' && <IngestPanel />}
          {activeTab === 'approvals' && <ApprovalsPanel />}
          {activeTab === 'audit' && <AuditPanel />}
        </main>
      </div>

      <FileUploadDrawer
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          fetchHealth();
        }}
      />
    </div>
  );
};

export default App;
