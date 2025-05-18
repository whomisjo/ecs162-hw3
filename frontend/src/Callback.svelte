<script lang="ts">
  import { onMount } from 'svelte';
  import { user } from './lib/user';
  import { goto } from '@sveltejs/kit'; // or just use `window.location`

  onMount(async () => {
    const params = new URLSearchParams(window.location.search);
    const code   = params.get('code');
    if (!code) {
      return goto('/'); // no code → go home
    }

    // Exchange code for token & userinfo
    const res = await fetch(`/api/auth/callback?code=${code}`);
    if (res.ok) {
      const u = await res.json();    // { email: "user@example.com" }
      user.set(u);
      // clear URL
      window.history.replaceState({}, '', '/');
      goto('/');
    } else {
      console.error('Auth failed:', await res.text());
      goto('/');
    }
  });
</script>

<p>Logging in…</p>