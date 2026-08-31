import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';

import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { TestModeBanner } from './components/layout/TestModeBanner';

import { LandingPage } from './pages/LandingPage';
import { Login } from './pages/Login';
import { CommandCenter } from './pages/CommandCenter';
import { RecoveryQueue } from './pages/RecoveryQueue';
import { CaseDetail } from './pages/CaseDetail';
import { AgentExecution } from './pages/AgentExecution';
import { AgentOperations } from './pages/AgentOperations';
import { HumanReview } from './pages/HumanReview';
import { CustomerActions } from './pages/CustomerActions';
import { Customers } from './pages/Customers';
import { CustomerDetail } from './pages/CustomerDetail';
import { Payments } from './pages/Payments';
import { Analytics } from './pages/Analytics';
import { AuditTrail } from './pages/AuditTrail';
import { Policies } from './pages/Policies';
import { Integrations } from './pages/Integrations';
import { TestMode } from './pages/TestMode';

const AppShell: React.FC = () => {
  const location = useLocation();
  const isPublicPage = location.pathname === '/' || location.pathname === '/login';

  if (isPublicPage) {
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#F9FAFB] text-slate-900 font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TestModeBanner />
        <Header />
        <main className="flex-1 overflow-y-auto pb-12">
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <CommandCenter />
                </ProtectedRoute>
              }
            />
            <Route
              path="/recovery"
              element={
                <ProtectedRoute>
                  <RecoveryQueue />
                </ProtectedRoute>
              }
            />
            <Route
              path="/recovery/:caseId"
              element={
                <ProtectedRoute>
                  <CaseDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/recovery/:caseId/run/:runId"
              element={
                <ProtectedRoute>
                  <AgentExecution />
                </ProtectedRoute>
              }
            />
            <Route
              path="/agent"
              element={
                <ProtectedRoute>
                  <AgentOperations />
                </ProtectedRoute>
              }
            />
            <Route
              path="/customer-actions"
              element={
                <ProtectedRoute>
                  <CustomerActions />
                </ProtectedRoute>
              }
            />
            <Route
              path="/human-review"
              element={
                <ProtectedRoute>
                  <HumanReview />
                </ProtectedRoute>
              }
            />
            <Route
              path="/customers"
              element={
                <ProtectedRoute>
                  <Customers />
                </ProtectedRoute>
              }
            />
            <Route
              path="/customers/:id"
              element={
                <ProtectedRoute>
                  <CustomerDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/payments"
              element={
                <ProtectedRoute>
                  <Payments />
                </ProtectedRoute>
              }
            />
            <Route
              path="/analytics"
              element={
                <ProtectedRoute>
                  <Analytics />
                </ProtectedRoute>
              }
            />
            <Route
              path="/audit"
              element={
                <ProtectedRoute>
                  <AuditTrail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/policies"
              element={
                <ProtectedRoute>
                  <Policies />
                </ProtectedRoute>
              }
            />
            <Route
              path="/integrations"
              element={
                <ProtectedRoute>
                  <Integrations />
                </ProtectedRoute>
              }
            />
            <Route
              path="/test-mode"
              element={
                <ProtectedRoute allowedRoles={['OPS', 'ADMIN']}>
                  <TestMode />
                </ProtectedRoute>
              }
            />
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
