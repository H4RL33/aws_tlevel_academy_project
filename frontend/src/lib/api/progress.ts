import { apiFetch } from './client';
import type { ProgressResponse } from './types';

export async function getProgress(): Promise<ProgressResponse[]> {
  throw new Error('not implemented');
}

export async function updateProgress(contentId: number, progressPct: number): Promise<void> {
  await apiFetch<void>(`/progress/${contentId}`, {
    method: 'POST',
    body: JSON.stringify({ progress_pct: progressPct }),
  });
}
