import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import SupportPage from '../pages/SupportPage'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  )
}

/** Helper to get form inputs by their label text (since labels lack htmlFor) */
function getInputByLabel(container: HTMLElement, labelText: string): HTMLElement {
  const labels = container.querySelectorAll('label')
  for (const label of labels) {
    if (label.textContent?.trim() === labelText) {
      const parent = label.parentElement!
      const input = parent.querySelector('input, textarea, select')
      if (input) return input as HTMLElement
    }
  }
  throw new Error(`Could not find input for label "${labelText}"`)
}

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('SupportPage', () => {
  it('renders the support page with all sections', () => {
    renderWithProviders(<SupportPage />)

    expect(screen.getByText('Help & Support')).toBeInTheDocument()
    expect(screen.getByText("We're here to help. Choose a support option below.")).toBeInTheDocument()

    // Support channels
    expect(screen.getByText('Email Support')).toBeInTheDocument()
    expect(screen.getByText('Community')).toBeInTheDocument()
    expect(screen.getByText('Documentation')).toBeInTheDocument()

    // FAQ section
    expect(screen.getByText('Common Questions')).toBeInTheDocument()

    // Contact form
    expect(screen.getByText('Contact Us')).toBeInTheDocument()
  })

  it('renders the contact form with all fields', () => {
    const { container } = renderWithProviders(<SupportPage />)

    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Subject')).toBeInTheDocument()
    expect(screen.getByText('Category')).toBeInTheDocument()
    expect(screen.getByText('Priority')).toBeInTheDocument()
    expect(screen.getByText('Message')).toBeInTheDocument()

    // Verify the form inputs exist
    expect(getInputByLabel(container, 'Name')).toBeInTheDocument()
    expect(getInputByLabel(container, 'Email')).toBeInTheDocument()
    expect(getInputByLabel(container, 'Subject')).toBeInTheDocument()
    expect(getInputByLabel(container, 'Category')).toBeInTheDocument()
    expect(getInputByLabel(container, 'Priority')).toBeInTheDocument()
    expect(getInputByLabel(container, 'Message')).toBeInTheDocument()

    expect(screen.getByText('Send Message')).toBeInTheDocument()
  })

  it('submits ticket successfully and shows confirmation', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SupportPage />)

    await user.type(getInputByLabel(container, 'Name'), 'John Doe')
    await user.type(getInputByLabel(container, 'Email'), 'john@example.com')
    await user.type(getInputByLabel(container, 'Subject'), 'Test Subject')
    await user.type(getInputByLabel(container, 'Message'), 'This is a test message')

    await user.click(screen.getByText('Send Message'))

    await waitFor(() => {
      expect(screen.getByText('Message Sent')).toBeInTheDocument()
    })
    expect(screen.getByText("We'll get back to you within 24 hours.")).toBeInTheDocument()
    expect(screen.getByText('Ticket #: TKT-12345')).toBeInTheDocument()
  })

  it('shows error message when ticket submission fails', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('/api/support', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      })
    )

    const { container } = renderWithProviders(<SupportPage />)

    await user.type(getInputByLabel(container, 'Name'), 'John Doe')
    await user.type(getInputByLabel(container, 'Email'), 'john@example.com')
    await user.type(getInputByLabel(container, 'Subject'), 'Test Subject')
    await user.type(getInputByLabel(container, 'Message'), 'Test message')

    await user.click(screen.getByText('Send Message'))

    await waitFor(() => {
      expect(
        screen.getByText('Destek talebi gönderilemedi. Lütfen tekrar deneyin.')
      ).toBeInTheDocument()
    })
  })

  it('shows FAQ items', () => {
    renderWithProviders(<SupportPage />)

    expect(screen.getByText('How do I connect my GitHub account?')).toBeInTheDocument()
    expect(screen.getByText('My build failed. What should I do?')).toBeInTheDocument()
    expect(screen.getByText('How do I add App Store credentials?')).toBeInTheDocument()
    expect(screen.getByText('What is the difference between Free and Pro?')).toBeInTheDocument()
  })

  it('allows selecting category and priority', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SupportPage />)

    const categorySelect = getInputByLabel(container, 'Category') as HTMLSelectElement
    const prioritySelect = getInputByLabel(container, 'Priority') as HTMLSelectElement

    await user.selectOptions(categorySelect, 'bug')
    expect(categorySelect.value).toBe('bug')

    await user.selectOptions(prioritySelect, 'high')
    expect(prioritySelect.value).toBe('high')
  })

  it('shows SLA information at the bottom', () => {
    renderWithProviders(<SupportPage />)

    expect(screen.getByText(/Response times/)).toBeInTheDocument()
    expect(screen.getByText(/Free \(48h\)/)).toBeInTheDocument()
  })
})
