<script lang="ts">
  import { onMount } from 'svelte';

  onMount(() => {
    const search = window.location.search; 
    const code = new URLSearchParams(search).get('code');
    if (!code) {
      window.location.href = '/';
      return;
    }
    // Sends code AND state to Flask in one go, cookies intact
    window.location.href = `/api/auth/callback${search}`;
  });
</script>

<p>Logging you in…</p>
