import { useEffect, useRef } from 'react'

export function Lightbox({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialogRef.current?.showModal()
  }, [])

  return (
    <dialog
      className="cc-lightbox"
      ref={dialogRef}
      onCancel={(e) => { e.preventDefault(); onClose() }}
      onClick={(e) => { if (e.target === dialogRef.current) onClose() }}
    >
      <button className="cc-lightbox__close" type="button" onClick={onClose} aria-label="Close">×</button>
      <div className="cc-lightbox__scroll">
        <img src={src} alt={alt} draggable={false} onClick={onClose} />
      </div>
    </dialog>
  )
}
