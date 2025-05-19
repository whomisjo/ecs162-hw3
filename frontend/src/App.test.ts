import { render } from '@testing-library/svelte';
import { screen, waitFor } from '@testing-library/dom';
import App from './App.svelte';
import { describe, test, expect } from 'vitest';
import { vi } from 'vitest'
import '@testing-library/jest-dom';

describe('App.svelte', () => {
  // searches for loading, if true, passes
  test('renders heading', () => {
    render(App);
    const loading = screen.getByText('Loading…')
    expect(loading).toBeTruthy();
  }),
  test('date', async () => {
    //looks for all dates matching today's date, used to fail with getByText(found multiple dates & failed)
    render(App);
    const options = {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    };
    const today = new Date().toLocaleDateString('en-US', options);
    const date = await screen.findAllByText(today);
    expect(date).toBeTruthy();
  }),
  test('NYT API', async() => {
    //creates a mockup of NYT API from app.svelte, then test
    //findByRole for headline and img, since they have roles, while abstract does not
    global.fetch = vi.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve({ 
          response: {
              docs: [
                {
                  headline: { main: 'Test Headline' },
                  abstract: 'Test abstract',
                  multimedia: { default: { url: '/img.jpg' } }
                }
              ]
            }
          })
      })
    ) as unknown as typeof fetch;
    
  
    render(App);
    const heading = await screen.findByRole('heading', { name: 'Test Headline' });
    expect(heading).toBeTruthy();
    const abstract = await screen.findByText('Test abstract');
    expect(abstract).toBeTruthy();
    const multimedia = await screen.findByRole('img', { name: 'Test Headline' });
    expect(multimedia).toBeTruthy();
  });
  test('sends a request to /api/stories', async () => {
    //creates a mock up and spies on window.fetch to catch our backend call
    const fetchSpy = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ response: { docs: [] } })
    }) as any;
    global.fetch = fetchSpy;
  
    render(App);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
  
    expect(fetchSpy).toHaveBeenCalledWith('/api/stories');
    ///////////////////////////////
  });
  test('shows login when not logged in', async () => {
    //mocks not logged in user and looks for login button by its role to verify
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({})  // no user
    });
    render(App);
    const loginButton = await screen.findByRole('button', { name: /log in/i });
    expect(loginButton).toBeInTheDocument();
  });
  test('shows user email and logout when logged in', async () => {
  //mocks logged in user, checking if there is logout button and the email is shown
  global.fetch = vi.fn((url) => {
    if (url === '/api/auth/userinfo') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ email: 'user@example.com' })
      });
    }

    //mocks creating stories
    if (url === '/api/stories') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ response: { docs: [] } })
      });
    }

    return Promise.reject(new Error('Unknown URL: ' + url));
  }) as any;

  render(App);
  });
});
