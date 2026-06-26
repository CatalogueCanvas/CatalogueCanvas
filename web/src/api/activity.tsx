// Context provider component and its hook intentionally live together.
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, type ReactNode } from 'react'

export type TaskStatus = 'running' | 'done' | 'error'
// Item statuses reuse the existing cc-upload-queue__item--<status> styles.
export type ItemStatus = 'pending' | 'uploading' | 'done' | 'skipped' | 'error'

export interface ActivityItem {
  label: string
  status: ItemStatus
  detail?: string
}

export interface ActivityTask {
  id: string
  kind: 'upload' | 'describe'
  title: string
  origin: string
  status: TaskStatus
  items: ActivityItem[]
  startedAt: number
  cancel?: () => void
}

interface StartTaskInput {
  kind: ActivityTask['kind']
  title: string
  origin: string
  items?: ActivityItem[]
  cancel?: () => void
}

interface ActivityContextValue {
  tasks: ActivityTask[]
  startTask: (input: StartTaskInput) => string
  addItems: (taskId: string, items: ActivityItem[]) => void
  updateItem: (taskId: string, label: string, fields: Partial<ActivityItem>) => void
  setTaskTitle: (taskId: string, title: string) => void
  finishTask: (taskId: string, status: TaskStatus) => void
  removeTask: (taskId: string) => void
  clearFinished: () => void
}

const ActivityContext = createContext<ActivityContextValue | null>(null)

let taskCounter = 0
const nextId = () => `task-${Date.now()}-${taskCounter++}`

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<ActivityTask[]>([])

  const startTask = (input: StartTaskInput): string => {
    const id = nextId()
    setTasks((prev) => [
      ...prev,
      {
        id,
        kind: input.kind,
        title: input.title,
        origin: input.origin,
        status: 'running',
        items: input.items ?? [],
        startedAt: Date.now(),
        cancel: input.cancel,
      },
    ])
    return id
  }

  const addItems = (taskId: string, items: ActivityItem[]) => {
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, items: [...t.items, ...items] } : t)))
  }

  const updateItem = (taskId: string, label: string, fields: Partial<ActivityItem>) => {
    setTasks((prev) =>
      prev.map((t) =>
        t.id === taskId
          ? { ...t, items: t.items.map((it) => (it.label === label ? { ...it, ...fields } : it)) }
          : t,
      ),
    )
  }

  const setTaskTitle = (taskId: string, title: string) => {
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, title } : t)))
  }

  const finishTask = (taskId: string, status: TaskStatus) => {
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status, cancel: undefined } : t)))
  }

  const removeTask = (taskId: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId))
  }

  const clearFinished = () => {
    setTasks((prev) => prev.filter((t) => t.status === 'running'))
  }

  return (
    <ActivityContext.Provider
      value={{ tasks, startTask, addItems, updateItem, setTaskTitle, finishTask, removeTask, clearFinished }}
    >
      {children}
    </ActivityContext.Provider>
  )
}

export function useActivity() {
  const ctx = useContext(ActivityContext)
  if (!ctx) throw new Error('useActivity must be used within ActivityProvider')
  return ctx
}
