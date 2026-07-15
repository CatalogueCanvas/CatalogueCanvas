import { beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Lightbox } from './Lightbox'

// jsdom implements neither <dialog>.showModal() nor pointer capture, both of
// which the component calls. Stub them here rather than in the shared setup —
// no other component needs them.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  })
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open')
  })
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
})

function renderLightbox(onClose = vi.fn()) {
  const utils = render(<Lightbox src="/preview.webp" alt="Work One" onClose={onClose} />)
  const dialog = utils.container.querySelector('dialog') as HTMLDialogElement
  const scroll = utils.container.querySelector('.cc-lightbox__scroll') as HTMLDivElement
  const img = screen.getByAltText('Work One')
  return { ...utils, onClose, dialog, scroll, img }
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

  it('does not close when the image itself is clicked', async () => {
    const { img, onClose } = renderLightbox()
    await userEvent.click(img)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('toggles between fit and 1:1 zoom when the image is clicked', async () => {
    const { img, scroll } = renderLightbox()
    expect(scroll).toHaveAttribute('data-zoomed', '0')

    await userEvent.click(img)
    expect(scroll).toHaveAttribute('data-zoomed', '1')

    await userEvent.click(img)
    expect(scroll).toHaveAttribute('data-zoomed', '0')
  })

  it('centres the image when zooming in', async () => {
    const { img, scroll } = renderLightbox()
    // jsdom reports 0 for layout metrics, so define them to assert real centring.
    Object.defineProperty(scroll, 'scrollWidth', { value: 1000, configurable: true })
    Object.defineProperty(scroll, 'clientWidth', { value: 400, configurable: true })
    Object.defineProperty(scroll, 'scrollHeight', { value: 800, configurable: true })
    Object.defineProperty(scroll, 'clientHeight', { value: 200, configurable: true })

    await userEvent.click(img)

    expect(scroll.scrollLeft).toBe(300)
    expect(scroll.scrollTop).toBe(300)
  })

  it('pans by dragging while zoomed', async () => {
    const { img, scroll } = renderLightbox()
    await userEvent.click(img)
    scroll.scrollLeft = 100
    scroll.scrollTop = 100

    fireEvent.pointerDown(img, { pointerId: 1, clientX: 50, clientY: 50 })
    expect(scroll).toHaveAttribute('data-panning', '1')

    // Dragging left/up scrolls the content the opposite way.
    fireEvent.pointerMove(img, { pointerId: 1, clientX: 30, clientY: 35 })
    expect(scroll.scrollLeft).toBe(120)
    expect(scroll.scrollTop).toBe(115)

    fireEvent.pointerUp(img, { pointerId: 1 })
    expect(scroll).toHaveAttribute('data-panning', '0')
  })

  it('ignores pointer drags while not zoomed', () => {
    const { img, scroll } = renderLightbox()
    scroll.scrollLeft = 0

    fireEvent.pointerDown(img, { pointerId: 1, clientX: 50, clientY: 50 })
    expect(scroll).toHaveAttribute('data-panning', '0')

    fireEvent.pointerMove(img, { pointerId: 1, clientX: 10, clientY: 10 })
    expect(scroll.scrollLeft).toBe(0)
  })

  it('stops panning when the pointer is cancelled', async () => {
    const { img, scroll } = renderLightbox()
    await userEvent.click(img)

    fireEvent.pointerDown(img, { pointerId: 1, clientX: 50, clientY: 50 })
    expect(scroll).toHaveAttribute('data-panning', '1')

    fireEvent.pointerCancel(img, { pointerId: 1 })
    expect(scroll).toHaveAttribute('data-panning', '0')
  })
})
