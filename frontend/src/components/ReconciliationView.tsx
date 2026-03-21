import { useState } from 'react';
import type { ReconciliationReport } from '../types';
import { reconcileFiles } from '../api';
import FileUpload from './FileUpload';

export default function ReconciliationView() {
  const [claimFile, setClaimFile] = useState<File | null>(null);
  const [remitFile, setRemitFile] = useState<File | null>(null);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleReconcile = async () => {
    if (!claimFile || !remitFile) return;
    setLoading(true);
    setError('');
    try {
      const result = await reconcileFiles(claimFile, remitFile);
      setReport(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Reconciliation failed');
    } finally {
      setLoading(false);
    }
  };

  const statusClass = (status: string) => {
    if (status === 'Paid in Full') return 'row-paid';
    if (status === 'Partial') return 'row-partial';
    if (status === 'Denied') return 'row-denied';
    return 'row-unmatched';
  };

  const statusDot = (status: string) => {
    if (status === 'Paid in Full') return '🟢';
    if (status === 'Partial') return '🟡';
    if (status === 'Denied') return '🔴';
    return '⚪';
  };

  return (
    <div className="flex flex-col gap-6 animate-fade-in" id="reconciliation-view">
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">835 ↔ 837 Reconciliation</h2>

      {/* File uploads */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FileUpload id="claim-upload" label="837 Claims File" onFile={setClaimFile} />
        <FileUpload id="remit-upload" label="835 Remittance File" onFile={setRemitFile} />
      </div>

      {claimFile && remitFile && !report && (
        <button
          onClick={handleReconcile}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent-cyan)] to-[var(--accent-blue)] text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          id="reconcile-btn"
        >
          {loading ? 'Reconciling…' : '🔗 Reconcile Files'}
        </button>
      )}

      {error && <div className="badge-error p-3 rounded-lg text-sm">{error}</div>}

      {/* Report */}
      {report && (
        <div className="flex flex-col gap-5 animate-fade-in">
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-green)]">{report.summary.total_matched}</div>
              <div className="text-xs text-[var(--text-muted)]">Matched</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--text-muted)]">{report.summary.total_unmatched_claims}</div>
              <div className="text-xs text-[var(--text-muted)]">Unmatched Claims</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-blue)]">${report.summary.total_billed.toFixed(2)}</div>
              <div className="text-xs text-[var(--text-muted)]">Total Billed</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-cyan)]">${report.summary.total_paid.toFixed(2)}</div>
              <div className="text-xs text-[var(--text-muted)]">Total Paid</div>
            </div>
          </div>

          {/* Matched table */}
          {report.matched.length > 0 && (
            <div className="glass-card overflow-hidden">
              <div className="p-3 border-b border-[var(--border-primary)]">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Matched Claims</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-primary)]">
                      <th className="p-3">Status</th>
                      <th className="p-3">Claim ID</th>
                      <th className="p-3 text-right">Billed</th>
                      <th className="p-3 text-right">Paid</th>
                      <th className="p-3 text-right">Adjustments</th>
                      <th className="p-3">Adj. Codes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.matched.map((m, i) => (
                      <tr key={i} className={`border-b border-[var(--border-primary)]/50 ${statusClass(m.status)}`}>
                        <td className="p-3 text-center">{statusDot(m.status)}</td>
                        <td className="p-3 font-mono text-xs">{m.claim_id}</td>
                        <td className="p-3 text-right font-mono text-xs">${m.billed_amount.toFixed(2)}</td>
                        <td className="p-3 text-right font-mono text-xs">${m.paid_amount.toFixed(2)}</td>
                        <td className="p-3 text-right font-mono text-xs">${m.total_adjustments.toFixed(2)}</td>
                        <td className="p-3 font-mono text-xs text-[var(--text-muted)]">{m.adjustment_codes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Unmatched */}
          {report.unmatched_claims.length > 0 && (
            <div className="glass-card p-4">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">Unmatched Claims (837 only)</h3>
              <div className="flex flex-col gap-1">
                {report.unmatched_claims.map((uc, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm text-[var(--text-muted)]">
                    <span>⚪</span>
                    <span className="font-mono text-xs">{uc.claim_id}</span>
                    <span className="ml-auto font-mono text-xs">${uc.billed_amount.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
