import { useEffect, useRef, useState, type DragEvent } from 'react'
import { listLibraries, uploadItem, ApiError } from '../api/client'
import type { Library } from '../api/client'

type FileStatus = 'pending' | 'uploading' | 'done' | 'skipped' | 'error'

interface FileEntry {
  name: string
  status: FileStatus
  detail?: string
}

export function Uploader({ onUploaded }: { onUploaded: () => void }) {
  const [dragOver, setDragOver] = useState(false)
  const [queue, setQueue] = useState<FileEntry[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const [libraries, setLibraries] = useState<Library[]>([])
  const [libraryId, setLibraryId] = useState('')

  useEffect(() => {
    listLibraries().then((libs) => {
      setLibraries(libs)
      const def = libs.find((l) => l.is_default)
      if (def) setLibraryId(def.id)
    }).catch(() => {})
  }, [])

  const updateEntry = (name: string, fields: Partial<FileEntry>) => {
    setQueue((prev) => prev.map((e) => (e.name === name ? { ...e, ...fields } : e)))
  }

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const zipFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.zip'))
    if (zipFiles.length === 0) return

    setQueue((prev) => [...prev, ...zipFiles.map((f) => ({ name: f.name, status: 'pending' as FileStatus }))])

    for (const file of zipFiles) {
      updateEntry(file.name, { status: 'uploading' })
      try {
        const res = await uploadItem(file, libraryId || undefined)
        if (res.created) {
          const detail = res.note ? `→ ${res.item?.id} (${res.note})` : `→ ${res.item?.id}`
          updateEntry(file.name, { status: 'done', detail })
        } else {
          updateEntry(file.name, { status: 'skipped', detail: res.note ?? undefined })
        }
      } catch (err) {
        updateEntry(file.name, { status: 'error', detail: err instanceof ApiError ? err.message : 'upload failed' })
      }
    }
    onUploaded()
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div>
      {libraries.length > 1 && (
        <div className="cc-row-tight" style={{ marginBottom: 'var(--space-3)' }}>
          <label className="cc-label" htmlFor="upload-library">Library</label>
          <select id="upload-library" className="cc-input" value={libraryId} onChange={(e) => setLibraryId(e.target.value)}>
            {libraries.map((lib) => (
              <option key={lib.id} value={lib.id}>{lib.name}</option>
            ))}
          </select>
        </div>
      )}
      <div
        className={`cc-dropzone${dragOver ? ' cc-dropzone--over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <span className="cc-dropzone__icon" />
        <input
          ref={inputRef}
          type="file"
          accept=".zip"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        Drop ZIP files here or click to upload
      </div>
      {queue.length > 0 && (
        <ul className="cc-upload-queue">
          {queue.map((entry) => (
            <li key={entry.name} className={`cc-upload-queue__item cc-upload-queue__item--${entry.status}`}>
              <span className="cc-upload-queue__status" />
              <span className="cc-upload-queue__name">{entry.name}</span>
              {entry.detail && <span className="cc-upload-queue__detail">{entry.detail}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
