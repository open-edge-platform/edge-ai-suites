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
