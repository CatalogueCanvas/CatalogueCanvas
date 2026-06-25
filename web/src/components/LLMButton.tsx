import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api/client'
import { ApiError } from '../api/client'
import { useActivity } from '../api/activity'

interface Props {
  itemId: string
  itemTitle?: string
  onResult: (result: api.DescribeResult) => void
}

export function LLMButton({ itemId, itemTitle, onResult }: Props) {
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState<api.AppSettings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { startTask, updateItem, finishTask } = useActivity()

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => {
      /* settings unavailable */
    })
  }, [])

  const run = async () => {
    if (!settings) return
    setBusy(true)
    setError('')
    const label = itemTitle || itemId
    const taskId = startTask({
      kind: 'describe',
      title: 'Describing 1 item',
      origin: `/items/${itemId}`,
      items: [{ label, status: 'uploading' }],
    })
    try {
      const result = await api.describeItem(itemId, {
        api_url: settings.llm_api_url,
        model: settings.llm_model,
        item_type: settings.llm_item_type,
        summary_focus: settings.llm_summary_focus,
        bullet_count: Number(settings.llm_bullet_count) || 3,
        bullet_max_words: Number(settings.llm_bullet_max_words) || 50,
        prompt_template: settings.llm_prompt_template,
        api_key: apiKey || undefined,
      })
      updateItem(taskId, label, { status: 'done' })
      finishTask(taskId, 'done')
      onResult(result)
      setOpen(false)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message.includes('Connection refused')
            ? `LLM server unreachable at ${settings.llm_api_url} — check Settings`
            : err.message
          : 'request failed'
      setError(message)
      updateItem(taskId, label, { status: 'error', detail: message })
      finishTask(taskId, 'error')
    } finally {
      setBusy(false)
      // Never persist the key beyond this component's lifetime.
      setApiKey('')
    }
  }

  if (!open) {
    return (
      <button className="cc-btn" onClick={() => { setOpen(true) }} type="button">
        Generate description (LLM)
      </button>
    )
  }

  return (
    <div className="cc-llm">
      <div className="cc-field">
        <label className="cc-label" htmlFor="llm-api-key">API key (optional, never stored)</label>
        <input id="llm-api-key" className="cc-input" type="password" value={apiKey} onChange={(e) => { setApiKey(e.target.value) }} />
      </div>
      <div className="cc-row-tight">
        <button className="cc-btn cc-btn--primary" onClick={() => void run()} disabled={busy || !settings} type="button">
          {busy ? 'Generating...' : 'Generate'}
        </button>
        <button className="cc-btn" onClick={() => { setOpen(false) }} type="button">Cancel</button>
      </div>
      {error && (
        <div className="error-text">
          {error} {error.includes('check Settings') && <Link to="/settings">Open Settings</Link>}
        </div>
      )}
    </div>
  )
}
