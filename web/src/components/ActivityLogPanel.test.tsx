import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ActivityLogPanel } from './ActivityLogPanel'
import type { ActivityEntry } from '../api/client'

vi.mock('../api/client', () => ({
  listActivity: vi.fn(),
  exportActivityCsv: vi.fn(),
  deleteActivityLog: vi.fn(),
  ApiError: class extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  },
  DELETE_ACTIVITY_CONFIRM: 'delete activity log',
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function entry(over: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    at: '2026-08-05T10:11:02+00:00',
    actor: 'admin',
    role: 'admin',
    action: 'item.upload',
    target: 'summary-916',
    detail: { created: true },
    ...over,
  }
}

describe('ActivityLogPanel', () => {
  it('shows an empty state when nothing is logged', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [], enabled: true, path: '/data/logs/audit.log' })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('No activity recorded yet.')).toBeInTheDocument())
  })

  it('renders entries in a table', async () => {
    mocked.listActivity.mockResolvedValue({
      entries: [entry(), entry({ action: 'item.delete', target: 'abc-1', detail: {} })],
      enabled: true,
      path: '/data/logs/audit.log',
    })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('item.upload')).toBeInTheDocument())
    expect(screen.getByText('summary-916')).toBeInTheDocument()
    expect(screen.getByText('item.delete')).toBeInTheDocument()
    expect(screen.getByText('created=true')).toBeInTheDocument()
  })

  it('notes when logging is disabled', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [], enabled: false, path: '/data/logs/audit.log' })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText(/Logging is currently disabled/)).toBeInTheDocument())
  })

  it('downloads the CSV', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [entry()], enabled: true, path: '/p' })
    mocked.exportActivityCsv.mockResolvedValue(undefined)
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('item.upload')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Download log (CSV)' }))
    expect(mocked.exportActivityCsv).toHaveBeenCalled()
  })

  it('disables delete when there is nothing to clear', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [], enabled: true, path: '/p' })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Delete log' })).toBeDisabled())
  })

  it('requires the exact phrase before deleting', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [entry()], enabled: true, path: '/p' })
    mocked.deleteActivityLog.mockResolvedValue({ ok: true })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('item.upload')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Delete log' }))
    const confirmButton = screen.getByRole('button', { name: 'Delete the log' })
    expect(confirmButton).toBeDisabled()

    await userEvent.type(screen.getByPlaceholderText('delete activity log'), 'wrong phrase')
    expect(confirmButton).toBeDisabled()
    expect(mocked.deleteActivityLog).not.toHaveBeenCalled()
  })

  it('deletes once the phrase matches', async () => {
    mocked.listActivity.mockResolvedValue({ entries: [entry()], enabled: true, path: '/p' })
    mocked.deleteActivityLog.mockResolvedValue({ ok: true })
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('item.upload')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Delete log' }))
    await userEvent.type(screen.getByPlaceholderText('delete activity log'), 'delete activity log')
    await userEvent.click(screen.getByRole('button', { name: 'Delete the log' }))

    await waitFor(() => expect(mocked.deleteActivityLog).toHaveBeenCalledWith('delete activity log'))
  })

  it('surfaces a load failure', async () => {
    mocked.listActivity.mockRejectedValue(new api.ApiError(500, 'boom'))
    render(<ActivityLogPanel />)
    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument())
  })
})
