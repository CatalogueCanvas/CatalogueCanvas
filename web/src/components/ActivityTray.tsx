import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useActivity, type ActivityTask } from '../api/activity'
import { Icon } from './Icon'

function taskSummary(task: ActivityTask): string {
  const done = task.items.filter((i) => i.status === 'done' || i.status === 'skipped').length
  const failed = task.items.filter((i) => i.status === 'error').length
  const total = task.items.length
  if (task.status === 'running') return `${done}/${total}`
  if (failed > 0) return `${done}/${total} · ${failed} failed`
  return `${done}/${total}`
}

export function ActivityTray() {
  const { tasks, removeTask, clearFinished } = useActivity()
  const [expanded, setExpanded] = useState(true)

  if (tasks.length === 0) return null

  const running = tasks.filter((t) => t.status === 'running').length
  const hasFinished = tasks.some((t) => t.status !== 'running')
  const pillLabel = running > 0 ? `${running} running…` : 'Done'

  return (
    <div className={`cc-activity-tray${expanded ? ' cc-activity-tray--open' : ''}`}>
      <button
        className="cc-activity-tray__pill"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
      >
        <span className={`cc-activity-tray__dot${running > 0 ? ' cc-activity-tray__dot--busy' : ''}`} />
        <span className="cc-activity-tray__pill-label">{pillLabel}</span>
        <Icon name="chevronDown" size={14} className={expanded ? 'cc-activity-tray__chev--open' : ''} />
      </button>

      {expanded && (
        <div className="cc-activity-tray__panel">
          <div className="cc-activity-tray__panel-head">
            <span>Activity</span>
            {hasFinished && (
              <button className="cc-activity-tray__clear" onClick={clearFinished} type="button">
                Clear finished
              </button>
            )}
          </div>
          <ul className="cc-activity-tray__tasks">
            {tasks.map((task) => (
              <li key={task.id} className={`cc-activity-tray__task cc-activity-tray__task--${task.status}`}>
                <div className="cc-activity-tray__task-head">
                  <Link className="cc-activity-tray__task-title" to={task.origin}>
                    {task.title}
                  </Link>
                  <span className="cc-activity-tray__task-summary">{taskSummary(task)}</span>
                  {task.status === 'running' && task.cancel && (
                    <button className="cc-activity-tray__cancel" onClick={task.cancel} type="button">
                      Cancel
                    </button>
                  )}
                  {task.status !== 'running' && (
                    <button
                      className="cc-activity-tray__dismiss"
                      onClick={() => removeTask(task.id)}
                      type="button"
                      aria-label="Dismiss"
                    >
                      ×
                    </button>
                  )}
                </div>
                <ul className="cc-upload-queue cc-activity-tray__items">
                  {task.items.map((item) => (
                    <li
                      key={item.label}
                      className={`cc-upload-queue__item cc-upload-queue__item--${item.status}`}
                    >
                      <span className="cc-upload-queue__status" />
                      <span className="cc-upload-queue__name">{item.label}</span>
                      {item.detail && <span className="cc-upload-queue__detail">{item.detail}</span>}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
