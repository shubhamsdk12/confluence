import type { Segment, ValidationError } from '../types';

interface Props {
  segment: Segment | null;
  errors: ValidationError[];
  onClose: () => void;
  onExplain: (error: ValidationError) => void;
}

export default function SegmentDetail({ segment, errors, onClose, onExplain }: Props) {
  if (!segment) return null;

  const segErrors = errors.filter(
    (e) => e.segment_id === segment.segment_id,
  );

  return (
    <div className="glass-card p-5 animate-slide-right overflow-auto max-h-[70vh]" id="segment-detail">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm px-2 py-1 rounded bg-[var(--accent-cyan)]/15 text-[var(--accent-cyan)]">
            {segment.segment_id}
          </span>
          {segment.ui_label && (
            <span className="text-sm text-[var(--text-secondary)]">{segment.ui_label}</span>
          )}
          <span className="text-xs text-[var(--text-muted)]">Line {segment.line_number}</span>
        </div>
        <button
          onClick={onClose}
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
          id="close-segment-detail"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Raw segment */}
      <div className="mb-4">
        <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-1">Raw</h4>
        <pre className="text-xs font-mono text-[var(--text-secondary)] bg-[var(--bg-primary)] p-3 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
          {segment.raw}
        </pre>
      </div>

      {/* Elements table */}
      <div className="mb-4">
        <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Elements</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-muted)] border-b border-[var(--border-primary)]">
                <th className="py-1.5 pr-3 w-12">Pos</th>
                <th className="py-1.5 pr-3">Value</th>
                <th className="py-1.5">Sub-Elements</th>
              </tr>
            </thead>
            <tbody>
              {segment.elements.map((el) => {
                const elError = segErrors.find((e) => e.element_position === el.position);
                return (
                  <tr
                    key={el.position}
                    className={`border-b border-[var(--border-primary)]/50 ${elError ? 'bg-[var(--accent-red)]/5' : ''}`}
                  >
                    <td className="py-1.5 pr-3 font-mono text-xs text-[var(--text-muted)]">{el.position}</td>
                    <td className={`py-1.5 pr-3 font-mono text-xs ${elError ? 'text-[var(--accent-red)]' : 'text-[var(--text-primary)]'}`}>
                      {el.value || <span className="text-[var(--text-muted)] italic">empty</span>}
                    </td>
                    <td className="py-1.5 font-mono text-xs text-[var(--text-muted)]">
                      {el.sub_elements.length > 0 ? el.sub_elements.join(' : ') : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Errors */}
      {segErrors.length > 0 && (
        <div>
          <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Validation Errors</h4>
          <div className="flex flex-col gap-2">
            {segErrors.map((err, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg border ${err.severity === 'error' ? 'border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5' : err.severity === 'warning' ? 'border-[var(--accent-yellow)]/30 bg-[var(--accent-yellow)]/5' : 'border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/5'}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-medium ${err.severity === 'error' ? 'text-[var(--accent-red)]' : err.severity === 'warning' ? 'text-[var(--accent-yellow)]' : 'text-[var(--accent-blue)]'}`}>
                    {err.code} · SNIP {err.snip_level}
                  </span>
                  <button
                    onClick={() => onExplain(err)}
                    className="text-xs px-2 py-0.5 rounded bg-[var(--accent-purple)]/15 text-[var(--accent-purple)] hover:bg-[var(--accent-purple)]/25 transition-colors"
                    id={`explain-${err.code}`}
                  >
                    Explain
                  </button>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">{err.message}</p>
                {err.suggestion && (
                  <p className="text-xs text-[var(--text-muted)] mt-1 italic">💡 {err.suggestion}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
