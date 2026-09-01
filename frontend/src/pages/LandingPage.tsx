import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import {
  ShieldCheck,
  Zap,
  Activity,
  Lock,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Cpu,
  Layers,
  ArrowUpRight,
  TrendingUp,
  AlertTriangle,
  Clock,
  UserCheck,
  Database,
  BarChart3,
  Scale,
  RefreshCw,
  GitBranch,
  Search,
  FileText,
  Check
} from 'lucide-react';

export const LandingPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Live database metrics & cases
  const [summary, setSummary] = useState<{
    revenue_at_risk: number;
    recoverable_revenue: number;
    revenue_recovered: number;
    recovery_rate: number;
    active_cases: number;
    total_cases: number;
  } | null>(null);

  const [activeTab, setActiveTab] = useState<'queue' | 'decision' | 'guardrails'>('queue');
  const [selectedCaseIdx, setSelectedCaseIdx] = useState<number>(0);

  const sampleCases = [
    {
      id: 'REC-9082',
      customer: 'Acme Software Corp',
      tier: 'Enterprise Tier',
      amount: 1250.00,
      reason: 'NETWORK_TIMEOUT',
      rootCause: 'TRANSIENT_FAILURE',
      prob: 0.92,
      ev: 1150.00,
      action: 'SMART_RETRY',
      status: 'PRIORITIZED',
      model: 'GradientBoosting (v3.0)',
      confidence: 0.94,
      guardrailChecks: [
        { name: '72h Recovery Window', passed: true, detail: 'Case age: 1.2h / 72h max' },
        { name: 'Max Retry Limit', passed: true, detail: 'Attempt 0 / 3 allowed' },
        { name: 'Customer Opt-Out', passed: true, detail: 'Account active (opted-in)' },
        { name: 'Exposure Ceiling', passed: true, detail: '$1,250.00 <= $10,000.00' }
      ]
    },
    {
      id: 'REC-9085',
      customer: 'Vertex Media Labs',
      tier: 'Growth Monthly',
      amount: 480.00,
      reason: 'CARD_EXPIRED',
      rootCause: 'CUSTOMER_ACTION',
      prob: 0.76,
      ev: 364.80,
      action: 'CUSTOMER_NUDGE',
      status: 'CUSTOMER_ACTION_REQUIRED',
      model: 'RandomForest (v3.0)',
      confidence: 0.89,
      guardrailChecks: [
        { name: '72h Recovery Window', passed: true, detail: 'Case age: 4.8h / 72h max' },
        { name: 'Max Retry Limit', passed: true, detail: 'Automated retry held pending update' },
        { name: 'Customer Opt-Out', passed: true, detail: 'SMS & Email link dispatched' },
        { name: 'Exposure Ceiling', passed: true, detail: '$480.00 <= $10,000.00' }
      ]
    },
    {
      id: 'REC-9089',
      customer: 'Aura Fintech Partners',
      tier: 'Scale Annual',
      amount: 3400.00,
      reason: 'FRAUD_SUSPECTED',
      rootCause: 'SUSPICIOUS_ACTIVITY',
      prob: 0.18,
      ev: 612.00,
      action: 'HUMAN_REVIEW',
      status: 'ESCALATED',
      model: 'RiskClassifier (v3.0)',
      confidence: 0.96,
      guardrailChecks: [
        { name: '72h Recovery Window', passed: true, detail: 'Case age: 0.4h / 72h max' },
        { name: 'Fraud Shield', passed: false, detail: 'Automated retries blocked by security policy' },
        { name: 'Human Review Routing', passed: true, detail: 'Routed directly to Operations queue' },
        { name: 'Exposure Ceiling', passed: true, detail: '$3,400.00 <= $10,000.00' }
      ]
    }
  ];

  useEffect(() => {
    // Fetch live backend metrics
    api.getDashboardSummary()
      .then((data) => {
        setSummary(data);
      })
      .catch(() => {
        setSummary({
          revenue_at_risk: 14850.0,
          recoverable_revenue: 10420.0,
          revenue_recovered: 8960.0,
          recovery_rate: 0.654,
          active_cases: 26,
          total_cases: 154
        });
      });
  }, []);

  const handleCta = () => {
    if (isAuthenticated) {
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  };

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  };

  const activeCase = sampleCases[selectedCaseIdx] || sampleCases[0];

  return (
    <div className="min-h-screen bg-[#070A11] text-slate-100 selection:bg-purple-600/30 selection:text-purple-200 font-sans antialiased">
      {/* Background Architectural Glow */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute top-[-15%] left-1/2 -translate-x-1/2 w-[1300px] h-[750px] bg-gradient-to-b from-purple-600/15 via-indigo-600/10 to-transparent blur-[160px] opacity-80" />
        <div className="absolute top-[45%] right-[-10%] w-[700px] h-[700px] bg-blue-600/10 blur-[150px]" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[800px] h-[800px] bg-purple-900/15 blur-[160px]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] [mask-image:radial-gradient(ellipse_70%_50%_at_50%_0%,#000_70%,transparent_100%)]" />
      </div>

      {/* 1. Top Editorial Header / Navbar */}
      <header className="fixed top-0 inset-x-0 h-20 bg-[#070A11]/85 backdrop-blur-xl border-b border-slate-800/80 z-50 transition-all">
        <div className="max-w-7xl mx-auto h-full px-6 md:px-10 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3.5 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 via-indigo-500 to-cyan-400 p-[1px] shadow-lg shadow-purple-500/20 group-hover:scale-105 transition-transform duration-200">
              <div className="w-full h-full bg-[#0A0E17] rounded-[11px] flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-purple-400" />
              </div>
            </div>
            <div>
              <span className="font-bold text-xl tracking-tight text-white flex items-center gap-1.5 font-mono">
                REVORA <span className="text-purple-400 font-sans font-semibold text-lg">AI</span>
              </span>
              <span className="text-[9px] uppercase tracking-widest text-slate-500 block font-mono -mt-1">
                Autonomous Revenue Recovery
              </span>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-mono tracking-wider uppercase text-slate-400">
            <a href="#how-it-works" className="hover:text-purple-300 transition-colors">01. Architecture</a>
            <a href="#expected-value" className="hover:text-purple-300 transition-colors">02. EV Prioritization</a>
            <a href="#intelligence" className="hover:text-purple-300 transition-colors">03. Intelligence</a>
            <a href="#guardrails" className="hover:text-purple-300 transition-colors">04. Guardrails</a>
            <a href="#ecosystem" className="hover:text-purple-300 transition-colors">05. Platform</a>
          </nav>

          <div className="flex items-center gap-4">
            <button
              onClick={handleCta}
              className="flex items-center gap-2.5 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs transition-all shadow-lg shadow-purple-600/25 hover:shadow-purple-600/40 cursor-pointer active:scale-95 border border-purple-400/30"
            >
              <span>{isAuthenticated ? 'Open Command Center' : 'Launch Platform'}</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section className="relative pt-36 pb-20 px-6 md:px-10 max-w-7xl mx-auto z-10 text-center">
        {/* Editorial Subhead Pill */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-purple-300 text-xs font-mono mb-8 shadow-inner backdrop-blur-md">
          <Sparkles size={13} className="text-cyan-400 animate-pulse" />
          <span className="text-slate-400">ML INFERENCE ENGINE</span>
          <span className="w-1 h-1 rounded-full bg-slate-700" />
          <span className="text-purple-300 font-semibold">POLICY CONTROLLED AUTOMATION</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.08] mb-6 max-w-5xl mx-auto">
          Intelligent Revenue Recovery <br />
          <span className="bg-gradient-to-r from-purple-300 via-indigo-200 to-cyan-300 bg-clip-text text-transparent">
            for Failed Payments.
          </span>
        </h1>

        {/* Hero Subtitle */}
        <p className="text-base sm:text-lg lg:text-xl text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed font-normal">
          Recover the <strong className="text-white font-semibold">right payment</strong>, at the <strong className="text-white font-semibold">right time</strong>, with the <strong className="text-white font-semibold">right action</strong>. Revora AI combines supervised ML root cause classification, expected-value prioritization, and deterministic safety guardrails to autonomously recapture lost revenue.
        </p>

        {/* Dual CTA Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <button
            onClick={handleCta}
            className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white font-bold text-sm transition-all shadow-xl shadow-purple-600/30 flex items-center justify-center gap-3 cursor-pointer group active:scale-98"
          >
            <span>EXPLORE RECOVERY PLATFORM</span>
            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
          </button>
          <button
            onClick={handleCta}
            className="w-full sm:w-auto px-7 py-4 rounded-xl bg-[#0B0F19] hover:bg-slate-800/80 border border-slate-700/80 text-slate-200 font-semibold text-sm transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg"
          >
            <Activity size={16} className="text-purple-400" />
            <span>Launch Live Demo Dashboard</span>
          </button>
        </div>

        {/* 3. Hero Product Centerpiece Console */}
        <div className="relative max-w-6xl mx-auto rounded-3xl p-1.5 bg-gradient-to-b from-slate-700/60 via-slate-800/40 to-slate-900/80 shadow-2xl shadow-purple-950/40 backdrop-blur-2xl text-left">
          <div className="bg-[#0A0E18] rounded-[22px] p-6 md:p-8 overflow-hidden border border-slate-800/90">
            {/* Top Workspace Chrome */}
            <div className="flex flex-wrap items-center justify-between pb-6 mb-6 border-b border-slate-800/80 gap-4">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-rose-500/80" />
                  <span className="w-3 h-3 rounded-full bg-amber-500/80" />
                  <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
                </div>
                <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-slate-900 border border-slate-800 text-xs font-mono text-slate-400">
                  <Activity size={12} className="text-indigo-400" />
                  <span>revora.app/operations-console</span>
                </div>
              </div>

              {/* Console Tabs */}
              <div className="flex items-center gap-1.5 bg-slate-900/90 p-1 rounded-xl border border-slate-800 text-xs font-mono">
                <button
                  onClick={() => setActiveTab('queue')}
                  className={`px-3 py-1 rounded-lg transition ${activeTab === 'queue' ? 'bg-purple-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                >
                  Recovery Queue
                </button>
                <button
                  onClick={() => setActiveTab('decision')}
                  className={`px-3 py-1 rounded-lg transition ${activeTab === 'decision' ? 'bg-purple-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                >
                  ML Decision Inspector
                </button>
                <button
                  onClick={() => setActiveTab('guardrails')}
                  className={`px-3 py-1 rounded-lg transition ${activeTab === 'guardrails' ? 'bg-purple-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'}`}
                >
                  Deterministic Guardrails
                </button>
              </div>

              <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/50 px-3 py-1 rounded-full">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Live Ingestion Active
              </div>
            </div>

            {/* Top Metric HUD Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <AlertTriangle size={12} className="text-amber-400" /> Revenue At Risk
                </div>
                <div className="text-2xl font-extrabold text-white font-mono">
                  {formatCurrency(summary?.revenue_at_risk)}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">{summary?.active_cases || 26} active cases under evaluation</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <TrendingUp size={12} className="text-cyan-400" /> Recoverable Pipeline
                </div>
                <div className="text-2xl font-extrabold text-cyan-400 font-mono">
                  {formatCurrency(summary?.recoverable_revenue)}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">EV Expected Target</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <CheckCircle2 size={12} className="text-emerald-400" /> Recaptured Revenue
                </div>
                <div className="text-2xl font-extrabold text-emerald-400 font-mono">
                  {formatCurrency(summary?.revenue_recovered)}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">Direct gateway settlement</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <Zap size={12} className="text-purple-400" /> Recovery Rate
                </div>
                <div className="text-2xl font-extrabold text-purple-300 font-mono">
                  {summary ? `${(summary.recovery_rate * 100).toFixed(1)}%` : '65.4%'}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">Autonomous ML efficiency</div>
              </div>
            </div>

            {/* Tab 1: Queue Preview with Interactive Selector */}
            {activeTab === 'queue' && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
                <div className="p-3 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400 font-mono">
                  <span className="font-bold text-slate-200">Autonomous Queue Execution Matrix</span>
                  <span>Click case to inspect telemetry</span>
                </div>
                <div className="divide-y divide-slate-800/60 text-xs">
                  {sampleCases.map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => setSelectedCaseIdx(idx)}
                      className={`p-4 flex flex-wrap md:flex-nowrap items-center justify-between gap-3 cursor-pointer transition-colors ${
                        selectedCaseIdx === idx ? 'bg-purple-950/30 border-l-4 border-purple-500' : 'hover:bg-slate-800/30'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-[200px]">
                        <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 text-purple-400 flex items-center justify-center font-mono font-bold text-xs">
                          0{idx + 1}
                        </div>
                        <div>
                          <div className="font-bold text-white text-xs">{item.customer}</div>
                          <div className="text-[10px] font-mono text-slate-400">{item.id} · {item.tier}</div>
                        </div>
                      </div>

                      <div className="flex items-center gap-6 font-mono text-xs">
                        <div>
                          <span className="text-[10px] text-slate-500 block">At Risk</span>
                          <span className="font-bold text-slate-200">${item.amount.toFixed(2)}</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">P(Recovery)</span>
                          <span className="font-bold text-cyan-400">{(item.prob * 100).toFixed(0)}%</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Expected Value</span>
                          <span className="font-bold text-purple-300">${item.ev.toFixed(2)}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded-md text-[10px] font-mono font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-800/50">
                          {item.action}
                        </span>
                        <span className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold ${
                          item.status === 'RECOVERED'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60'
                            : item.status === 'CUSTOMER_ACTION_REQUIRED'
                            ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                            : item.status === 'ESCALATED'
                            ? 'bg-purple-950 text-purple-300 border border-purple-800/60'
                            : 'bg-slate-800 text-slate-200 border border-slate-700'
                        }`}>
                          {item.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 2: ML Decision Inspector */}
            {activeTab === 'decision' && (
              <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/50 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <span className="text-xs font-mono text-purple-400 uppercase font-bold">Case Telemetry: {activeCase.id}</span>
                    <h4 className="text-sm font-bold text-white mt-0.5">{activeCase.customer} — Decline Analysis</h4>
                  </div>
                  <span className="px-3 py-1 rounded-md bg-purple-950 text-purple-300 font-mono text-xs font-bold border border-purple-800">
                    Model: {activeCase.model}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                  <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">DIAGNOSED ROOT CAUSE</span>
                    <span className="font-bold text-white text-sm">{activeCase.rootCause}</span>
                    <span className="text-[10px] text-slate-400 block mt-1">Decline code: {activeCase.reason}</span>
                  </div>
                  <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">RECOVERY PROBABILITY P(R)</span>
                    <span className="font-bold text-cyan-400 text-sm">{(activeCase.prob * 100).toFixed(1)}%</span>
                    <span className="text-[10px] text-slate-400 block mt-1">Confidence score: {(activeCase.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-slate-500 block text-[10px]">SELECTED STRATEGY</span>
                    <span className="font-bold text-purple-300 text-sm">{activeCase.action}</span>
                    <span className="text-[10px] text-slate-400 block mt-1">Status: {activeCase.status}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Guardrails Verification */}
            {activeTab === 'guardrails' && (
              <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/50 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-xs font-mono text-emerald-400 uppercase font-bold">Deterministic Policy Verification — {activeCase.id}</span>
                  <span className="text-xs font-mono text-slate-400">Pre-execution safety gate</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {activeCase.guardrailChecks.map((chk, cIdx) => (
                    <div key={cIdx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${chk.passed ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'}`}>
                        {chk.passed ? <Check size={12} /> : <AlertTriangle size={12} />}
                      </div>
                      <div>
                        <div className="font-bold text-white">{chk.name}</div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">{chk.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 4. Editorial Problem Section: Heterogeneity */}
      <section className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
          <div className="max-w-2xl">
            <div className="text-xs font-mono font-bold uppercase tracking-widest text-purple-400 mb-3">01 / DECLINE TAXONOMY</div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
              Failed payments are not all the same.
            </h2>
          </div>
          <p className="text-slate-400 text-sm max-w-md leading-relaxed">
            Blind retry scripts cause expensive gateway penalties, customer friction, and silent churn. Revora AI classifies every transaction context to execute the only appropriate recovery action.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="p-8 rounded-2xl bg-[#0B0F19] border border-slate-800/90 hover:border-indigo-500/50 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Zap size={22} />
              </div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400 block mb-2">Category 01</span>
              <h3 className="text-xl font-bold text-white mb-3">Transient & Systemic Glitches</h3>
              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Network dropouts, gateway timeouts, and bank connection glitches are resolved autonomously via scheduled adaptive backoff retries.
              </p>
            </div>
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400">P(Recovery): 85%–95%</span>
              <span className="px-2.5 py-1 rounded bg-indigo-950/80 border border-indigo-800 text-indigo-300 font-mono text-xs font-bold">
                ACT NOW (RETRY)
              </span>
            </div>
          </div>

          {/* Card 2 */}
          <div className="p-8 rounded-2xl bg-[#0B0F19] border border-slate-800/90 hover:border-amber-500/50 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Clock size={22} />
              </div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-amber-400 block mb-2">Category 02</span>
              <h3 className="text-xl font-bold text-white mb-3">Customer-Dependent Declines</h3>
              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Expired cards and insufficient funds will fail repeatedly on immediate retries. Revora AI dispatches self-service card update portals and holds retry execution until the customer acts.
              </p>
            </div>
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400">P(Recovery): 60%–80%</span>
              <span className="px-2.5 py-1 rounded bg-amber-950/80 border border-amber-800 text-amber-300 font-mono text-xs font-bold">
                WAIT FOR CUSTOMER
              </span>
            </div>
          </div>

          {/* Card 3 */}
          <div className="p-8 rounded-2xl bg-[#0B0F19] border border-slate-800/90 hover:border-purple-500/50 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <ShieldCheck size={22} />
              </div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-purple-400 block mb-2">Category 03</span>
              <h3 className="text-xl font-bold text-white mb-3">High-Risk & Security Flags</h3>
              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Suspicious activities, card velocity triggers, and stolen card signals are immediately hard-blocked from automated retries and routed to Human Review.
              </p>
            </div>
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400">P(Recovery): Guarded</span>
              <span className="px-2.5 py-1 rounded bg-purple-950/80 border border-purple-800 text-purple-300 font-mono text-xs font-bold">
                ESCALATE TO REVIEW
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Core Architectural Workflow */}
      <section id="how-it-works" className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="text-xs font-mono font-bold uppercase tracking-widest text-cyan-400 mb-3">02 / CORE ARCHITECTURE</div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-4">
            From Failed Payment to Recovered Revenue
          </h2>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Every transaction decline flows through an 8-stage deterministic state machine with verifiable policy boundaries.
          </p>
        </div>

        {/* 8-Stage Sequential Flow */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-12">
          {[
            { step: '01', title: 'DETECT', sub: 'HMAC Webhooks' },
            { step: '02', title: 'DIAGNOSE', sub: 'Root Cause ML' },
            { step: '03', title: 'INFERENCE', sub: 'P(Recovery)' },
            { step: '04', title: 'PRIORITIZE', sub: 'EV Score Ranking' },
            { step: '05', title: 'DECIDE', sub: 'Action Selector' },
            { step: '06', title: 'GUARDRAILS', sub: 'Policy Boundary' },
            { step: '07', title: 'EXECUTE', sub: 'Smart Dispatch' },
            { step: '08', title: 'RE-EVALUATE', sub: 'Closed Loop' }
          ].map((s, idx) => (
            <div key={idx} className="p-4 rounded-xl bg-[#0A0E17] border border-slate-800 text-center hover:border-purple-500/60 transition-all">
              <div className="text-[10px] font-mono text-purple-400 font-bold mb-1">STAGE {s.step}</div>
              <div className="text-xs font-bold text-white mb-1">{s.title}</div>
              <div className="text-[10px] text-slate-500 font-mono">{s.sub}</div>
            </div>
          ))}
        </div>

        {/* Branching Decision Tree Showcase */}
        <div className="p-8 rounded-3xl bg-[#090D17] border border-slate-800 shadow-xl text-center">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-widest mb-6">Autonomous Branching Topology</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-left">
            <div className="p-5 rounded-2xl bg-indigo-950/30 border border-indigo-800/60">
              <div className="flex items-center gap-2 text-indigo-300 font-mono text-xs font-bold mb-2">
                <Zap size={14} /> 1. SMART RETRY
              </div>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                Calculates optimal gateway resubmission window with adaptive backoff.
              </p>
              <div className="text-[10px] font-mono text-indigo-400">Target: Autonomous Recovery</div>
            </div>

            <div className="p-5 rounded-2xl bg-amber-950/30 border border-amber-800/60">
              <div className="flex items-center gap-2 text-amber-300 font-mono text-xs font-bold mb-2">
                <Clock size={14} /> 2. CUSTOMER ACTION
              </div>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                Dispatches secure self-service billing link; waits for customer resolution.
              </p>
              <div className="text-[10px] font-mono text-amber-400">Target: Customer Resolution</div>
            </div>

            <div className="p-5 rounded-2xl bg-purple-950/30 border border-purple-800/60">
              <div className="flex items-center gap-2 text-purple-300 font-mono text-xs font-bold mb-2">
                <UserCheck size={14} /> 3. HUMAN REVIEW
              </div>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                High-exposure & fraud flags escalate to operations with full ML explainability.
              </p>
              <div className="text-[10px] font-mono text-purple-400">Target: Operator Approval</div>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs font-bold mb-2">
                <Lock size={14} /> 4. TERMINAL STOP
              </div>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                Deterministic halt triggered when retry limits or customer opt-outs are met.
              </p>
              <div className="text-[10px] font-mono text-slate-500">Target: Guardrail Boundary</div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Expected Value Prioritization Section */}
      <section id="expected-value" className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="text-xs font-mono font-bold uppercase tracking-widest text-purple-400 mb-3">03 / MATHEMATICAL ADVANTAGE</div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-6">
              Prioritize by Recovery Opportunity, <br />
              <span className="text-cyan-300 font-serif italic font-normal">not just Dollar Amount.</span>
            </h2>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed mb-6">
              Conventional dunning tools blindly sort by invoice size, wasting finite retry attempts on dead cards. Revora AI prioritizes cases by <strong className="text-white">Expected Recovery Value (EV)</strong> to maximize total revenue recovered per operational unit.
            </p>

            {/* Formula Block */}
            <div className="p-6 rounded-2xl bg-[#0A0E18] border border-slate-800 font-mono text-sm space-y-3 mb-6">
              <div className="text-slate-400 text-xs uppercase tracking-wider">The Revora Expected Value Formula:</div>
              <div className="text-lg font-bold text-purple-300">
                Expected Recovery = Revenue At Risk × P(Recovery)
              </div>
              <div className="text-xs text-slate-400">
                P(Recovery) is calibrated using Gradient Boosted ML models conditioned on customer tenure, LTV, historical success rate, and decline telemetry.
              </div>
            </div>
          </div>

          {/* Numerical Proof Comparison */}
          <div className="space-y-4">
            <div className="p-6 rounded-2xl bg-gradient-to-r from-emerald-950/30 via-[#0B0F19] to-[#0B0F19] border border-emerald-800/60 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-emerald-400 uppercase">Case A: High Probability Transient</span>
                <span className="px-2.5 py-0.5 rounded bg-emerald-900/80 text-emerald-300 text-[10px] font-mono font-bold">Priority Rank #1</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-xs font-mono mb-2">
                <div><span className="text-slate-500 block text-[10px]">At Risk</span>$850.00</div>
                <div><span className="text-slate-500 block text-[10px]">P(Recovery)</span>92%</div>
                <div><span className="text-slate-500 block text-[10px]">Expected Recovery</span><span className="text-emerald-400 font-bold">$782.00</span></div>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">Diagnosis: NETWORK_TIMEOUT · Automated Smart Retry</div>
            </div>

            <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-slate-400 uppercase">Case B: High Amount, Low Probability</span>
                <span className="px-2.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono font-bold">Priority Rank #4</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-xs font-mono mb-2">
                <div><span className="text-slate-500 block text-[10px]">At Risk</span>$2,400.00</div>
                <div><span className="text-slate-500 block text-[10px]">P(Recovery)</span>18%</div>
                <div><span className="text-slate-500 block text-[10px]">Expected Recovery</span><span className="text-slate-300 font-bold">$432.00</span></div>
              </div>
              <div className="text-[11px] text-slate-400 font-mono">Diagnosis: FRAUD_SUSPECTED · Stolen card flag · Human Review Required</div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Deterministic Guardrails Section */}
      <section id="guardrails" className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="text-xs font-mono font-bold uppercase tracking-widest text-indigo-400 mb-3">04 / POLICY SAFETY ENGINE</div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-4">
            Intelligence With Boundaries
          </h2>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            AI recommendations are never allowed to execute unchecked. Deterministic policy guardrails enforce immutable enterprise boundaries before every gateway call.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <Scale className="w-5 h-5 text-purple-400" />
              <h3 className="text-base font-bold text-white">72-Hour Recovery SLA</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Enforces a strict 72-hour window from original decline time. Attempts beyond this SLA are halted to prevent stale authorizations.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <RefreshCw className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-white">Max 3 Retry Ceiling</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Strict limit of 3 automated retries per case. Prevents excessive gateway fees and maintains compliance standing with acquirers.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <UserCheck className="w-5 h-5 text-emerald-400" />
              <h3 className="text-base font-bold text-white">Customer Opt-Out Respect</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Customers opted out of automated communications are safeguarded from nudges with zero external communication leaks.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <Lock className="w-5 h-5 text-amber-400" />
              <h3 className="text-base font-bold text-white">$10,000 Auto-Retry Cap</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              High-exposure transactions exceeding configurable policy thresholds require explicit human review before execution.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <GitBranch className="w-5 h-5 text-indigo-400" />
              <h3 className="text-base font-bold text-white">HMAC Idempotency Shield</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Cryptographic HMAC signature verification and database-backed idempotency prevent duplicate retry charges across rapid webhook retries.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-3 mb-3">
              <Database className="w-5 h-5 text-rose-400" />
              <h3 className="text-base font-bold text-white">Immutable Audit Ledger</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every ML diagnosis, guardrail evaluation, and operator decision is recorded in an immutable chronological database audit trail.
            </p>
          </div>
        </div>
      </section>

      {/* 8. Closed-Loop Re-evaluation Section */}
      <section className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="p-8 sm:p-12 rounded-3xl bg-gradient-to-r from-purple-950/25 via-[#0A0E17] to-[#0A0E17] border border-purple-900/40 shadow-2xl">
          <div className="max-w-3xl">
            <div className="text-xs font-mono font-bold uppercase tracking-widest text-purple-400 mb-3">CLOSED-LOOP FEEDBACK</div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-4">
              Recovery Doesn&apos;t End at the First Failure.
            </h2>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed mb-8">
              Revora AI observes the outcome of every recovery attempt. When a gateway retry fails with a secondary reason, the case automatically transitions to <span className="font-mono text-purple-300 font-semibold">RE_EVALUATING</span> with adaptive backoff timing, running fresh ML inference to route to the correct next step.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300">
                1. Observe Gateway Result
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300">
                2. Calculate Adaptive Backoff
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300">
                3. Re-evaluate Context & Policy
              </div>
              <div className="p-3 rounded-xl bg-purple-900/50 border border-purple-700/60 text-purple-300 font-bold">
                4. Recapture Revenue
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 9. Product Ecosystem Modules */}
      <section id="ecosystem" className="py-28 px-6 md:px-10 max-w-7xl mx-auto border-t border-slate-800/60 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="text-xs font-mono font-bold uppercase tracking-widest text-cyan-400 mb-3">05 / PLATFORM MODULES</div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-4">
            Unified Revenue Operations Suite
          </h2>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Everything finance, risk, and operations teams require to oversee, simulate, and govern autonomous payment recovery.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { title: 'Command Center', icon: Activity, desc: 'Real-time recovery KPIs, revenue funnel, and live telemetry.' },
            { title: 'Recovery Queue', icon: Layers, desc: 'Prioritized operational list with active vs recovered separation.' },
            { title: 'Agent Operations', icon: Cpu, desc: 'Detailed 8-step ML trace with explainability and probability scores.' },
            { title: 'Human Review', icon: UserCheck, desc: 'Operator queue for high-risk, fraud, and high-exposure approvals.' },
            { title: 'Customer Actions', icon: Clock, desc: 'Track pending card updates, fund additions, and 3DS validations.' },
            { title: 'Live Analytics', icon: BarChart3, desc: 'Decline reason distribution, recovery rates, and cohort metrics.' },
            { title: 'Audit Trail', icon: FileText, desc: 'Immutable chronological ledger of all decisions and human actions.' },
            { title: 'Global Search', icon: Search, desc: 'Sub-second search across Payment, Customer, and Recovery IDs.' }
          ].map((mod, idx) => {
            const Icon = mod.icon;
            return (
              <div key={idx} className="p-5 rounded-2xl bg-[#0B0F19] border border-slate-800 hover:border-slate-700 transition-colors">
                <div className="w-9 h-9 rounded-lg bg-slate-800 text-purple-400 flex items-center justify-center mb-3">
                  <Icon size={18} />
                </div>
                <h4 className="text-sm font-bold text-white mb-1">{mod.title}</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">{mod.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* 10. Final Call to Action Section */}
      <section className="py-28 px-6 md:px-10 max-w-5xl mx-auto text-center border-t border-slate-800/60 relative z-10">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-purple-600 to-cyan-500 p-[1px] shadow-xl shadow-purple-500/20 mx-auto mb-8">
          <div className="w-full h-full bg-[#0A0E18] rounded-[15px] flex items-center justify-center text-purple-400">
            <ShieldCheck size={28} />
          </div>
        </div>

        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight mb-6">
          Turn Failed Payments Into <br />
          <span className="bg-gradient-to-r from-purple-400 via-indigo-300 to-cyan-300 bg-clip-text text-transparent">
            Recoverable Revenue.
          </span>
        </h2>

        <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          See how Revora AI detects, prioritizes, and recovers payment opportunities through an intelligent closed-loop workflow.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button
            onClick={handleCta}
            className="w-full sm:w-auto px-9 py-4 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white font-bold text-sm shadow-xl shadow-purple-600/30 transition-all cursor-pointer flex items-center justify-center gap-2 group active:scale-95"
          >
            <span>{isAuthenticated ? 'OPEN COMMAND CENTER' : 'EXPLORE REVORA AI'}</span>
            <ArrowUpRight size={16} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </button>
        </div>
      </section>

      {/* 11. Editorial Footer */}
      <footer className="border-t border-slate-800/80 bg-[#05070D] relative z-10 py-12 px-6 text-center">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6 text-xs text-slate-500 font-mono">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-purple-400" />
            <span className="font-bold text-slate-300">REVORA AI</span>
            <span>— Autonomous Revenue Recovery</span>
          </div>

          <div className="flex items-center gap-6">
            <a href="#how-it-works" className="hover:text-slate-300 transition-colors">Architecture</a>
            <a href="#expected-value" className="hover:text-slate-300 transition-colors">Prioritization</a>
            <a href="#guardrails" className="hover:text-slate-300 transition-colors">Guardrails</a>
            <button onClick={handleCta} className="hover:text-purple-400 transition-colors font-semibold cursor-pointer">
              Dashboard
            </button>
          </div>

          <div>
            © {new Date().getFullYear()} Revora AI. Enterprise System.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
