const BASE = '/api';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail?.message ?? body.detail ?? res.statusText);
  }
  return res.json();
}

function fileForm(name: string, file: File): FormData {
  const fd = new FormData();
  fd.append(name, file);
  return fd;
}

/* ─── Parse ─── */
export async function parseFile(file: File) {
  return request<import('./types').ParseResponse>('/parse', {
    method: 'POST',
    body: fileForm('file', file),
  });
}

/* ─── Validate ─── */
export async function validateFile(file: File) {
  return request<import('./types').ValidateResponse>('/validate', {
    method: 'POST',
    body: fileForm('file', file),
  });
}

/* ─── Reconcile ─── */
export async function reconcileFiles(claimFile: File, remittanceFile: File) {
  const fd = new FormData();
  fd.append('claim_file', claimFile);
  fd.append('remittance_file', remittanceFile);
  return request<import('./types').ReconciliationReport>('/reconcile', {
    method: 'POST',
    body: fd,
  });
}

/* ─── Delta ─── */
export async function deltaFiles(oldFile: File, newFile: File) {
  const fd = new FormData();
  fd.append('old_file', oldFile);
  fd.append('new_file', newFile);
  return request<import('./types').DeltaReport>('/delta', {
    method: 'POST',
    body: fd,
  });
}

/* ─── AI Explain ─── */
export async function explainError(error: import('./types').ValidationError) {
  return request<import('./types').ExplainResponse>('/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(error),
  });
}
