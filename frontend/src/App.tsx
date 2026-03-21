import { useState } from 'react';
import type { ActiveView, ParseResult, Segment, ValidationError, ValidateResponse } from './types';
import { validateFile } from './api';
import FileUpload from './components/FileUpload';
import EdiTree from './components/EdiTree';
import ValidationSummary from './components/ValidationSummary';
import SegmentDetail from './components/SegmentDetail';
import AiPanel from './components/AiPanel';
import ReconciliationView from './components/ReconciliationView';
import DeltaView from './components/DeltaView';

/* ─── Tab config ─── */
const TABS: { key: ActiveView; label: string; icon: string }[] = [
  { key: 'validate', label: 'Parse & Validate', icon: '🔍' },
  { key: 'reconcile', label: 'Reconciliation', icon: '🔗' },
  { key: 'delta', label: 'Enrollment Delta', icon: '📊' },
];

export default function App() {
  const [view, setView] = useState<ActiveView>('validate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Validate state
  const [validateResult, setValidateResult] = useState<ValidateResponse | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  const [aiError, setAiError] = useState<ValidationError | null>(null);

  const handleValidate = async (file: File) => {
    setLoading(true);
    setError('');
    setValidateResult(null);
    setSelectedSegment(null);
    try {
      const res = await validateFile(file);
      setValidateResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ─── Header ─── */}
      <header className="border-b border-[var(--border-primary)] bg-[var(--bg-secondary)]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-[var(--accent-blue)]/20">
              X12
            </div>
            <div>
              <h1 className="text-base font-bold text-[var(--text-primary)]">EDI Parser & Validator</h1>
              <p className="text-xs text-[var(--text-muted)]">X12 Healthcare · HIPAA 5010</p>
            </div>
          </div>

          {/* Nav tabs */}
          <nav className="flex gap-1 bg-[var(--bg-primary)] rounded-xl p-1" id="main-nav">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => { setView(tab.key); setError(''); }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  view === tab.key
                    ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] shadow-inner'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                }`}
                id={`tab-${tab.key}`}
              >
                <span className="mr-1.5">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* ─── Main Content ─── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {/* Global error */}
        {error && (
          <div className="mb-4 p-3 rounded-xl badge-error text-sm animate-fade-in" id="global-error">
            {error}
          </div>
        )}

        {/* ─── Validate View ─── */}
        {view === 'validate' && (
          <div className="flex flex-col gap-6 animate-fade-in">
            <FileUpload id="validate-upload" label="Upload EDI File to Parse & Validate" onFile={handleValidate} />

            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="w-10 h-10 border-3 border-[var(--accent-blue)] border-t-transparent rounded-full animate-spin" />
              </div>
            )}

            {validateResult && (
              <>
                <ValidationSummary
                  summary={validateResult.summary}
                  segmentCount={validateResult.parse_result.segment_count}
                  transactionType={validateResult.parse_result.transaction_type}
                />

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Tree (2/3 width) */}
                  <div className="lg:col-span-2">
                    <EdiTree
                      loops={validateResult.parse_result.loops}
                      errors={validateResult.validation_errors}
                      onSelectSegment={setSelectedSegment}
                    />
                  </div>

                  {/* Detail panel (1/3 width) */}
                  <div>
                    <SegmentDetail
                      segment={selectedSegment}
                      errors={validateResult.validation_errors}
                      onClose={() => setSelectedSegment(null)}
                      onExplain={(err) => setAiError(err)}
                    />
                    {!selectedSegment && (
                      <div className="glass-card p-6 text-center text-[var(--text-muted)] text-sm">
                        Click a segment in the tree to view details
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ─── Reconciliation View ─── */}
        {view === 'reconcile' && <ReconciliationView />}

        {/* ─── Delta View ─── */}
        {view === 'delta' && <DeltaView />}
      </main>

      {/* ─── AI Panel Overlay ─── */}
      {aiError && (
        <>
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
            onClick={() => setAiError(null)}
          />
          <AiPanel error={aiError} onClose={() => setAiError(null)} />
        </>
      )}

      {/* ─── Footer ─── */}
      <footer className="border-t border-[var(--border-primary)] py-3 text-center text-xs text-[var(--text-muted)]">
        EDI Parser &amp; Validator · COEP Inspiron
      </footer>
    </div>
  );
}
