# XP Gamification Frontend Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the frontend so reading a Snippet awards XP (via the existing backend `progress` endpoints and `gamification_service`), and completing an Album's last unread Snippet triggers the existing Album-completion XP bonus automatically.

**Architecture:** Implement the two stub frontend API functions (`getProgress`/`updateProgress`) that already have a working backend behind them. Add a small `is_completed` field to the Snippet-detail response (on the `/content/{id}` route the reader page actually uses — not the separate `/snippets/{id}` route) so the reader page knows on load whether to show "Mark as read" or "✓ Read". Add a "Mark as read" button to the Snippet reader page that calls `updateProgress` and flips to a disabled read state inline (no toast). No Album-specific frontend code is needed — `gamification_service.get_stats` already derives Album completion from `UserContentProgress` rows.

**Tech Stack:** FastAPI + SQLAlchemy (async) + pytest (backend); SvelteKit + TypeScript + vitest (frontend).

---

## Design doc

Full design: `docs/superpowers/specs/2026-07-02-xp-gamification-frontend-design.md`

---

### Task 1: Backend — add `is_completed` to `ContentDetailResponse`

**Files:**
- Modify: `backend/app/schemas/content.py`
- Test: `backend/tests/test_content_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_content_service.py` (after the existing tests, using the same `_make_topic` helper already defined in that file):

```python
async def test_get_content_returns_is_completed_false_when_no_progress_row(
    db_session: AsyncSession,
) -> None:
    from app.models.user import User

    topic = await _make_topic(db_session)
    content = Content(
        title="Intro",
        body="Body",
        content_type=ContentType.article,
        topic_id=topic.id,
    )
    db_session.add(content)
    user = User(cognito_sub="sub-1", email="a@example.com", first_name="A", last_name="B")
    db_session.add(user)
    await db_session.commit()

    result = await content_service.get_content(db_session, content.id, user=user)

    assert result.is_completed is False


async def test_get_content_returns_is_completed_false_when_progress_incomplete(
    db_session: AsyncSession,
) -> None:
    from app.models.progress import UserContentProgress
    from app.models.user import User

    topic = await _make_topic(db_session)
    content = Content(
        title="Intro",
        body="Body",
        content_type=ContentType.article,
        topic_id=topic.id,
    )
    db_session.add(content)
    user = User(cognito_sub="sub-1", email="a@example.com", first_name="A", last_name="B")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserContentProgress(user_id=user.id, content_id=content.id, progress_pct=40)
    )
    await db_session.commit()

    result = await content_service.get_content(db_session, content.id, user=user)

    assert result.is_completed is False


async def test_get_content_returns_is_completed_true_when_progress_100(
    db_session: AsyncSession,
) -> None:
    from app.models.progress import UserContentProgress
    from app.models.user import User

    topic = await _make_topic(db_session)
    content = Content(
        title="Intro",
        body="Body",
        content_type=ContentType.article,
        topic_id=topic.id,
    )
    db_session.add(content)
    user = User(cognito_sub="sub-1", email="a@example.com", first_name="A", last_name="B")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserContentProgress(user_id=user.id, content_id=content.id, progress_pct=100)
    )
    await db_session.commit()

    result = await content_service.get_content(db_session, content.id, user=user)

    assert result.is_completed is True


async def test_get_content_returns_is_completed_false_for_anonymous_user(
    db_session: AsyncSession,
) -> None:
    topic = await _make_topic(db_session)
    content = Content(
        title="Intro",
        body="Body",
        content_type=ContentType.article,
        topic_id=topic.id,
    )
    db_session.add(content)
    await db_session.commit()

    result = await content_service.get_content(db_session, content.id)

    assert result.is_completed is False
```

Check the `User` model's required constructor fields first — read `backend/app/models/user.py` if the fields used above (`cognito_sub`, `email`, `first_name`, `last_name`) don't match; adjust the test fixtures to whatever fields that model actually requires (mirror how `current_user` is constructed in `backend/tests/conftest.py`, which is the fixture already used by `test_snippet_service.py`'s `current_user` argument — prefer reusing that fixture over hand-building a `User` if it fits, i.e. add `current_user: User` as a fixture parameter to each new test instead of constructing `User(...)` manually).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && poetry run pytest tests/test_content_service.py -v -k is_completed`
Expected: FAIL with `TypeError: get_content() got an unexpected keyword argument 'user'` (or `AttributeError: 'ContentDetailResponse' object has no attribute 'is_completed'`)

- [ ] **Step 3: Add the field to the schema**

In `backend/app/schemas/content.py`, in `class ContentDetailResponse(ContentListResponse):`, add:

```python
    is_completed: bool = False
```

placed directly after the existing `is_saved: bool = False` line.

- [ ] **Step 4: Run tests to verify the schema change alone doesn't yet pass**

Run: `cd backend && poetry run pytest tests/test_content_service.py -v -k is_completed`
Expected: still FAIL (function doesn't accept `user` yet, and never sets `is_completed`) — confirms the test is actually exercising the new behaviour, not just a default.

- [ ] **Step 5: Commit the schema-only change is deferred to Task 2's commit** (schema and service change land together — do not commit yet)

---

### Task 2: Backend — compute `is_completed` in `content_service.get_content`

**Files:**
- Modify: `backend/app/services/content_service.py`
- Modify: `backend/app/routers/content.py`

- [ ] **Step 1: Update `content_service.get_content`**

In `backend/app/services/content_service.py`, add these imports at the top:

```python
from app.models.progress import UserContentProgress
from app.models.user import User
```

Change the function signature and body:

```python
async def get_content(
    db: AsyncSession, content_id: int, user: User | None = None
) -> ContentDetailResponse:
    """
    Return a single Content item including body (Markdown) and a fresh
    pre-signed S3 URL in the media_url field (generated via get_presigned_url).
    Raise HTTP 404 if not found.
    """
    result = await db.execute(
        select(Content)
        .options(selectinload(Content.content_tags).selectinload(ContentTag.tag))
        .where(Content.id == content_id)
    )
    content = result.scalar_one_or_none()
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")

    media_url = await get_presigned_url(content.media_url) if content.media_url else None

    is_completed = False
    if user is not None:
        progress_row = await db.get(UserContentProgress, (user.id, content_id))
        is_completed = progress_row is not None and progress_row.progress_pct == 100

    return ContentDetailResponse(
        id=content.id,
        title=content.title,
        content_type=content.content_type,
        topic_id=content.topic_id,
        t_level_id=content.t_level_id,
        tags=[TagResponse.model_validate(ct.tag) for ct in content.content_tags],
        created_at=content.created_at,
        body=content.body,
        media_url=media_url,
        is_completed=is_completed,
    )
```

This mirrors how `snippet_service.get_snippet` (`backend/app/services/snippet_service.py:46-49`) already computes `is_saved` from `UserSnippetSave`.

- [ ] **Step 2: Run the Task 1 tests to verify they now pass**

Run: `cd backend && poetry run pytest tests/test_content_service.py -v -k is_completed`
Expected: PASS (all 4 new tests)

- [ ] **Step 3: Run the full content_service test file to check nothing else broke**

Run: `cd backend && poetry run pytest tests/test_content_service.py -v`
Expected: PASS (all tests, including the pre-existing ones that call `get_content(db_session, content.id)` with no `user` arg — the new parameter has a default so those calls remain valid)

- [ ] **Step 4: Wire optional auth into the router**

In `backend/app/routers/content.py`, update the imports:

```python
from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.models.user import User
from app.schemas.content import ContentDetailResponse, ContentListResponse
from app.services import content_service
```

Update the `get_content` route:

```python
@router.get(
    "/{content_id}",
    response_model=ContentDetailResponse,
    summary="Get content item with body and media URL",
)
async def get_content(
    content_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ContentDetailResponse:
    return await content_service.get_content(db, content_id, current_user)
```

This matches the exact pattern already used in `backend/app/routers/snippets.py:13-19`. `get_current_user_optional` calls `get_current_user` as a plain function call (not a nested `Depends`), so it never 401s and does not appear in `route.dependant.dependencies` — it will not trip `test_no_content_route_depends_on_get_current_user` in `backend/tests/test_content.py`.

- [ ] **Step 5: Run the router guard test to confirm the route is still public**

Run: `cd backend && poetry run pytest tests/test_content.py -v`
Expected: PASS (both existing tests — the route still has no `get_current_user` dependency)

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && poetry run pytest -v`
Expected: PASS (no regressions elsewhere — in particular check `test_library_router.py` and anything that calls `/content/{id}` doesn't assume a fixed response shape that breaks with the new field)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/content.py backend/app/services/content_service.py backend/app/routers/content.py backend/tests/test_content_service.py
git commit -m "feat(backend): expose is_completed on GET /content/{id}"
```

---

### Task 3: Frontend — implement `updateProgress` in `progress.ts`

**Files:**
- Modify: `frontend/src/lib/api/progress.ts`
- Test: `frontend/src/lib/api/progress.test.ts` (create)

`getProgress()` stays a stub — nothing in this plan consumes it (it backs the
"continue reading" widget, which is a separate, not-yet-built feature). Only
`updateProgress` is needed for XP-on-read, so only it gets implemented here.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/api/progress.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/api/progress.test.ts`
Expected: FAIL with `Error: not implemented`

- [ ] **Step 3: Implement `updateProgress`**

In `frontend/src/lib/api/progress.ts`, keep `getProgress` exactly as-is and replace only the `updateProgress` stub:

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/api/progress.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/progress.ts frontend/src/lib/api/progress.test.ts
git commit -m "feat(frontend): implement updateProgress API client"
```

---

### Task 4: Frontend — add `is_completed` to the `ContentDetailResponse` type

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/content.test.ts`

- [ ] **Step 1: Update the type**

In `frontend/src/lib/api/types.ts`, find:

```ts
export interface ContentDetailResponse extends ContentListResponse {
  body: string | null;
  media_url: string | null;
}
```

Change to:

```ts
export interface ContentDetailResponse extends ContentListResponse {
  body: string | null;
  media_url: string | null;
  is_completed: boolean;
}
```

- [ ] **Step 2: Update the existing test fixture so it still type-checks**

In `frontend/src/lib/api/content.test.ts`, the `content` object (lines 11-21) is missing the new required field. Add `is_completed: false,` to that object literal.

- [ ] **Step 3: Run the content API tests and typecheck**

Run: `cd frontend && npx vitest run src/lib/api/content.test.ts && npx svelte-check --tsconfig ./tsconfig.json`
Expected: vitest PASS; svelte-check reports no new errors (existing unrelated errors, if any, are out of scope — only confirm no *new* errors reference `ContentDetailResponse` or `is_completed`)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/content.test.ts
git commit -m "feat(frontend): add is_completed to ContentDetailResponse type"
```

---

### Task 5: Frontend — "Mark as read" button on the Snippet reader

**Files:**
- Modify: `frontend/src/routes/learn/[id]/+page.svelte`

- [ ] **Step 1: Add state and the handler**

In `frontend/src/routes/learn/[id]/+page.svelte`, add to the imports:

```ts
  import Button from '$lib/components/Button.svelte';
  import { updateProgress } from '$lib/api/progress';
```

Add a reactive/local state variable near the other snippet state (after `let snippetError: string | null = null;`):

```ts
  let snippetRead = false;
  let markingRead = false;
  let markReadError: string | null = null;
```

In `loadSnippet`, after the successful `snippet = await getContent(id);` assignment, initialise the read state from the response:

```ts
      snippet = await getContent(id);
      snippetRead = snippet.is_completed;
      markReadError = null;
```

(Keep the existing `catch`/`finally` unchanged — just add these two lines right after the assignment inside the `try` block.)

Add the handler function near `toggleSnippetSave`:

```ts
  async function markSnippetRead() {
    if (!snippet || snippetRead) return;
    markingRead = true;
    markReadError = null;
    try {
      await updateProgress(snippet.id, 100);
      snippetRead = true;
    } catch {
      markReadError = "Couldn't save your progress — please try again.";
    } finally {
      markingRead = false;
    }
  }
```

- [ ] **Step 2: Add the button to the template**

In the snippet body section, after the `<p>{snippet.body}</p>` line, add (still inside the `{:else}` branch that renders a loaded snippet, gated to logged-in users the same way the save button is):

```svelte
        <p>{snippet.body}</p>
        {#if $currentUser}
          <div class="mark-read-row">
            <Button variant="primary" disabled={snippetRead || markingRead} on:click={markSnippetRead}>
              {snippetRead ? '✓ Read' : markingRead ? 'Saving…' : 'Mark as read (+10 XP)'}
            </Button>
            {#if markReadError}
              <span class="mark-read-error">{markReadError}</span>
            {/if}
          </div>
        {/if}
```

- [ ] **Step 3: Add styles**

In the `<style>` block, add:

```css
  .mark-read-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .mark-read-error {
    font-size: var(--font-size-body-secondary);
    color: #ef4444;
  }
```

Place these after the existing `.snippet-header h1` block (or any other logical spot alongside the other snippet-specific rules) — check the file's existing style ordering first and follow it rather than appending blindly to the end.

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx svelte-check --tsconfig ./tsconfig.json`
Expected: no new errors introduced by this file

- [ ] **Step 5: Manual verification in the browser**

Follow the project's `run` skill (or `docker compose up --build -d` per `CLAUDE.md` if not already running) to start the app. As a logged-in user:
1. Open an enrolled Album, navigate to an unread Snippet.
2. Confirm the "Mark as read (+10 XP)" button is visible and enabled.
3. Click it — button should change to "✓ Read" and become disabled; no page reload.
4. Reload the page — button should show "✓ Read" immediately (proves `is_completed` round-trips from the backend).
5. Go to `/` (home page) and confirm the "⭐ XP Earned" stat increased by 10 and "Albums Enrolled"/snippets-completed reflect the change (per the existing stats-row wiring in `+page.svelte`).
6. Mark every remaining unread Snippet in that Album as read, then reload the home page and confirm total XP jumped by an additional 50 (the Album-completion bonus), matching `XP_ALBUM_COMPLETION_BONUS` in `backend/app/services/gamification_service.py`.
7. As a logged-out visitor, open the same Snippet and confirm no "Mark as read" button appears (Snippets stay public/read-only for anonymous users, per `CLAUDE.md`'s "Snippets are public" constraint).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/learn/\[id\]/+page.svelte
git commit -m "feat(frontend): add mark-as-read button to Snippet reader"
```

---

### Task 6: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && poetry run pytest -v`
Expected: PASS

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS

- [ ] **Step 3: Run frontend lint/typecheck**

Run: `cd frontend && npx eslint . && npx svelte-check --tsconfig ./tsconfig.json`
Expected: no new errors/warnings introduced by this work

- [ ] **Step 4: Run backend lint**

Run: `cd backend && poetry run ruff check .`
Expected: no new errors introduced by this work

No commit for this task — it's a verification checkpoint only. If anything fails, fix it in the relevant earlier task's files and re-commit there (or as a small fixup commit referencing which task it belongs to).
