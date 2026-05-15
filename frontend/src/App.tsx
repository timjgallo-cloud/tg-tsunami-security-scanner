import React, { useState, useEffect } from 'react';
import { Shield, Search, Play, CheckCircle2, AlertTriangle, Clock, RefreshCw, ExternalLink, ChevronRight } from 'lucide-react';

interface Vulnerability {
  cveId?: string;
  title?: string;
  description?: string;
  rating?: string;
  gtiRiskScore?: number;
}

interface ScanResult {
  scanStatus: string;
  scanFindings?: {
    vulnerability: Vulnerability;
  }[];
}

export default function App() {
  const [target, setTarget] = useState('');
  const [executionId, setExecutionId] = useState('');
  const [status, setStatus] = useState<'idle' | 'scanning' | 'completed' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [results, setResults] = useState<ScanResult | null>(null);
  const [isEnriched, setIsEnriched] = useState(false);

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target) return;

    setStatus('scanning');
    setErrorMessage('');
    setResults(null);

    try {
      const res = await fetch('/api/v1/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to start scan');
      }

      const data = await res.json();
      setExecutionId(data.execution_id);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message || 'An unexpected error occurred');
    }
  };

  const fetchResults = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/results/${id}`);
      if (!res.ok) {
        if (res.status === 404) {
          // Still running or waiting for results
          return;
        }
        throw new Error('Failed to fetch results');
      }

      const data = await res.json();
      if (data.data) {
        setResults(data.data);
        setIsEnriched(data.enriched);
        if (data.data.scanStatus === 'COMPLETED') {
          setStatus('completed');
        }
      }
    } catch (err: any) {
      console.error('Fetch results error:', err);
    }
  };

  useEffect(() => {
    let interval: any;
    if (status === 'scanning' && executionId) {
      interval = setInterval(() => {
        fetchResults(executionId);
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [status, executionId]);

  return (
    <div className="min-h-screen bg-navy-900 text-gray-100 flex flex-col">
      {/* Top Navigation Bar */}
      <header className="border-b border-navy-700 bg-navy-800/50 backdrop-blur px-8 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Shield className="h-8 w-8 text-electric-blue animate-pulse" />
          <span className="text-xl font-bold tracking-wide bg-gradient-to-r from-electric-blue to-electric-cyan bg-clip-text text-transparent">
            Stitch Security Scanner
          </span>
        </div>
        <div className="flex items-center space-x-4 text-sm text-gray-400">
          <span>Cloud Run Native</span>
          <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span>
          <span>GTI Enriched</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-8 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Scan Trigger Form */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-navy-800/80 border border-navy-700 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
            <h2 className="text-lg font-semibold mb-4 flex items-center space-x-2">
              <Search className="h-5 w-5 text-electric-cyan" />
              <span>Launch Assessment</span>
            </h2>
            <form onSubmit={handleScan} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                  Target Hostname / IP
                </label>
                <input
                  type="text"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="scanme.nmap.org"
                  disabled={status === 'scanning'}
                  className="w-full bg-navy-900 border border-navy-700 rounded-xl px-4 py-3 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-electric-blue transition"
                />
              </div>
              <button
                type="submit"
                disabled={status === 'scanning' || !target}
                className="w-full bg-gradient-to-r from-electric-blue to-electric-cyan text-navy-900 font-bold rounded-xl px-6 py-3 flex items-center justify-center space-x-2 shadow-lg shadow-electric-blue/20 hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === 'scanning' ? (
                  <>
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    <span>Scanning in Progress...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-5 w-5" />
                    <span>Start Tsunami Scan</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Active Status Card */}
          {executionId && (
            <div className="bg-navy-800/80 border border-navy-700 rounded-2xl p-6 shadow-xl backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Execution ID</span>
                <span className="text-xs font-mono bg-navy-900 px-2.5 py-1 rounded border border-navy-700 text-electric-cyan">
                  {executionId.slice(0, 8)}...
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Status</span>
                {status === 'scanning' && (
                  <span className="flex items-center space-x-2 text-yellow-400 text-sm font-medium animate-pulse">
                    <Clock className="h-4 w-4" />
                    <span>Running Scans</span>
                  </span>
                )}
                {status === 'completed' && (
                  <span className="flex items-center space-x-2 text-green-400 text-sm font-medium">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Completed</span>
                  </span>
                )}
                {status === 'error' && (
                  <span className="flex items-center space-x-2 text-red-400 text-sm font-medium">
                    <AlertTriangle className="h-4 w-4" />
                    <span>Scan Failed</span>
                  </span>
                )}
              </div>
              {errorMessage && (
                <div className="bg-red-900/30 border border-red-800 rounded-xl p-4 text-xs text-red-300">
                  {errorMessage}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Findings Dashboard */}
        <div className="lg:col-span-8 space-y-6">
          <div className="bg-navy-800/80 border border-navy-700 rounded-2xl p-6 shadow-xl backdrop-blur-sm min-h-[500px] flex flex-col">
            <div className="flex items-center justify-between border-b border-navy-700 pb-4 mb-6">
              <h2 className="text-lg font-semibold flex items-center space-x-2">
                <Shield className="h-5 w-5 text-electric-blue" />
                <span>Assessment Report</span>
              </h2>
              {results && (
                <div className="flex items-center space-x-2 text-xs">
                  <span className="text-gray-400">Enrichment Layer:</span>
                  <span className={`px-2.5 py-1 rounded font-medium ${isEnriched ? 'bg-green-900/40 text-green-400 border border-green-800' : 'bg-yellow-900/40 text-yellow-400 border border-yellow-800'}`}>
                    {isEnriched ? 'GTI Complete' : 'Pending / Raw'}
                  </span>
                </div>
              )}
            </div>

            {/* No Scan Triggered State */}
            {!results && status === 'idle' && (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-500 space-y-3">
                <Shield className="h-16 w-16 stroke-1 text-navy-700" />
                <p className="text-sm">Enter a target and trigger a scan to view results</p>
              </div>
            )}

            {/* Scanning Waiting State */}
            {!results && status === 'scanning' && (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-400 space-y-4">
                <RefreshCw className="h-12 w-12 animate-spin text-electric-cyan" />
                <div className="text-center space-y-1">
                  <p className="font-medium text-gray-200">Executing Tsunami Reconnaissance...</p>
                  <p className="text-xs text-gray-500">Probing open ports and launching vulnerability plugins</p>
                </div>
              </div>
            )}

            {/* Findings List */}
            {results && (
              <div className="space-y-4 flex-1">
                {results.scanFindings && results.scanFindings.length > 0 ? (
                  results.scanFindings.map((finding, index) => {
                    const vuln = finding.vulnerability;
                    return (
                      <div
                        key={index}
                        className="bg-navy-900/80 border border-navy-700 rounded-xl p-5 hover:border-navy-600 transition shadow-md space-y-3"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center space-x-3">
                              <span className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                                vuln.rating === 'HIGH' || vuln.rating === 'CRITICAL'
                                  ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                  : vuln.rating === 'MEDIUM'
                                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                                  : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                              }`}>
                                {vuln.rating || 'INFO'}
                              </span>
                              <h3 className="font-semibold text-gray-100">{vuln.title || 'Unnamed Finding'}</h3>
                            </div>
                            {vuln.cveId && (
                              <span className="text-xs font-mono text-electric-cyan mt-1 block">
                                {vuln.cveId}
                              </span>
                            )}
                          </div>
                          {vuln.gtiRiskScore !== undefined && (
                            <div className="flex flex-col items-end">
                              <span className="text-xs text-gray-400">GTI Risk Score</span>
                              <span className="text-lg font-bold text-electric-blue font-mono">
                                {vuln.gtiRiskScore}
                              </span>
                            </div>
                          )}
                        </div>
                        {vuln.description && (
                          <p className="text-xs text-gray-400 leading-relaxed">
                            {vuln.description}
                          </p>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-gray-500 space-y-2 py-12">
                    <CheckCircle2 className="h-12 w-12 text-green-500/50" />
                    <p className="text-sm font-medium text-gray-300">No vulnerabilities identified</p>
                    <p className="text-xs text-gray-500">Target appears secure against current Tsunami plugins</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
