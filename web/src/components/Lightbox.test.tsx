import { beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Lightbox } from './Lightbox'

// jsdom does not implement <dialog>.showModal(), which the component calls.
// Stub it here rather than in the shared setup — no other component needs it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  })
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open')
  })
})

function renderLightbox(onClose = vi.fn()) {
  const utils = render(<Lightbox src="/preview.webp" alt="Work One" onClose={onClose} />)
  const dialog = utils.container.querySelector('dialog') as HTMLDialogElement
  const img = screen.getByAltText('Work One')
  return { ...utils, onClose, dialog, img }
}

describe('Lightbox', () => {
  it('opens as a modal on mount', () => {
    const { dialog } = renderLightbox()
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled()
    expect(dialog).toHaveAttribute('open')
  })

  it('closes via the close button', async () => {
    const { onClose } = renderLightbox()
    await userEvent.click(screen.getByLabelText('Close'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes on Escape and prevents the browser default', () => {
    const { dialog, onClose } = renderLightbox()
    const cancel = new Event('cancel', { cancelable: true, bubbles: false })
    fireEvent(dialog, cancel)
    expect(onClose).toHaveBeenCalledOnce()
    expect(cancel.defaultPrevented).toBe(true)
  })

  it('closes when the backdrop is clicked', () => {
    const { dialog, onClose } = renderLightbox()
    fireEvent.click(dialog)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes when the image is clicked', async () => {
    const { img, onClose } = renderLightbox()
    await userEvent.click(img)
    expect(onClose).toHaveBeenCalledOnce()
  })
})
