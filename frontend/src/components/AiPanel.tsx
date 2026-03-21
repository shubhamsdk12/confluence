import { useState } from 'react';
import type { ValidationError, ExplainResponse } from '../types';
import { explainError } from '../api';

interface Props {
  error: ValidationError | null;
  onClose: () => void;
}

export default function AiPanel({ error, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [fetchError, setFetchError] = useState('');

  const handleExplain = async () => {
    if (!error) return;
    setLoading(true);
    setFetchError('');
    try {
      const result = await explainError(error);
      setExplanation(result);
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : 'Failed to get explanation');
    } finally {
      setLoading(false);
    }
  };

  if (!error) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md glass-card shadow-2xl animate-slide-right z-50 flex flex-col" id="ai-panel">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border-primary)]">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-blue)] flex items-center justify-center text-white text-sm font-bold">
            AI
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Error Explanation</h3>
            <p className="text-xs text-[var(--text-muted)]">{error.code}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
          id="close-ai-panel"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 flex flex-col gap-4">
        {/* Error details */}
        <div className={`p-3 rounded-lg border ${error.severity === 'error' ? 'border-[var(--accent-red)]/30 bg-[var(--accent-red)]/5' : 'border-[var(--accent-yellow)]/30 bg-[var(--accent-yellow)]/5'}`}>
          <p className="text-sm text-[var(--text-primary)]">{error.message}</p>
          <div className="flex gap-2 mt-2 text-xs text-[var(--text-muted)]">
            <span>SNIP {error.snip_level}</span>
            <span>·</span>
            <span>{error.segment_id}{error.element_position !== null ? ` [${error.element_position}]` : ''}</span>
          </div>
        </div>

        {/* Explain button */}
        {!explanation && !loading && (
          <button
            onClick={handleExplain}
            className="w-full py-2.5 rounded-lg bg-gradient-to-r from-[var(--accent-purple)] to-[var(--accent-blue)] text-white font-medium text-sm hover:opacity-90 transition-opacity"
            id="get-explanation"
          >
            🧠 Get AI Explanation
          </button>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="w-8 h-8 border-2 border-[var(--accent-purple)] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Error */}
        {fetchError && (
          <div className="p-3 rounded-lg badge-error text-sm">{fetchError}</div>
        )}

        {/* Explanation */}
        {explanation && (
          <div className="flex flex-col gap-4 animate-fade-in">
            <div>
              <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Plain English</h4>
              <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">{explanation.plain_english}</div>
            </div>

            {explanation.suggested_fix && (
              <div>
                <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Suggested Fix</h4>
                <div className="p-3 rounded-lg bg-[var(--accent-green)]/10 border border-[var(--accent-green)]/20 text-sm text-[var(--accent-green)]">
                  {explanation.suggested_fix}
                </div>
              </div>
            )}

            {explanation.regulatory_context && explanation.regulatory_context.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Regulatory Context</h4>
                <div className="flex flex-col gap-2">
                  {explanation.regulatory_context.map((ctx, i) => (
                    <div key={i} className="text-xs text-[var(--text-muted)] p-2 bg-[var(--bg-primary)] rounded-lg">
                      {ctx}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {explanation.sources && explanation.sources.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider text-[var(--text-muted)] mb-2">Sources</h4>
                <div className="flex flex-wrap gap-1.5">
                  {explanation.sources.map((src, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-[var(--bg-card)] text-[var(--text-muted)]">
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
