import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import * as api from '../api/client'
import type { Item } from '../api/client'

export function NotesPanel({ item, onSaved, readOnly = false }: { item: Item; onSaved: (item: Item) => void; readOnly?: boolean }) {
  const [editing, setEditing] = useState(false)
  const [note, setNote] = useState(item.note)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const updated = await api.updateItem(item.id, { note })
      onSaved(updated)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const cancel = () => {
    setNote(item.note)
    setEditing(false)
  }

  return (
    <div className="cc-panel cc-notes">
      <div className="cc-notes__head">
        <h2 className="cc-h2">Notes</h2>
        {readOnly ? null : editing ? (
          <div className="cc-row-tight">
            <button className="cc-btn" type="button" onClick={cancel} disabled={saving}>Cancel</button>
            <button className="cc-btn cc-btn--primary" type="button" onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        ) : (
          <button className="cc-btn cc-btn--sm" type="button" onClick={() => { setEditing(true) }}>Edit</button>
        )}
      </div>
      {editing ? (
        <textarea
          className="cc-textarea cc-textarea--mono"
          rows={10}
          value={note}
          onChange={(e) => { setNote(e.target.value) }}
        />
      ) : item.note ? (
        <div className="cc-notes__rendered">
          <ReactMarkdown>{item.note}</ReactMarkdown>
        </div>
      ) : (
        <p className="cc-hint">No notes yet.</p>
      )}
    </div>
  )
}
