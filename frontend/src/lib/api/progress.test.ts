import { afterEach, describe, expect, it, vi } from 'vitest';
import { updateProgress } from './progress';

describe('updateProgress', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('POSTs progress_pct to /progress/{contentId}', async () => {
    const mockFetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', mockFetch);

    await updateProgress(7, 100);

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toContain('/progress/7');
    expect(init.method).toBe('POST');
    expect(init.body).toContain('100');
  });
});
