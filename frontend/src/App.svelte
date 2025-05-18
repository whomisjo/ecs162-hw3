<script lang="ts">
  import { onMount } from 'svelte';

  let stories: any[] = [];
  let currentDate: string = '';
  
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
    } catch (e) {
      console.error('Failed to load stories:', e);
    }
  });
</script>

<main>
  <header>
    <img src="/nyt-logo.png" alt="NYT Logo" class="logo" />
    <div class="date">
      <p>{currentDate}</p>
      <p>Today’s Paper</p>
    </div>
  </header>

  <div class="grid-container">
    {#if stories.length === 0}
      <p>Loading…</p>
    {:else}
      {#each stories as s, i}
        <div class="story story{ i+1 }">
          {#if s.multimedia?.default?.url}
            <img
              src={s.multimedia.default.url}
              alt={s.headline.main}
              class="story-img"
            />
          {/if}

          <h1>{s.headline.main}</h1>

          {#if s.abstract}
            <p>{s.abstract}</p>
          {:else if s.snippet}
            <p>{s.snippet}</p>
          {:else}
            <p>{s.lead_paragraph}</p>
          {/if}
        </div>
      {/each}
    {/if}
  </div>

  <footer>
    <p>2025 The New York Times</p>
  </footer>

</main>


