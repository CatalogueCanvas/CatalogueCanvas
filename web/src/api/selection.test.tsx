import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { SelectionProvider, useSelection } from './selection'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SelectionProvider>{children}</SelectionProvider>
)

describe('useSelection', () => {
  it('throws when used outside the provider', () => {
    expect(() => renderHook(() => useSelection())).toThrow(/within SelectionProvider/)
  })

  it('toggles batch mode and clears selection when leaving it', () => {
    const { result } = renderHook(() => useSelection(), { wrapper })
    expect(result.current.batchMode).toBe(false)

    act(() => result.current.toggleBatchMode())
    expect(result.current.batchMode).toBe(true)

    act(() => result.current.toggleSelect('a'))
    expect(result.current.selected.has('a')).toBe(true)

    act(() => result.current.toggleBatchMode())
    expect(result.current.batchMode).toBe(false)
    expect(result.current.selected.size).toBe(0)
  })

  it('toggleSelect adds and removes ids', () => {
    const { result } = renderHook(() => useSelection(), { wrapper })
    act(() => result.current.toggleSelect('x'))
    act(() => result.current.toggleSelect('y'))
    expect([...result.current.selected].sort()).toEqual(['x', 'y'])
    act(() => result.current.toggleSelect('x'))
    expect([...result.current.selected]).toEqual(['y'])
  })

  it('selectAll and clear replace the set', () => {
    const { result } = renderHook(() => useSelection(), { wrapper })
    act(() => result.current.selectAll(['a', 'b', 'c']))
    expect(result.current.selected.size).toBe(3)
    act(() => result.current.clear())
    expect(result.current.selected.size).toBe(0)
  })
})
