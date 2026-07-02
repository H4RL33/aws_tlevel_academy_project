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

**Correction from the initial design:** the Snippet reader
(`learn/[id]/+page.svelte`) calls `getContent()` → `GET /content/{id}` →
`content_service.get_content`, **not** `GET /snippets/{id}` →
`snippet_service.get_snippet`. The two are separate, parallel code paths
(`snippet_service.get_snippet` backs the save/unsave-only `/snippets/{id}`
route; `content_service.get_content` backs the public, no-required-auth
`/content/{id}` route the reader actually uses). The `is_completed` field
must be added to the path the reader actually hits, so this design targets
`content_service.get_content` instead.

`ContentDetailResponse` (`backend/app/schemas/content.py`) gains:

```python
is_completed: bool = False
```

`backend/app/routers/content.py`'s `GET /{content_id}` route gains an
optional-auth dependency, mirroring how `snippets.py`'s `GET /{content_id}`
already does it:

```python
current_user: User | None = Depends(get_current_user_optional)
```

(`get_current_user_optional` calls `get_current_user` as a plain function
rather than as a nested `Depends`, so it never 401s and doesn't trip the
existing `test_no_content_route_depends_on_get_current_user` guard test —
the route stays public.)

`content_service.get_content` gains a `user: User | None = None` parameter
and computes `is_completed` the same way `snippet_service.get_snippet`
already computes `is_saved`: look up the `UserContentProgress` row for
`(user.id, content_id)` when `user is not None`, and set
`is_completed = row is not None and row.progress_pct == 100`.

## Frontend changes

### `frontend/src/lib/api/progress.ts`

Implement `updateProgress` only:

```ts
export async function updateProgress(contentId: number, progressPct: number): Promise<void> {
  await apiFetch(`/progress/${contentId}`, {
    method: 'POST',
    body: JSON.stringify({ progress_pct: progressPct }),
  });
}
```

`getProgress` stays a stub. It backs the "continue reading" widget, which
this design doesn't build (nothing consumes it) — implementing it now would
be dead code.

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

- Backend: extend `test_content_service.py`/`test_content.py` to cover
  `is_completed` in both states (no progress row, and a `progress_pct == 100`
  row) — follow the existing `is_saved` test pattern in
  `test_snippet_service.py`.
- Frontend: unit tests for `progress.ts` (`getProgress`/`updateProgress` hit
  the right endpoints/payloads), matching the existing `*.test.ts` pattern
  used for other `lib/api/*.ts` modules. No `+page.svelte` route currently
  has automated tests in this codebase (only `lib/components` and `lib/api`
  do), so the mark-as-read button in `learn/[id]/+page.svelte` is verified
  manually in the browser instead of via a new route-test pattern.
