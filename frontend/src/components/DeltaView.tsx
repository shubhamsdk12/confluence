import { useState } from 'react';
import type { DeltaReport, DeltaMember } from '../types';
import { deltaFiles } from '../api';
import FileUpload from './FileUpload';

export default function DeltaView() {
  const [oldFile, setOldFile] = useState<File | null>(null);
  const [newFile, setNewFile] = useState<File | null>(null);
  const [report, setReport] = useState<DeltaReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleDelta = async () => {
    if (!oldFile || !newFile) return;
    setLoading(true);
    setError('');
    try {
      const result = await deltaFiles(oldFile, newFile);
      setReport(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delta computation failed');
    } finally {
      setLoading(false);
    }
  };

  const statusDot = (s: string) => {
    if (s === 'Added') return '🟢';
    if (s === 'Changed') return '🟡';
    if (s === 'Terminated') return '🔴';
    return '⚪';
  };

  const statusClass = (s: string) => {
    if (s === 'Added') return 'row-added';
    if (s === 'Changed') return 'row-changed';
    if (s === 'Terminated') return 'row-terminated';
    return '';
  };

  const MemberRow = ({ member }: { member: DeltaMember }) => (
    <>
      <tr
        className={`border-b border-[var(--border-primary)]/50 cursor-pointer hover:bg-[var(--bg-card-hover)] transition-colors ${statusClass(member.status)}`}
        onClick={() => setExpandedId(expandedId === member.subscriber_id ? null : member.subscriber_id)}
      >
        <td className="p-3 text-center">{statusDot(member.status)}</td>
        <td className="p-3 font-mono text-xs">{member.subscriber_id}</td>
        <td className="p-3 text-sm">{member.name}</td>
        <td className="p-3 text-xs font-mono text-[var(--text-muted)]">{member.maintenance_code || '—'}</td>
        <td className="p-3 text-xs text-[var(--text-muted)]">{member.insurance_type || '—'}</td>
        <td className="p-3 text-xs font-mono text-[var(--text-muted)]">{member.benefit_start || '—'}</td>
      </tr>
      {expandedId === member.subscriber_id && member.changes && member.changes.length > 0 && (
        <tr>
          <td colSpan={6} className="p-0">
            <div className="p-3 bg-[var(--bg-primary)] animate-fade-in">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[var(--text-muted)]">
                    <th className="text-left py-1 px-2">Field</th>
                    <th className="text-left py-1 px-2">Old Value</th>
                    <th className="text-left py-1 px-2">→</th>
                    <th className="text-left py-1 px-2">New Value</th>
                  </tr>
                </thead>
                <tbody>
                  {member.changes.map((c, i) => (
                    <tr key={i}>
                      <td className="py-1 px-2 font-medium text-[var(--text-secondary)]">{c.field}</td>
                      <td className="py-1 px-2 text-[var(--accent-red)] font-mono">{c.old_value || '—'}</td>
                      <td className="py-1 px-2 text-[var(--text-muted)]">→</td>
                      <td className="py-1 px-2 text-[var(--accent-green)] font-mono">{c.new_value || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );

  return (
    <div className="flex flex-col gap-6 animate-fade-in" id="delta-view">
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">834 Enrollment Delta</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FileUpload id="old-834-upload" label="Previous 834 File" onFile={setOldFile} />
        <FileUpload id="new-834-upload" label="Current 834 File" onFile={setNewFile} />
      </div>

      {oldFile && newFile && !report && (
        <button
          onClick={handleDelta}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-[var(--accent-green)] to-[var(--accent-cyan)] text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          id="delta-btn"
        >
          {loading ? 'Computing Delta…' : '📊 Compare Enrollment Files'}
        </button>
      )}

      {error && <div className="badge-error p-3 rounded-lg text-sm">{error}</div>}

      {report && (
        <div className="flex flex-col gap-5 animate-fade-in">
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-green)]">{report.summary.total_added}</div>
              <div className="text-xs text-[var(--text-muted)]">🟢 Added</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-yellow)]">{report.summary.total_changed}</div>
              <div className="text-xs text-[var(--text-muted)]">🟡 Changed</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--accent-red)]">{report.summary.total_terminated}</div>
              <div className="text-xs text-[var(--text-muted)]">🔴 Terminated</div>
            </div>
            <div className="glass-card p-4 text-center">
              <div className="text-2xl font-bold text-[var(--text-muted)]">{report.summary.total_unchanged}</div>
              <div className="text-xs text-[var(--text-muted)]">⚪ Unchanged</div>
            </div>
          </div>

          {/* Table */}
          {(report.added.length > 0 || report.changed.length > 0 || report.terminated.length > 0) && (
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-primary)]">
                      <th className="p-3 w-12">Status</th>
                      <th className="p-3">Subscriber ID</th>
                      <th className="p-3">Name</th>
                      <th className="p-3">Maint. Code</th>
                      <th className="p-3">Insurance</th>
                      <th className="p-3">Benefit Start</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.added.map((m) => <MemberRow key={m.subscriber_id} member={m} />)}
                    {report.changed.map((m) => <MemberRow key={m.subscriber_id} member={m} />)}
                    {report.terminated.map((m) => <MemberRow key={m.subscriber_id} member={m} />)}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
