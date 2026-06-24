import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { ActivityProvider, useActivity } from './activity'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <ActivityProvider>{children}</ActivityProvider>
)

describe('useActivity', () => {
  it('throws outside the provider', () => {
    expect(() => renderHook(() => useActivity())).toThrow(/within ActivityProvider/)
  })

  it('starts a task and tracks it as running', () => {
    const { result } = renderHook(() => useActivity(), { wrapper })
    let id = ''
    act(() => { id = result.current.startTask({ kind: 'upload', title: 'Upload', origin: 'test' }) })
    expect(result.current.tasks).toHaveLength(1)
    expect(result.current.tasks[0].status).toBe('running')
    expect(id).toMatch(/^task-/)
  })

  it('adds and updates items', () => {
    const { result } = renderHook(() => useActivity(), { wrapper })
    let id = ''
    act(() => { id = result.current.startTask({ kind: 'upload', title: 'U', origin: 'o' }) })
    act(() => { result.current.addItems(id, [{ label: 'a.png', status: 'pending' }]); })
    expect(result.current.tasks[0].items).toHaveLength(1)
    act(() => { result.current.updateItem(id, 'a.png', { status: 'done', detail: 'ok' }); })
    expect(result.current.tasks[0].items[0]).toMatchObject({ status: 'done', detail: 'ok' })
  })

  it('renames and finishes a task', () => {
    const { result } = renderHook(() => useActivity(), { wrapper })
    let id = ''
    act(() => { id = result.current.startTask({ kind: 'describe', title: 'Old', origin: 'o' }) })
    act(() => { result.current.setTaskTitle(id, 'New'); })
    expect(result.current.tasks[0].title).toBe('New')
    act(() => { result.current.finishTask(id, 'done'); })
    expect(result.current.tasks[0].status).toBe('done')
  })

  it('removes a task and clears finished ones', () => {
    const { result } = renderHook(() => useActivity(), { wrapper })
    let running = ''
    act(() => {
      running = result.current.startTask({ kind: 'upload', title: 'R', origin: 'o' })
      const done = result.current.startTask({ kind: 'upload', title: 'D', origin: 'o' })
      result.current.finishTask(done, 'done')
    })
    expect(result.current.tasks).toHaveLength(2)
    act(() => { result.current.clearFinished(); })
    expect(result.current.tasks).toHaveLength(1)
    act(() => { result.current.removeTask(running); })
    expect(result.current.tasks).toHaveLength(0)
  })
})
