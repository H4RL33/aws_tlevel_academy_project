# XP Gamification Frontend Wiring — Design

Date: 2026-07-02

## Purpose

Users should be rewarded XP for reading a Snippet, and a bonus for completing
an Album. The backend already computes this (`gamification_service.py`,
`GET /users/me/stats`) and exposes progress endpoints (`GET /progress`,
`POST /progress/{content_id}`), but nothing on the frontend calls them yet:

- `frontend/src/lib/api/progress.ts` — `getProgress`/`updateProgress` are
  stubs that throw `not implemented`.
- The Snippet reader (`frontend/src/routes/learn/[id]/+page.svelte`) has no
  UI or logic that marks a Snippet as read.
- There is no way for the Snippet reader to know, on load, whether the
  current user has already read the Snippet.

This design wires up the missing frontend piece plus one small backend
addition needed to support it. Album completion needs no separate trigger:
`gamification_service.get_stats` already derives `albums_completed` (and its
XP bonus) purely from `UserContentProgress` rows, so completing the last
unread Snippet in an enrolled Album is what completes it.

## Non-goals

- No toast/animation for XP earned — feedback is an inline button state
  change only (per earlier decision).
- No live cross-page XP sync store — the home page's XP total refreshes via
  its existing `getStats()` call next time it loads.
- No change to `XPBadge.svelte` (still a stub, unused) or to `SnippetCard`'s
  existing `+xp` badge prop — neither is fed by this work.
- No scroll-tracking or reading-time heuristics — completion is an explicit
  user action.

## Backend change

`ContentDetailResponse` (`backend/app/schemas/content.py`) gains:

```python
is_completed: bool = False
```

`snippet_service.get_snippet` (`backend/app/services/snippet_service.py`)
computes it the same way it already computes `is_saved`: look up the
`UserContentProgress` row for `(user.id, content_id)` when `user is not
None`, and set `is_completed = row is not None and row.progress_pct == 100`.

## Frontend changes

### `frontend/src/lib/api/progress.ts`

Replace the stubs with real calls:

```ts
export async function getProgress(): Promise<ProgressResponse[]> {
  return apiFetch<ProgressResponse[]>('/progress');
}

export async function updateProgress(contentId: number, progressPct: number): Promise<void> {
  await apiFetch(`/progress/${contentId}`, {
    method: 'POST',
    body: JSON.stringify({ progress_pct: progressPct }),
  });
}
```

### `frontend/src/lib/api/types.ts`

Add `is_completed: boolean` to `ContentDetailResponse`.

### `frontend/src/routes/learn/[id]/+page.svelte`

For a logged-in user (`$currentUser`) viewing a Snippet:

- Track local completion state, initialised from `snippet.is_completed` when
  the Snippet loads.
- Render a "Mark as read (+10 XP)" button below the Snippet body (mirrors
  the existing save-button's auth-gating and placement pattern already in
  this file).
- On click: call `updateProgress(snippet.id, 100)`, then flip local state so
  the button becomes a disabled "✓ Read" state. On failure, leave the button
  clickable and show the same inline error pattern already used for
  load failures on this page (no separate toast).
- If the state is already "read" on load (from `is_completed`), render
  directly in the read state — no flash of the unread button.

No changes are needed to `AlbumSidebar`, `CTASidebar`, or the home page:
Album completion is derived server-side, and the home page already fetches
`total_xp`/`snippets_completed` via `getStats()` on mount for authenticated
users.

## Testing

- Backend: extend `snippet_service`/`content` router tests to cover
  `is_completed` in both states (no progress row, and a `progress_pct == 100`
  row) — follow the existing `is_saved` test pattern.
- Frontend: unit tests for `progress.ts` (`getProgress`/`updateProgress` hit
  the right endpoints/payloads), and a test for the Snippet reader's mark-as-read
  button (renders unread/read state correctly, calls `updateProgress`, flips
  state on success, stays clickable on failure).
