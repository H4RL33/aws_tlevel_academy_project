<!--
  ChatSessionMenu
  Purpose: Wraps a single chat-session row in the Library left rail's
    session-list, adding rename/delete actions via a right-click context
    menu, following the same dropdown visual/interaction pattern as
    NavBarAvatar's dropdown (white background, box-shadow, radius 0, closes
    on outside click/Escape).
  Used in: routes/library/+page.svelte, inside each <li> of .session-list.
  Props:
    - session (ChatSessionSummary): the session this row represents
    - href (string): link target, forwarded to the inner NavLink
    - active / muted (boolean): forwarded to the inner NavLink
    - onSelect (() => void): called when the row (NavLink) itself is clicked
    - onRenamed ((session: ChatSessionSummary) => void): called after a
      successful rename, with the updated session
    - onDeleted ((sessionId: number) => void): called after a successful delete
  Behaviour:
    - Right-click (or the "..." icon button, shown on hover/focus for
      keyboard/touch users who can't right-click) opens a dropdown with
      "Rename" and "Delete".
    - "Rename" swaps the row into an inline text input; Enter/blur saves,
      Escape cancels.
    - "Delete" asks for confirmation via the native confirm() dialog, then
      calls onDeleted.
    - The dropdown closes on outside click or Escape.
-->
<script lang="ts">
  import { tick } from 'svelte';
  import NavLink from '$lib/components/NavLink.svelte';
  import { renameChatSession, deleteChatSession } from '$lib/api/chat';
  import type { ChatSessionSummary } from '$lib/api/chat';

  export let session: ChatSessionSummary;
  export let href: string;
  export let active = false;
  export let muted = false;
  export let onSelect: () => void;
  export let onRenamed: (session: ChatSessionSummary) => void;
  export let onDeleted: (sessionId: number) => void;

  let containerEl: HTMLDivElement;
  let inputEl: HTMLInputElement;

  let menuOpen = false;
  let editing = false;
  let editValue = session.title;
  let menuError: string | null = null;

  function openMenu() {
    menuError = null;
    menuOpen = true;
  }

  function closeMenu() {
    menuOpen = false;
  }

  function handleContextMenu(event: MouseEvent) {
    event.preventDefault();
    openMenu();
  }

  function handleTriggerClick(event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    menuOpen ? closeMenu() : openMenu();
  }

  function handleWindowClick(event: MouseEvent) {
    if (menuOpen && containerEl && !containerEl.contains(event.target as Node)) {
      closeMenu();
    }
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key !== 'Escape') return;
    if (editing) {
      cancelRename();
    } else if (menuOpen) {
      closeMenu();
    }
  }

  async function startRename() {
    closeMenu();
    editValue = session.title;
    editing = true;
    await tick();
    inputEl?.focus();
    inputEl?.select();
  }

  function cancelRename() {
    editing = false;
    menuError = null;
  }

  async function saveRename() {
    const title = editValue.trim();
    if (!title || title === session.title) {
      editing = false;
      return;
    }
    try {
      const updated = await renameChatSession(session.id, title);
      editing = false;
      onRenamed(updated);
    } catch (err) {
      menuError = "Couldn't rename that chat — please try again.";
      console.error(err);
    }
  }

  function handleInputKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      saveRename();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      cancelRename();
    }
  }

  async function handleDelete() {
    closeMenu();
    // Simplest confirmation step consistent with the app's existing
    // error-handling style — no bespoke confirm-dialog component exists yet
    // for this kind of destructive-but-low-stakes action.
    if (!confirm(`Delete "${session.title}"? This can't be undone.`)) {
      return;
    }
    try {
      await deleteChatSession(session.id);
      onDeleted(session.id);
    } catch (err) {
      menuError = "Couldn't delete that chat — please try again.";
      console.error(err);
    }
  }
</script>

<svelte:window on:click={handleWindowClick} on:keydown={handleWindowKeydown} />

<div
  class="session-row"
  role="group"
  aria-label={session.title}
  bind:this={containerEl}
  on:contextmenu={handleContextMenu}
>
  {#if editing}
    <input
      bind:this={inputEl}
      class="rename-input"
      type="text"
      maxlength="60"
      bind:value={editValue}
      on:keydown={handleInputKeydown}
      on:blur={saveRename}
      aria-label="Rename chat session"
    />
  {:else}
    <NavLink
      {href}
      label={session.title}
      {active}
      {muted}
      on:click={(e) => {
        e.preventDefault();
        onSelect();
      }}
    />
    <button
      class="menu-trigger"
      type="button"
      aria-label="Chat session options"
      aria-haspopup="true"
      aria-expanded={menuOpen}
      on:click={handleTriggerClick}
    >
      &#8943;
    </button>
  {/if}

  {#if menuOpen}
    <div class="dropdown">
      <button class="dropdown-item" type="button" on:click={startRename}>Rename</button>
      <button class="dropdown-item delete" type="button" on:click={handleDelete}>Delete</button>
    </div>
  {/if}

  {#if menuError}
    <p class="menu-error" role="alert">{menuError}</p>
  {/if}
</div>

<style>
  .session-row {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .session-row :global(a) {
    flex: 1 1 auto;
    min-width: 0;
  }

  .menu-trigger {
    flex: 0 0 auto;
    background: none;
    border: none;
    cursor: pointer;
    padding: 0 0.25rem;
    line-height: 1;
    font-size: 1rem;
    color: #5a6472;
    opacity: 0;
    /* Shown on hover/focus-within so keyboard users tabbing through the
       session list (not just mouse users who can right-click) can discover
       and reach it — right-click alone isn't keyboard accessible. */
    transition: opacity 0.15s ease-in-out;
  }

  .session-row:hover .menu-trigger,
  .session-row:focus-within .menu-trigger {
    opacity: 1;
  }

  .menu-trigger:focus-visible {
    opacity: 1;
    outline: 2px solid #232f3e;
    outline-offset: 1px;
  }

  .rename-input {
    flex: 1 1 auto;
    min-width: 0;
    font-family: 'Ubuntu', sans-serif;
    font-size: 0.825rem;
    color: #232f3e;
    border: 1px solid #232f3e;
    border-radius: 0;
    padding: 0.15rem 0.35rem;
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 0.25rem);
    right: 0;
    min-width: 140px;
    background: #ffffff;
    border-radius: 0;
    box-shadow: 0 10px 18px -4px rgba(35, 47, 62, 0.35);
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0;
    z-index: 10;
  }

  .dropdown-item {
    background: none;
    border: none;
    cursor: pointer;
    width: 100%;
    text-align: left;
    color: #232f3e;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-family: 'Ubuntu', sans-serif;
  }

  .dropdown-item:hover {
    text-decoration: underline;
  }

  .dropdown-item.delete {
    color: #b3261e;
  }

  .menu-error {
    position: absolute;
    top: 100%;
    left: 0;
    font-size: 0.7rem;
    color: #b3261e;
    margin: 0.2rem 0 0;
    font-family: 'Ubuntu', sans-serif;
    white-space: normal;
  }
</style>
