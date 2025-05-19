import { render } from '@testing-library/svelte';
import { screen, waitFor } from '@testing-library/dom';
import App from './App.svelte';
import { describe, test, expect } from 'vitest';
import { vi } from 'vitest'
import '@testing-library/jest-dom';
import { fireEvent } from '@testing-library/svelte';

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
  test('is comment section opened when clicked', async () => {
    //mocks fetch for articles and comments, waiting for necessary things to load(articles) before checking if button works  
    global.fetch = vi.fn((url) => {
      if (url === '/api/auth/userinfo') {
        return Promise.resolve({
          ok: false
        });
      }
      if (url === '/api/stories') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            response: {
              docs: [
                {
                  uri: 'test-article',
                  headline: { main: 'Test Headline' },
                  abstract: 'Test abstract',
                  multimedia: { default: { url: '/img.jpg' } }
                }
              ]
            }
          })
        });
      }
      if (url.includes('/api/articles/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      return Promise.reject(new Error('Unknown URL: ' + url));
    }) as any;

    const { container } = render(App);
    //waits for stories to load
    await screen.findByRole('heading', { name: 'Test Headline' });
    
    //find anf click comment button
    const commentBtn = container.querySelector('.comment-btn');
    await commentBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    //check if comment section is shown
    const commentsPanel = await screen.findByText('Comments');
    expect(commentsPanel).toBeInTheDocument();
  });
  test('loads comments for a article', async () => {
    global.fetch = vi.fn((url) => {
      if (url === '/api/auth/userinfo') {
        return Promise.resolve({ ok: false });
      }
      if (url === '/api/stories') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            response: {
              docs: [
                {
                  uri: 'test-article',
                  headline: { main: 'Test Headline' },
                  abstract: 'Test abstract',
                  multimedia: { default: { url: '/img.jpg' } }
                }
              ]
            }
          })
        });
      }
      if (url.includes('/api/articles/test-article/comments')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 'comment1',
              author: 'Test User',
              text: 'This is a test comment',
              created: new Date().toISOString()
            }
          ])
        });
      }
      return Promise.reject(new Error('Unknown URL: ' + url));
    }) as any;

    const { container } = render(App);
    
    await screen.findByRole('heading', { name: 'Test Headline' });
    
    const commentBtn = container.querySelector('.comment-btn');
    await commentBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    
    const commentText = await screen.findByText('This is a test comment');
    expect(commentText).toBeInTheDocument();
    
    const authorText = await screen.findByText('Test User');
    expect(authorText).toBeInTheDocument();
  });
//posts a new comment when authenticated
test('moderator can see delete buttons for comments', async () => {
  //mocks moderator
  const mockUser = { 
    email: 'moderator@example.com',
    groups: ['moderator']
  };
  
  global.fetch = vi.fn((url) => {
    if (url === '/api/auth/userinfo') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockUser)
      });
    }
    if (url === '/api/stories') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ 
          response: {
            docs: [
              {
                uri: 'test-article',
                headline: { main: 'Test Headline' },
                abstract: 'Test abstract',
                multimedia: { default: { url: '/img.jpg' } }
              }
            ]
          }
        })
      });
    }
    if (url.includes('/api/articles/test-article/comments')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([
          {
            id: 'comment1',
            author: 'Test User',
            text: 'This is a test comment',
            created: new Date().toISOString()
          }
        ])
      });
    }
    return Promise.reject(new Error('Unknown URL: ' + url));
  }) as any;

  const { container } = render(App);
  
  await screen.findByRole('heading', { name: 'Test Headline' });
  
  const commentBtn = container.querySelector('.comment-btn');
  await commentBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  
  //checks if delete button is visible
  const deleteBtn = await screen.findByLabelText('Delete comment');
  expect(deleteBtn).toBeInTheDocument();
  });
  test('non-moderator cannot see delete buttons for comments', async () => {
    //mocks authenticated user as non moderator
    const mockUser = { 
      email: 'user@example.com',
      groups: []
    };
    
    global.fetch = vi.fn((url) => {
      if (url === '/api/auth/userinfo') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockUser)
        });
      }
      if (url === '/api/stories') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            response: {
              docs: [
                {
                  uri: 'test-article',
                  headline: { main: 'Test Headline' },
                  abstract: 'Test abstract',
                  multimedia: { default: { url: '/img.jpg' } }
                }
              ]
            }
          })
        });
      }
      if (url.includes('/api/articles/test-article/comments')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 'comment1',
              author: 'Test User',
              text: 'This is a test comment',
              created: new Date().toISOString()
            }
          ])
        });
      }
      return Promise.reject(new Error('Unknown URL: ' + url));
    }) as any;

    const { container } = render(App);
    
    await screen.findByRole('heading', { name: 'Test Headline' });
    
    const commentBtn = container.querySelector('.comment-btn');
    await commentBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    
    //checks that the delete button is not visible
    await vi.waitFor(() => {
      expect(screen.queryByLabelText('Delete comment')).not.toBeInTheDocument();
    });
  });
  //moderator can delete comments
  test('moderator can delete comments', async () => {
    //mocks an authenticated user as moderator
    const mockUser = { 
      email: 'moderator@example.com',
      groups: ['moderator']
    };
    
    let deleteUrl = null;
    
    global.fetch = vi.fn((url, options) => {
      if (url === '/api/auth/userinfo') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockUser)
        });
      }
      if (url === '/api/stories') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            response: {
              docs: [
                {
                  uri: 'test-article',
                  headline: { main: 'Test Headline' },
                  abstract: 'Test abstract',
                  multimedia: { default: { url: '/img.jpg' } }
                }
              ]
            }
          })
        });
      }
      if (url.includes('/api/articles/test-article/comments') && !options?.method) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 'comment1',
              author: 'Test User',
              text: 'This is a test comment',
              created: new Date().toISOString()
            }
          ])
        });
      }
      if (url.includes('/api/articles/test-article/comments/') && options?.method === 'DELETE') {
        deleteUrl = url;
        return Promise.resolve({
          ok: true,
          text: () => Promise.resolve('')
        });
      }
      return Promise.reject(new Error('Unknown URL: ' + url));
    }) as any;

    const { container } = render(App);
    
    await screen.findByRole('heading', { name: 'Test Headline' });
    
    const commentBtn = container.querySelector('.comment-btn');
    await commentBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    
    //find and click the delete button
    const deleteBtn = await screen.findByLabelText('Delete comment');
    fireEvent.click(deleteBtn);
    
    //check if the delete request was made
    await vi.waitFor(() => {
      expect(deleteUrl).toBe('/api/articles/test-article/comments/comment1');
    });
  });

});
