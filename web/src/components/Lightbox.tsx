import { useEffect, useRef, useState } from 'react'

export function Lightbox({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [zoomed, setZoomed] = useState(false)
  const [panning, setPanning] = useState(false)
  const origin = useRef({ x: 0, y: 0, left: 0, top: 0 })

  useEffect(() => {
    dialogRef.current?.showModal()
  }, [])

  // Centre the image when zooming to 1:1 so the pan starts from the middle
  // rather than the top-left corner.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !zoomed) return
    el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2
    el.scrollTop = (el.scrollHeight - el.clientHeight) / 2
  }, [zoomed])

  const onPointerDown = (e: React.PointerEvent) => {
    const el = scrollRef.current
    if (!zoomed || !el) return
    e.currentTarget.setPointerCapture(e.pointerId)
    origin.current = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop }
    setPanning(true)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const el = scrollRef.current
    if (!panning || !el) return
    el.scrollLeft = origin.current.left - (e.clientX - origin.current.x)
    el.scrollTop = origin.current.top - (e.clientY - origin.current.y)
  }

  const endPan = (e: React.PointerEvent) => {
    if (!panning) return
    e.currentTarget.releasePointerCapture(e.pointerId)
    setPanning(false)
  }

  return (
    <dialog
      className="cc-lightbox"
      ref={dialogRef}
      onCancel={(e) => { e.preventDefault(); onClose() }}
      onClick={(e) => { if (e.target === dialogRef.current) onClose() }}
    >
      <button className="cc-lightbox__close" type="button" onClick={onClose} aria-label="Close">×</button>
      <div className="cc-lightbox__scroll" ref={scrollRef} data-zoomed={zoomed ? 1 : 0} data-panning={panning ? 1 : 0}>
        <img
          src={src}
          alt={alt}
          draggable={false}
          onClick={() => { setZoomed((z) => !z) }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endPan}
          onPointerCancel={endPan}
        />
      </div>
    </dialog>
  )
}
