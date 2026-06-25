import { createContext, useContext, useState, type ReactNode } from 'react'

interface SelectionContextValue {
  batchMode: boolean
  toggleBatchMode: () => void
  selected: Set<string>
  toggleSelect: (id: string) => void
  selectAll: (ids: string[]) => void
  clear: () => void
}

const SelectionContext = createContext<SelectionContextValue | null>(null)

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [batchMode, setBatchMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const toggleBatchMode = () => {
    setBatchMode((prev) => {
      if (prev) setSelected(new Set())
      return !prev
    })
  }

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = (ids: string[]) => { setSelected(new Set(ids)) }
  const clear = () => { setSelected(new Set()) }

  return (
    <SelectionContext.Provider value={{ batchMode, toggleBatchMode, selected, toggleSelect, selectAll, clear }}>
      {children}
    </SelectionContext.Provider>
  )
}

export function useSelection() {
  const ctx = useContext(SelectionContext)
  if (!ctx) throw new Error('useSelection must be used within SelectionProvider')
  return ctx
}
