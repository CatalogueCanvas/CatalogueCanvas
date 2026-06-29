import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ActivityTray } from './ActivityTray'
import type { ActivityTask } from '../api/activity'

const mockRemoveTask = vi.fn()
const mockClearFinished = vi.fn()
let mockTasks: ActivityTask[] = []

vi.mock('../api/activity', () => ({
  useActivity: () => ({
    tasks: mockTasks,
    removeTask: mockRemoveTask,
    clearFinished: mockClearFinished,
  }),
}))

vi.mock('./Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

afterEach(() => {
  vi.clearAllMocks()
  mockTasks = []
})

function makeTask(over: Partial<ActivityTask> = {}): ActivityTask {
  return {
    id: 'task-1',
    kind: 'upload',
    title: 'Upload batch',
    origin: '/',
    status: 'done',
    items: [{ label: 'file.zip', status: 'done' }],
    startedAt: 0,
    ...over,
  }
}

function renderTray() {
  return render(<MemoryRouter><ActivityTray /></MemoryRouter>)
}

describe('ActivityTray', () => {
  it('renders nothing when there are no tasks', () => {
    const { container } = renderTray()
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a running pill when tasks are active', () => {
    mockTasks = [makeTask({ status: 'running' })]
    renderTray()
    expect(screen.getByText('1 running…')).toBeInTheDocument()
  })

  it('shows "Done" pill when all tasks are finished', () => {
    mockTasks = [makeTask({ status: 'done' })]
    renderTray()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('dismiss button calls removeTask', async () => {
    mockTasks = [makeTask()]
    renderTray()
    await userEvent.click(screen.getByLabelText('Dismiss'))
    expect(mockRemoveTask).toHaveBeenCalledWith('task-1')
  })

  it('shows clear finished button and calls clearFinished', async () => {
    mockTasks = [makeTask()]
    renderTray()
    await userEvent.click(screen.getByText('Clear finished'))
    expect(mockClearFinished).toHaveBeenCalled()
  })

  it('collapses and expands the panel', async () => {
    mockTasks = [makeTask()]
    renderTray()
    expect(screen.getByText('Activity')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { expanded: true }))
    expect(screen.queryByText('Activity')).not.toBeInTheDocument()
  })
})
