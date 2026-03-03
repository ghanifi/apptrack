import { http, HttpResponse } from 'msw'

export const handlers = [
  // Auth
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string }
    if (body.email === 'test@example.com' && body.password === 'password123') {
      return HttpResponse.json({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
      })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
  }),

  http.post('/api/auth/refresh', async ({ request }) => {
    const body = (await request.json()) as { refresh_token: string }
    if (body.refresh_token === 'valid-refresh-token') {
      return HttpResponse.json({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
      })
    }
    return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 })
  }),

  // Projects
  http.get('/api/projects', () => {
    return HttpResponse.json([
      {
        id: '1',
        name: 'test-app',
        framework: 'react_native',
        status: 'ready',
        repo_url: 'https://github.com/test/app',
        branch: 'main',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-06-01T00:00:00Z',
        owner_id: '1',
        builds: [],
      },
    ])
  }),

  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name: string; repo_url: string; branch: string }
    return HttpResponse.json({
      id: 'new-project-1',
      name: body.name,
      repo_url: body.repo_url,
      branch: body.branch,
      framework: 'react-native',
      status: 'analyzing',
      created_at: '2025-06-01T00:00:00Z',
      updated_at: '2025-06-01T00:00:00Z',
      owner_id: '1',
      builds: [],
    })
  }),

  // Builds
  http.get('/api/builds', () => {
    return HttpResponse.json({
      items: [
        {
          id: 'build-1',
          project_id: '1',
          platform: 'android',
          provider: 'eas',
          status: 'success',
          started_at: '2025-06-01T00:00:00Z',
          completed_at: '2025-06-01T00:05:00Z',
        },
      ],
    })
  }),

  http.post('/api/projects/:projectId/build', () => {
    return HttpResponse.json({
      id: 'build-2',
      status: 'queued',
      platform: 'android',
      provider: 'eas',
    })
  }),

  // GitHub
  http.get('/api/github/profile', () => {
    return HttpResponse.json({
      github_connected: true,
      github_username: 'testuser',
    })
  }),

  http.get('/api/github/repos', () => {
    return HttpResponse.json([
      {
        id: 1,
        name: 'my-app',
        full_name: 'testuser/my-app',
        clone_url: 'https://github.com/testuser/my-app.git',
        default_branch: 'main',
        private: false,
        language: 'TypeScript',
        description: 'A test application',
      },
      {
        id: 2,
        name: 'another-app',
        full_name: 'testuser/another-app',
        clone_url: 'https://github.com/testuser/another-app.git',
        default_branch: 'main',
        private: true,
        language: 'JavaScript',
        description: null,
      },
    ])
  }),

  // Credentials
  http.get('/api/credentials', () => {
    return HttpResponse.json([])
  }),

  http.put('/api/credentials', () => {
    return HttpResponse.json({ ok: true })
  }),

  // Deployments
  http.post('/api/deployments/:buildId/deploy', () => {
    return HttpResponse.json({ id: 'deploy-1', status: 'pending' })
  }),

  // Support
  http.post('/api/support', async ({ request }) => {
    const body = (await request.json()) as { subject: string }
    if (body.subject === 'fail-test') {
      return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
    }
    return HttpResponse.json({ ticket_id: 'TKT-12345' })
  }),
]
