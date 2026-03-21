import type { ValidationSummary as SummaryData } from '../types';

interface Props {
  summary: SummaryData;
  segmentCount: number;
  transactionType: string;
}

function StatCard({ label, value, accent }: { label: string; value: number | string; accent: string }) {
  return (
    <div className="glass-card p-4 flex flex-col gap-1 min-w-[120px]">
      <span className="text-xs uppercase tracking-wider text-[var(--text-muted)]">{label}</span>
      <span className={`text-2xl font-bold ${accent}`}>{value}</span>
    </div>
  );
}

export default function ValidationSummary({ summary, segmentCount, transactionType }: Props) {
  const hasErrors = summary.total_errors > 0 || summary.total_warnings > 0;

  return (
    <div className="animate-fade-in" id="validation-summary">
      {/* header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-3 h-3 rounded-full ${hasErrors ? 'bg-[var(--accent-red)]' : 'bg-[var(--accent-green)]'} animate-pulse-glow`} />
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Validation Results
        </h2>
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] font-mono">
          {transactionType}
        </span>
      </div>

      {/* stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        <StatCard label="Segments" value={segmentCount} accent="text-[var(--text-primary)]" />
        <StatCard label="Errors" value={summary.total_errors} accent={summary.total_errors > 0 ? 'text-[var(--accent-red)]' : 'text-[var(--accent-green)]'} />
        <StatCard label="Warnings" value={summary.total_warnings} accent={summary.total_warnings > 0 ? 'text-[var(--accent-yellow)]' : 'text-[var(--accent-green)]'} />
        <StatCard label="SNIP 1" value={summary.snip1_errors} accent={summary.snip1_errors > 0 ? 'text-[var(--accent-red)]' : 'text-[var(--text-muted)]'} />
        <StatCard label="SNIP 2" value={summary.snip2_errors} accent={summary.snip2_errors > 0 ? 'text-[var(--accent-red)]' : 'text-[var(--text-muted)]'} />
        <StatCard label="SNIP 3" value={summary.snip3_errors} accent={summary.snip3_errors > 0 ? 'text-[var(--accent-red)]' : 'text-[var(--text-muted)]'} />
      </div>
    </div>
  );
}
