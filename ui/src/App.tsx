import React, { useState, useEffect } from 'react';
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
import { apiFetch } from './lib/api';
import type { ChatSession } from './types';

const AppContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('query');
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [matterId, setMatterId] = useState<string>('Matter_101');
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);

  const { user } = useAuth();

  useEffect(() => {
    const handleExpired = () => {
      setIsAuthOpen(true);
    };
    window.addEventListener('auth_session_expired', handleExpired);
    return () => window.removeEventListener('auth_session_expired', handleExpired);
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await apiFetch('/sessions');
      if (res.ok) {
        const data: ChatSession[] = await res.json();
        setSessions(data);
        if (data.length > 0 && !activeSessionId) {
          setActiveSessionId(data[0].session_id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch chat sessions', e);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [user]);

  const handleCreateSession = async () => {
    try {
      const res = await apiFetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `Legal Query ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
          user_id: user?.user_id || 'default_user',
          active_matter_id: matterId,
        }),
      });
      if (res.ok) {
        const newSession: ChatSession = await res.json();
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(newSession.session_id);
        setActiveTab('query');
      }
    } catch (e) {
      console.error('Failed to create session', e);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        const filtered = sessions.filter((s) => s.session_id !== sessionId);
        setSessions(filtered);
        if (activeSessionId === sessionId) {
          setActiveSessionId(filtered.length > 0 ? filtered[0].session_id : null);
        }
      }
    } catch (e) {
      console.error('Failed to delete session', e);
    }
  };

  const handleOpenAuditTrace = (_traceId: string) => {
    setActiveTab('audit');
  };

  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  const fetchPendingCount = async () => {
    try {
      const res = await apiFetch('/approvals/api/pending');
      if (res.ok) {
        const data = await res.json();
        setPendingApprovalsCount((data || []).length);
      }
    } catch (e) {
      console.error('Failed to fetch pending approvals count', e);
    }
  };

  useEffect(() => {
    fetchPendingCount();
    const interval = setInterval(fetchPendingCount, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans text-slate-800">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        sessions={sessions}
        activeSessionId={activeSessionId}
        setActiveSessionId={setActiveSessionId}
        onCreateSession={handleCreateSession}
        onDeleteSession={handleDeleteSession}
        matterId={matterId}
        setMatterId={setMatterId}
        pendingApprovalsCount={pendingApprovalsCount}
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
              activeSessionId={activeSessionId}
              sessions={sessions}
              matterId={matterId}
              onOpenUpload={() => setIsUploadOpen(true)}
              onOpenAudit={handleOpenAuditTrace}
              onSessionCreated={(newSess) => {
                setSessions((prev) => [newSess, ...prev]);
                setActiveSessionId(newSess.session_id);
              }}
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
