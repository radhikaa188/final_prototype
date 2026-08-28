const API_BASE = `${import.meta.env.VITE_API_URL}/api`;
export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  const contentType = res.headers.get('content-type') || '';

  if (!res.ok) {
    let errorDetail = `HTTP Error ${res.status}`;
    if (contentType.includes('application/json')) {
      const errorData = await res.json().catch(() => ({ detail: 'An error occurred' }));
      errorDetail = errorData.detail || errorDetail;
    }
    throw new Error(errorDetail);
  }

  if (contentType.includes('application/json')) {
    return res.json();
  }
  const text = await res.text();
  throw new Error(`Expected JSON response from API, received: ${text.substring(0, 60)}...`);
}

export const api = {
  // Dashboard
  getDashboardSummary: () => fetchApi<{
    revenue_at_risk: number;
    recoverable_revenue: number;
    revenue_recovered: number;
    recovery_rate: number;
    active_cases: number;
    total_cases: number;
  }>('/dashboard/summary'),

  getDashboardRevenue: () => fetchApi<Array<{ date: string; at_risk: number; recoverable: number; recovered: number }>>('/dashboard/revenue'),

  getDashboardFunnel: () => fetchApi<Array<{ stage: string; count: number; color: string }>>('/dashboard/funnel'),

  getDashboardActivity: () => fetchApi<Array<{ id: string; timestamp: string; case_id: string; actor_type: string; event_type: string; description: string }>>('/dashboard/activity'),

  // Recovery Queue & Detail
  getRecoveryCases: (params?: Record<string, string | number | boolean>) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') query.append(k, String(v));
      });
    }
    return fetchApi<{ total: number; cases: any[] }>(`/recovery-cases?${query.toString()}`);
  },

  getRecoveryCase: (caseId: string) => fetchApi<any>(`/recovery-cases/${caseId}`),

  approveCase: (caseId: string) => fetchApi<{ run_id: string; case_id: string; status: string }>(`/recovery-cases/${caseId}/approve`, { method: 'POST' }),

  executeCase: (caseId: string) => fetchApi<{ run_id: string; case_id: string; status: string }>(`/recovery-cases/${caseId}/execute`, { method: 'POST' }),

  rejectCase: (caseId: string) => fetchApi<{ case_id: string; status: string }>(`/recovery-cases/${caseId}/reject`, { method: 'POST' }),

  escalateCase: (caseId: string) => fetchApi<{ case_id: string; status: string }>(`/recovery-cases/${caseId}/escalate`, { method: 'POST' }),

  // Agent Operations
  getAgentRuns: () => fetchApi<{ total: number; runs: any[] }>('/agent/runs'),

  getAgentRun: (runId: string) => fetchApi<any>(`/agent/runs/${runId}`),

  // Customers
  getCustomers: () => fetchApi<{ total: number; customers: any[] }>('/customers'),

  getCustomer: (customerId: string) => fetchApi<any>(`/customers/${customerId}`),

  // Payments
  getPayments: () => fetchApi<{ total: number; payments: any[] }>('/payments'),

  getPayment: (paymentId: string) => fetchApi<any>(`/payments/${paymentId}`),

  // Analytics
  getAnalyticsSummary: () => fetchApi<any>('/analytics/summary'),
  getAnalyticsFailureReasons: () => fetchApi<any[]>('/analytics/failure-reasons'),
  getAnalyticsActions: () => fetchApi<any[]>('/analytics/actions'),
  getAnalyticsMLMetrics: () => fetchApi<any>('/analytics/ml-metrics'),

  // Audit
  getAuditEvents: (actorType?: string) => fetchApi<{ total: number; events: any[] }>(`/audit${actorType ? `?actor_type=${actorType}` : ''}`),

  // Policies
  getPolicy: () => fetchApi<any>('/policies'),
  updatePolicy: (policy: any) => fetchApi<any>('/policies', { method: 'PUT', body: JSON.stringify(policy) }),

  // Notifications
  getNotifications: () => fetchApi<{ total: number; notifications: any[] }>('/notifications'),

  // Test Mode
  generateTestPayment: (payload?: any) => fetchApi<any>('/test-mode/generate-payment', { method: 'POST', body: payload ? JSON.stringify(payload) : JSON.stringify({}) }),
};
