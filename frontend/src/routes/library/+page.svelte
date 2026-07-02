<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import type { PageData } from './$types';
  import PageCard from '$lib/components/PageCard.svelte';
  import AlbumCard from '$lib/components/AlbumCard.svelte';
  import SnippetCard from '$lib/components/SnippetCard.svelte';
  import AgentChatWindow from '$lib/components/AgentChatWindow.svelte';
  import Button from '$lib/components/Button.svelte';
  import NavLink from '$lib/components/NavLink.svelte';
  import { createChatSession, getChatSession, sendChatMessage } from '$lib/api/chat';
  import type { ChatSessionSummary, ChatSessionDetail } from '$lib/api/chat';
  import { saveSnippet, unsaveSnippet } from '$lib/api/library';
  import { currentUser } from '$lib/stores/user';
  import { enrolledAlbumIds } from '$lib/stores/enrolments';
  import { savedSnippetIds } from '$lib/stores/savedSnippets';

  export let data: PageData;

  let sessions: ChatSessionSummary[] = data.sessions;
  let activeSession: ChatSessionDetail | null = data.activeSession;
  let streamingText: string | undefined = undefined;
  let isStreaming = false;
  let chatError: string | null = null;

  savedSnippetIds.set(new Set(data.library.saved_snippets.map((s) => s.id)));
  enrolledAlbumIds.set(new Set(data.library.enrolled_albums.map((a) => a.id)));

  $: displayedEnrolledAlbums = data.library.enrolled_albums.filter((a) =>
    $enrolledAlbumIds.has(a.id)
  );
  $: displayedSavedSnippets = data.library.saved_snippets.filter((s) => $savedSnippetIds.has(s.id));

  async function selectSession(sessionId: number) {
    chatError = null;
    try {
      activeSession = await getChatSession(sessionId);
      goto(`/library?session=${sessionId}`, { keepFocus: true, noScroll: true });
    } catch (err) {
      chatError = "Couldn't load that chat — please try again.";
      console.error(err);
    }
  }

  async function handleNewChat() {
    chatError = null;
    try {
      const session = await createChatSession();
      sessions = [
        { id: session.id, title: session.title, updated_at: session.updated_at },
        ...sessions,
      ];
      activeSession = { id: session.id, title: session.title, messages: [] };
      goto(`/library?session=${session.id}`, { keepFocus: true, noScroll: true });
    } catch (err) {
      chatError = "Couldn't start a new chat — please try again.";
      console.error(err);
    }
  }

  async function handleSend(text: string) {
    if (!activeSession) return;
    const sessionId = activeSession.id;
    chatError = null;
    isStreaming = true;
    streamingText = '';
    try {
      await sendChatMessage(sessionId, text, (delta) => {
        streamingText = (streamingText ?? '') + delta;
      });
      activeSession = await getChatSession(sessionId);
      sessions = sessions
        .map((s) =>
          s.id === sessionId
            ? { ...s, title: activeSession!.title, updated_at: new Date().toISOString() }
            : s
        )
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
    } catch (err) {
      chatError = "Couldn't send that message — please try again.";
      console.error(err);
    } finally {
      isStreaming = false;
      streamingText = undefined;
    }
  }

  async function toggleSave(contentId: number, currentlySaved: boolean) {
    if (currentlySaved) {
      savedSnippetIds.update((s) => {
        s.delete(contentId);
        return new Set(s);
      });
      await unsaveSnippet(contentId);
    } else {
      savedSnippetIds.update((s) => {
        s.add(contentId);
        return new Set(s);
      });
      await saveSnippet(contentId);
    }
  }

  onMount(() => {
    if (data.draft && activeSession) {
      const draftText = data.draft;
      goto(`/library?session=${activeSession.id}`, {
        replaceState: true,
        keepFocus: true,
        noScroll: true,
      });
      handleSend(draftText);
    }
  });
</script>

<div class="library-layout">
  <PageCard as="aside" width="var(--left-rail-width)" padding="1rem" overflowY="auto">
    <Button variant="cta" on:click={handleNewChat}>+ New chat</Button>
    {#if sessions.length === 0}
      <p class="empty">No chats yet — ask the Mentor something to start one.</p>
    {:else}
      <ul class="session-list">
        {#each sessions as session (session.id)}
          <li>
            <NavLink
              href={`/library?session=${session.id}`}
              label={session.title}
              active={activeSession?.id === session.id}
              muted={activeSession?.id !== session.id}
              on:click={(e) => {
                e.preventDefault();
                selectSession(session.id);
              }}
            />
          </li>
        {/each}
      </ul>
    {/if}
  </PageCard>

  <PageCard as="main" padding="1rem 1.5rem">
    {#if chatError}
      <p class="chat-error" role="alert">{chatError}</p>
    {/if}
    {#if activeSession}
      <AgentChatWindow
        messages={activeSession.messages}
        onSend={handleSend}
        userDisplayName={$currentUser?.first_name || $currentUser?.username || 'You'}
        {streamingText}
        {isStreaming}
      />
    {:else}
      <p class="empty">Start a new chat to talk to the Dynamic Mentor.</p>
    {/if}
  </PageCard>

  <div class="right-stack">
    <PageCard padding="1rem 1.25rem" overflowY="auto">
      <span class="section-label">Enrolled Albums</span>
      {#if displayedEnrolledAlbums.length === 0}
        <p class="empty">No albums enrolled yet — browse Albums to get started.</p>
      {:else}
        <div class="album-grid">
          {#each displayedEnrolledAlbums as album (album.id)}
            <AlbumCard {album} />
          {/each}
        </div>
      {/if}
    </PageCard>

    <PageCard padding="1rem 1.25rem" overflowY="auto">
      <span class="section-label">Saved Snippets</span>
      {#if displayedSavedSnippets.length === 0}
        <p class="empty">No saved snippets yet — save one while browsing to see it here.</p>
      {:else}
        <div class="snippet-list">
          {#each displayedSavedSnippets as snippet (snippet.id)}
            <SnippetCard
              content={snippet}
              saved={$savedSnippetIds.has(snippet.id)}
              onSaveToggle={() => toggleSave(snippet.id, $savedSnippetIds.has(snippet.id))}
            />
          {/each}
        </div>
      {/if}
    </PageCard>
  </div>
</div>

<style>
  /* The right-hand stack's width is derived so it can't drift from its own
     content: 2 AlbumCards at AlbumGrid's max track width (220px, see
     AlbumGrid.svelte's minmax(190px, 220px)) + one --gap-inner between them
     + a 3rem buffer. The right-stack PageCards use less padding than 3rem
     (padding="1rem 1.25rem") — the 3rem figure is a deliberate slack margin,
     not a literal padding sum, to leave room for scrollbars/content overflow.

     The left rail only holds a list of chat-session nav links, so it gets
     its own much narrower width budget instead of reusing the right
     stack's — reusing it starved the middle chat column on narrower
     viewports (e.g. ~1280px CSS px, as seen at 1080p with 150% Windows
     display scaling). minmax-via-clamp lets it shrink first under pressure
     while the chat column (flex: 1 1 auto) keeps size priority. */
  .library-layout {
    --right-rail-width: calc(2 * 220px + var(--gap-inner) + 3rem);
    --left-rail-width: clamp(160px, 16vw, 200px);
    display: flex;
    gap: var(--gap-inner);
    height: 100%;
  }

  .library-layout > :global(aside.page-card) {
    flex: 1 1 var(--left-rail-width);
    min-width: 160px;
    max-width: 200px;
  }

  .library-layout > :global(main.page-card) {
    flex: 3 1 auto;
    min-width: 0;
  }

  .right-stack {
    flex: 0 0 var(--right-rail-width);
    display: flex;
    flex-direction: column;
    gap: var(--gap-inner);
  }

  .right-stack :global(.page-card) {
    flex: 1 1 0;
    min-height: 0;
  }

  .library-layout :global(aside.page-card > button.cta) {
    width: 100%;
  }

  .session-list {
    list-style: none;
    margin: 0.75rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .session-list li {
    padding: 0.35rem 0.6rem;
  }

  /* overflow/ellipsis must live on the inner .label span, not on the <a>
     itself — NavLink's active/hover underline is an ::after pseudo-element
     positioned at bottom: -0.3em (outside the anchor's own box), so
     overflow: hidden on the <a> clips the underline away entirely. */
  .session-list :global(a) {
    display: block;
    width: 100%;
    font-size: 0.825rem;
  }

  .session-list :global(a .label) {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .section-label {
    display: block;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a6472;
    font-family: 'Ubuntu', sans-serif;
    margin-bottom: 0.75rem;
  }

  .album-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--gap-inner);
  }

  .snippet-list {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.6rem;
  }

  .empty {
    color: #5a6472;
    font-size: 0.875rem;
    margin: 0;
    font-family: 'Ubuntu', sans-serif;
  }

  .chat-error {
    font-size: 0.8rem;
    color: #b3261e;
    margin: 0 0 0.75rem;
    font-family: 'Ubuntu', sans-serif;
  }
</style>
