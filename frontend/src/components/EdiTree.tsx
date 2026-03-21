import { useState } from 'react';
import type { Loop, Segment, ValidationError } from '../types';

/* ─── Props ─── */
interface TreeProps {
  loops: Loop[];
  errors: ValidationError[];
  onSelectSegment: (segment: Segment) => void;
}

interface LoopNodeProps {
  loop: Loop;
  depth: number;
  errors: ValidationError[];
  onSelectSegment: (segment: Segment) => void;
}

/* ─── Helpers ─── */
function errorsForSegment(seg: Segment, errors: ValidationError[]) {
  return errors.filter(
    (e) => e.segment_id === seg.segment_id && (e.element_position === null || seg.elements.some((el) => el.position === e.element_position)),
  );
}

function countErrors(loop: Loop, errors: ValidationError[]): { err: number; warn: number } {
  let err = 0, warn = 0;
  for (const seg of loop.segments) {
    for (const e of errorsForSegment(seg, errors)) {
      if (e.severity === 'error') err++;
      else if (e.severity === 'warning') warn++;
    }
  }
  for (const child of loop.children) {
    const c = countErrors(child, errors);
    err += c.err;
    warn += c.warn;
  }
  return { err, warn };
}

/* ─── LoopNode ─── */
function LoopNode({ loop, depth, errors, onSelectSegment }: LoopNodeProps) {
  const [open, setOpen] = useState(depth < 2);
  const { err, warn } = countErrors(loop, errors);
  const hasChildren = loop.children.length > 0 || loop.segments.length > 0;

  return (
    <div className="tree-node animate-fade-in" style={{ animationDelay: `${depth * 30}ms` }}>
      <button
        className="flex items-center gap-2 w-full text-left py-1.5 px-2 rounded-lg hover:bg-[var(--bg-card-hover)] transition-colors group"
        onClick={() => setOpen(!open)}
        id={`loop-${loop.loop_id}`}
      >
        {/* chevron */}
        {hasChildren && (
          <svg
            className={`w-4 h-4 text-[var(--text-muted)] transition-transform ${open ? 'rotate-90' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        )}
        {!hasChildren && <span className="w-4" />}

        {/* loop label */}
        <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-[var(--accent-purple)]/15 text-[var(--accent-purple)]">
          {loop.loop_id}
        </span>
        <span className="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors truncate">
          {loop.ui_label || loop.loop_id}
        </span>

        {/* badges */}
        <span className="ml-auto flex gap-1.5">
          {err > 0 && (
            <span className="badge-error text-xs px-1.5 py-0.5 rounded-full font-medium">{err}</span>
          )}
          {warn > 0 && (
            <span className="badge-warning text-xs px-1.5 py-0.5 rounded-full font-medium">{warn}</span>
          )}
        </span>
      </button>

      {open && (
        <div className="ml-4 border-l border-[var(--border-primary)] pl-2">
          {/* segments */}
          {loop.segments.map((seg, i) => {
            const segErrors = errorsForSegment(seg, errors);
            return (
              <button
                key={`${seg.segment_id}-${i}`}
                className="flex items-center gap-2 w-full text-left py-1 px-2 rounded hover:bg-[var(--bg-card-hover)] transition-colors text-sm"
                onClick={() => onSelectSegment(seg)}
                id={`seg-${seg.segment_id}-${seg.line_number}`}
              >
                <span className="font-mono text-xs text-[var(--accent-cyan)] min-w-[32px]">{seg.segment_id}</span>
                <span className="text-[var(--text-muted)] truncate flex-1 text-xs font-mono">{seg.raw.slice(0, 80)}</span>
                {segErrors.map((e, j) => (
                  <span
                    key={j}
                    className={`text-xs px-1.5 py-0.5 rounded-full ${e.severity === 'error' ? 'badge-error' : e.severity === 'warning' ? 'badge-warning' : 'badge-info'}`}
                  >
                    {e.code.replace(/^SNIP\d_/, '')}
                  </span>
                ))}
              </button>
            );
          })}

          {/* children loops */}
          {loop.children.map((child) => (
            <LoopNode
              key={child.loop_id}
              loop={child}
              depth={depth + 1}
              errors={errors}
              onSelectSegment={onSelectSegment}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── EdiTree ─── */
export default function EdiTree({ loops, errors, onSelectSegment }: TreeProps) {
  if (!loops.length) {
    return (
      <div className="glass-card p-6 text-center text-[var(--text-muted)]">
        No data to display. Upload an EDI file to see the tree.
      </div>
    );
  }

  return (
    <div className="glass-card p-4 overflow-auto max-h-[70vh]" id="edi-tree">
      <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
        Loop Hierarchy
      </h3>
      {loops.map((loop) => (
        <LoopNode
          key={loop.loop_id}
          loop={loop}
          depth={0}
          errors={errors}
          onSelectSegment={onSelectSegment}
        />
      ))}
    </div>
  );
}
