import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { TestModeBanner } from './components/layout/TestModeBanner';

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

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-[#F9FAFB] text-slate-900 font-sans">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TestModeBanner />
          <Header />
          <main className="flex-1 overflow-y-auto pb-12">
            <Routes>
              <Route path="/" element={<CommandCenter />} />
              <Route path="/recovery" element={<RecoveryQueue />} />
              <Route path="/recovery/:caseId" element={<CaseDetail />} />
              <Route path="/recovery/:caseId/run/:runId" element={<AgentExecution />} />
              <Route path="/agent" element={<AgentOperations />} />
              <Route path="/customer-actions" element={<CustomerActions />} />
              <Route path="/human-review" element={<HumanReview />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/customers/:id" element={<CustomerDetail />} />
              <Route path="/payments" element={<Payments />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/audit" element={<AuditTrail />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/integrations" element={<Integrations />} />
              <Route path="/test-mode" element={<TestMode />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
};

export default App;
