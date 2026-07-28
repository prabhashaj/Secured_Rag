import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ConversationalChat } from './components/ConversationalChat';
import { DocumentsPanel } from './components/DocumentsPanel';
import { FileUploadDrawer } from './components/FileUploadDrawer';
import { IngestPanel } from './components/IngestPanel';
import { ApprovalsPanel } from './components/ApprovalsPanel';
import { AuditPanel } from './components/AuditPanel';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AuthModal } from './components/AuthModal';
import { UserProfileDrawer } from './components/UserProfileDrawer';

const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('query');
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);

  const { user } = useAuth();

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

      <div className="main-content flex-1 ml-64 flex flex-col min-h-screen">
        <Header
          activeTab={activeTab}
          onOpenAuth={() => setIsAuthOpen(true)}
          onOpenProfile={() => setIsProfileOpen(true)}
        />

        <main className="p-6 flex-1 flex flex-col">
          {activeTab === 'query' && (
            <ConversationalChat
              onOpenUpload={() => setIsUploadOpen(true)}
              onOpenAudit={handleOpenAuditTrace}
            />
          )}
          {activeTab === 'documents' && (
            <DocumentsPanel
              onOpenUpload={() => setIsUploadOpen(true)}
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
        onSuccess={() => {}}
      />

      <AuthModal
        isOpen={isAuthOpen || !user}
        onClose={() => setIsAuthOpen(false)}
      />

      <UserProfileDrawer
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
