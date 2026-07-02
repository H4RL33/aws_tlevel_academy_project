<!--
  NavSidebar
  Purpose: Thin adapter over Sidebar for scroll-navigation sidebars (e.g. /learn, /t-levels/[slug]).
    Accepts a flat list of anchor links and an activeHref updated by IntersectionObserver.
  Used in: /learn, /t-levels/[slug]
  Props:
    - links ({ label: string; href: string }[]): ordered list of anchor/page links
    - activeHref (string): href of the currently-visible section
-->
<script lang="ts">
  import Sidebar from '$lib/components/Sidebar.svelte';
  import type { SidebarSection } from '$lib/components/Sidebar.svelte';

  export let links: { label: string; href: string }[] = [];
  export let activeHref: string = '';

  $: sections = [{ links }] satisfies SidebarSection[];
</script>

<!--
  padding="0.875rem 1rem": NavSidebar's sections never have a `title`, so Sidebar never
  renders a SideHeader — the sidebar-nav's first link sits directly on the PageCard's own
  top padding with no extra compensating margin. Both /learn and /t-levels/[slug] pair this
  sidebar with a first right-hand panel that is the small section-heading PageCard
  (padding="0.875rem 1.25rem", see those routes' +page.svelte), not a `main` with the
  2rem-padding default that Sidebar's own 1.5rem default is tuned for. Matching that
  0.875rem top padding here keeps the sidebar card's top edge flush with the heading
  card's top edge instead of sitting visibly lower.
-->
<Sidebar {sections} {activeHref} padding="0.875rem 1rem" ariaLabel="Section navigation" />
