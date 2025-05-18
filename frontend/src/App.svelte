<script lang="ts">
  import { onMount } from 'svelte';
  import { user, type User } from './lib/user';
  import { get } from 'svelte/store';

  let currentUser: User | null = null;
  let showAccountPanel      = false;
  user.subscribe(u => currentUser = u);

  let stories: any[] = [];
  let currentDate: string = '';
  let commentsMap: Record<string, any[]> = {};
  let newComments: Record<string, string> = {};
  let activeSlug: string | null = null;

  // Date
  onMount(async() => {
    const options = {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    };
    const today = new Date();
    currentDate = today.toLocaleDateString('en-US', options);

    const res = await fetch('/api/auth/userinfo');
    if (res.ok) {
      user.set(await res.json());   // { email: '…' }
    }

    // stories
    try {
      const res  = await fetch('/api/stories');
      const data = await res.json();
      const docs = data.response?.docs || [];

      // only keep docs with an image and some text
      const withImageAndText = docs.filter(d =>
        !!d.multimedia?.default?.url &&
        (d.abstract || d.snippet || d.lead_paragraph)
      );
      stories = withImageAndText.slice(0, 6);

      for (const s of stories) {
        const slug = encodeURIComponent(s.uri);
        commentsMap[slug] = [];
        newComments[slug] = '';
        loadComments(slug);
      }
    } catch (e) {
      console.error('Failed to load stories:', e);
    }
  });

  async function loadComments(slug: string) {
    const res = await fetch(`/api/articles/${slug}/comments`);
    if (res.ok) commentsMap[slug] = await res.json();
  }

  async function postComment(slug: string) {
    const text = newComments[slug]?.trim();
    if (!text) return;
    const res = await fetch(`/api/articles/${slug}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (res.ok) {
      const c = await res.json();
      commentsMap[slug] = [...commentsMap[slug], c];
      newComments[slug] = '';
    } else {
      console.error('Failed to post:', await res.json());
    }
  }

  function openComments(slug: string) {
    activeSlug = slug;
    if (!commentsMap[slug]?.length) loadComments(slug);
  }
  function closeComments() {
    activeSlug = null;
  }

  function login() {
    const redirect = encodeURIComponent('http://localhost:5173/callback');
    window.location.href =
      `http://localhost:5556/auth?` +
      `client_id=flask-app&` +
      `redirect_uri=${redirect}&` + 
      `response_type=code&` +
      `scope=openid%20email%20profile`;
  }

  function logout() {
    // clear on backend
    fetch('/api/auth/logout', { method: 'POST' })
      .then(_ => {
        user.set(null);
        showAccountPanel = false;
      });
  }
</script>

<main>
  <header>
    <img src="/nyt-logo.png" alt="NYT Logo" class="logo" />
    <div class="date">
      <p>{currentDate}</p>
      <p>Today’s Paper</p>
    </div>
    {#if !currentUser}
      <button class="login-btn" on:click={login}>
        Log in
      </button>
    {:else}
      <button class="login-btn" on:click={() => showAccountPanel = true}>
        Account ⯆
      </button>
    {/if}
  </header>

<div class="grid-container">
  {#if stories.length === 0}
    <p>Loading…</p>
  {:else}
    {#each stories as s (s.uri)}
      <div class="story">
        {#if s.multimedia?.default?.url}
          <img src={s.multimedia.default.url} alt={s.headline.main} class="story-img" />
        {/if}
        <h1>{s.headline.main}</h1>
        <p>
          {#if s.abstract}{s.abstract}
          {:else if s.snippet}{s.snippet}
          {:else}{s.lead_paragraph}
          {/if}
        </p>

        <!-- COMMENT BUTTON -->
        <button
          class="comment-btn"
          on:click|stopPropagation={() => openComments(encodeURIComponent(s.uri))}
          aria-label="Show comments"
        >💬</button>
      </div>
    {/each}
  {/if}
</div>

  <footer>
    <p>2025 The New York Times</p>
  </footer>
  {#if activeSlug}
    <aside class="comments-panel">
      <button class="close" on:click={closeComments} aria-label="Close">✕</button>
      <h2>Comments</h2>

      {#if commentsMap[activeSlug]?.length === 0}
        <p><em>No comments yet.</em></p>
      {:else}
        <ul>
          {#each commentsMap[activeSlug] as c}
            <li>
              <strong>{c.author}</strong>
              <small>({new Date(c.created).toLocaleString()})</small>:
              {c.text}
            </li>
          {/each}
        </ul>
      {/if}

      <form on:submit|preventDefault={() => postComment(activeSlug!)}>
        <textarea
          bind:value={newComments[activeSlug!]}
          placeholder="Share your thoughts…"
          rows="4"
        ></textarea>
        <button type="submit" disabled={!newComments[activeSlug!]?.trim()}>
          Post
        </button>
      </form>
    </aside>
  {/if}

  {#if showAccountPanel}
    <aside class="account-panel">
      <button class="close" on:click={() => (showAccountPanel = false)}>✕</button>
      <p><strong>{currentUser?.email}</strong></p>
      <p>Good afternoon.</p>
      <button class="logout-btn" on:click={logout}>Log out</button>
    </aside>
  {/if}
</main>
