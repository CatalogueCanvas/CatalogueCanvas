import { useRef, useState, type DragEvent } from 'react'
import { uploadItem, ApiError } from '../api/client'

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
        const res = await uploadItem(file)
        if (res.created) {
          updateEntry(file.name, { status: 'done', detail: `→ ${res.item?.id}` })
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
