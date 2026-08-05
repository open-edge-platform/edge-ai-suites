export const shortId = (id: string): string => (id ? id.slice(0, 8) : '');

export const toErrorMessage = (e: unknown): string =>
  e instanceof Error ? e.message : String(e);

export const formatElapsed = (
  createdAt: string | undefined,
  endedAt: string | null | undefined,
  now?: number,
): string => {
  if (!createdAt) return '—';
  const start = Date.parse(createdAt);
  const end = endedAt ? Date.parse(endedAt) : (now ?? Date.now());
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '—';
  let s = Math.floor((end - start) / 1000);
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`;
  return `${s}s`;
};

/** Format an ISO timestamp as "YYYY-MM-DD HH:MM" (plus seconds when `withSeconds`). Falls back to the raw input if parsing fails. */
export const formatDateTime = (iso: string, withSeconds = false): string => {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    const base = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    return withSeconds ? `${base}:${pad(d.getSeconds())}` : base;
  } catch {
    return iso;
  }
};

/** Whether a grading task status is terminal (no further progress will happen). */
export const isTerminalStatus = (status: string): boolean =>
  status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED';

/** Compare two strings numerically when both parse as numbers, otherwise lexically. */
export const compareByNumericThenString = (a: string, b: string): number => {
  const na = Number(a);
  const nb = Number(b);
  const aNum = !Number.isNaN(na);
  const bNum = !Number.isNaN(nb);
  if (aNum && bNum) return na - nb;
  if (aNum) return -1;
  if (bNum) return 1;
  return a.localeCompare(b);
};
