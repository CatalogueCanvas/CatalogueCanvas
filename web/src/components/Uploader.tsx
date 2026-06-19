import { useEffect, useRef, useState, type DragEvent } from 'react'
import { listLibraries, uploadItem, ApiError } from '../api/client'
import type { Library } from '../api/client'
import { useActivity } from '../api/activity'

export function Uploader({ onUploaded }: { onUploaded: () => void }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [libraries, setLibraries] = useState<Library[]>([])
  const [libraryId, setLibraryId] = useState('')
  const { startTask, updateItem, finishTask } = useActivity()

  useEffect(() => {
    listLibraries().then((libs) => {
      setLibraries(libs)
      const def = libs.find((l) => l.is_default)
      if (def) setLibraryId(def.id)
    }).catch(() => {})
  }, [])

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const zipFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.zip'))
    if (zipFiles.length === 0) return

    const taskId = startTask({
      kind: 'upload',
      title: `Uploading ${zipFiles.length} ZIP${zipFiles.length === 1 ? '' : 's'}`,
      origin: '/upload',
      items: zipFiles.map((f) => ({ label: f.name, status: 'pending' as const })),
    })

    let failed = false
    for (const file of zipFiles) {
      updateItem(taskId, file.name, { status: 'uploading' })
      try {
        const res = await uploadItem(file, libraryId || undefined)
        if (res.created) {
          const detail = res.note ? `→ ${res.item?.id} (${res.note})` : `→ ${res.item?.id}`
          updateItem(taskId, file.name, { status: 'done', detail })
        } else {
          updateItem(taskId, file.name, { status: 'skipped', detail: res.note ?? undefined })
        }
      } catch (err) {
        failed = true
        updateItem(taskId, file.name, { status: 'error', detail: err instanceof ApiError ? err.message : 'upload failed' })
      }
    }
    finishTask(taskId, failed ? 'error' : 'done')
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
    </div>
  )
}
