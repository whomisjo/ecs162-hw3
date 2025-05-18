// src/lib/user.ts
import { writable } from 'svelte/store';

export interface User { email: string; }

// will hold either `null` or the logged-in user
export const user = writable<User | null>(null);