import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import * as api from '../api/client'
import type { Item, PublicPortfolio } from '../api/client'
import './deck.css'

const CAPABILITIES = [
  'Archival Systems', 'Type Specimens', 'Reference Libraries',
  'Editorial Design', 'Cataloguing', 'Open Data', 'Wayfinding',
]

export function Deck() {
  const { slug, token } = useParams<{ slug: string; token?: string }>()
  const [portfolio, setPortfolio] = useState<PublicPortfolio | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hover, setHover] = useState<Item | null>(null)
  const followRef = useRef<HTMLDivElement>(null)

  const style = portfolio?.style || 'ledger'
  const layout = portfolio?.layout || 'slide'
  const kinetic = style === 'kinetic'

  useEffect(() => {
    if (!slug) return
    api.getPublicPortfolio(slug, token)
      .then(setPortfolio)
      .catch(() => { setError('Portfolio not found.') })
  }, [slug, token])

  // Cursor-following thumbnail tracks the pointer (kinetic deck only).
  useEffect(() => {
    if (!kinetic) return
    const el = followRef.current
    const onMove = (e: MouseEvent) => {
      if (el) { el.style.left = `${e.clientX}px`; el.style.top = `${e.clientY}px` }
    }
    window.addEventListener('mousemove', onMove)
    return () => { window.removeEventListener('mousemove', onMove) }
  }, [kinetic])

  if (error) return <div className="cc-deck"><section className="cc-deck__sec"><div className="cc-empty"><p className="cc-empty__title">{error}</p></div></section></div>
  if (!portfolio) return <div className="cc-deck"><section className="cc-deck__sec" /></div>

  const items = portfolio.items
  const total = items.length

  const INDEX_PER_PAGE = 8
  const indexPages: typeof items[] = []
  for (let i = 0; i < items.length; i += INDEX_PER_PAGE) {
    indexPages.push(items.slice(i, i + INDEX_PER_PAGE))
  }

  return (
    <div className="cc-deck" data-portfolio-style={style} data-portfolio-layout={layout}>
      {layout === 'slide' && (
        <button className="cc-btn cc-deck__printbtn no-print" onClick={() => { window.print() }} type="button">
          Print / Export PDF
        </button>
      )}
      <section className="cc-deck__sec cc-deck__cover">
        <p className="cc-deck__kicker">Portfolio · {total} works</p>
        <h1 className="cc-deck__title">{portfolio.title}</h1>
        {portfolio.description && <div className="cc-deck__desc"><ReactMarkdown>{portfolio.description}</ReactMarkdown></div>}
        <div className="cc-deck__cover-foot">
          <span>CatalogueCanvas</span>
          <span>/p/{portfolio.slug}</span>
        </div>
      </section>

      {kinetic && (
        <section className="cc-deck__sec cc-deck__marquee" aria-hidden="true">
          <div className="cc-deck__marquee-track">
            {[0, 1].map((set) => (
              <span key={set}>
                {CAPABILITIES.map((c) => (
                  <span key={c}>{c}<i>/</i></span>
                ))}
              </span>
            ))}
          </div>
        </section>
      )}

      {kinetic ? (
        <section className="cc-deck__sec">
          <div className="cc-deck__indexhead">
            <h2>Selected</h2>
            <span className="cc-mono">{String(total).padStart(2, '0')} works</span>
          </div>
          <div className="cc-deck__kindex" onMouseLeave={() => { setHover(null) }}>
            {items.map((item, i) => (
              <a className="cc-deck__krow" href={`#work-${item.id}`} key={item.id} onMouseEnter={() => { setHover(item) }}>
                <span className="cc-deck__krow-num">{String(i + 1).padStart(2, '0')}</span>
                <span className="cc-deck__krow-title">{item.title}</span>
                <span className="cc-deck__krow-meta cc-mono">{item.tags[0] || ''}</span>
              </a>
            ))}
          </div>
        </section>
      ) : (
        indexPages.map((page, pageIndex) => (
          <section className="cc-deck__sec cc-deck__index" key={`index-${pageIndex}`}>
            <div className="cc-deck__indexhead">
              <h2>{pageIndex === 0 ? 'Works' : 'Works (cont.)'}</h2>
              <span className="cc-mono">{portfolio.slug}</span>
            </div>
            <div className="cc-deck__indexgrid">
              {page.map((item, i) => (
                <div className="cc-deck__idxitem" key={item.id}>
                  <span className="cc-deck__idxnum">{String(pageIndex * INDEX_PER_PAGE + i + 1).padStart(2, '0')}</span>
                  <div className="cc-thumb">
                    {item.preview_url
                      ? <img src={item.preview_url} alt={item.title} />
                      : <span className="cc-thumb__label">no preview</span>}
                  </div>
                  <div className="cc-deck__idxtitle">{item.title}</div>
                </div>
              ))}
            </div>
          </section>
        ))
      )}

      {items.map((item, i) => {
        const isWide = !!(item.width && item.height && item.width > item.height)
        return (
          <section id={`work-${item.id}`} className={`cc-deck__sec cc-deck__art ${i % 2 === 1 ? 'cc-deck__art--rev' : ''} ${isWide ? 'cc-deck__art--wide' : ''}`} key={item.id}>
            <div className="cc-deck__plate">
              {item.preview_url
                ? <img src={item.preview_url} alt={item.title} />
                : <span>no preview</span>}
            </div>
            <div className="cc-deck__caption">
              <p className="cc-deck__kicker">Work {String(i + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</p>
              <h3>{item.title}</h3>
              <span className="cc-mono">{item.id}</span>
              {item.note && <p>{item.note}</p>}
              {item.tags.length > 0 && (
                <div className="cc-deck__tags">
                  {item.tags.map((tag) => <span className="cc-tag" key={tag}>{tag}</span>)}
                </div>
              )}
            </div>
          </section>
        )
      })}

      <section className="cc-deck__sec cc-deck__colo">
        <div>
          <h2>About this work</h2>
          {portfolio.description && <ReactMarkdown>{portfolio.description}</ReactMarkdown>}
          <p>A portfolio of {total} works shared via CatalogueCanvas.</p>
        </div>
        <ul className="cc-deck__worklist">
          {items.map((item, i) => (
            <li key={item.id}>
              <span className="cc-mono">{String(i + 1).padStart(2, '0')}</span>
              <span>{item.title}</span>
            </li>
          ))}
        </ul>
      </section>

      {kinetic && (
        <div className="cc-deck__follow no-print" ref={followRef} data-on={hover ? 1 : 0} aria-hidden="true">
          <div className="cc-deck__plate cc-deck__followplate">
            {hover?.preview_url
              ? <img src={hover.preview_url} alt="" />
              : <span>{hover ? hover.id : ''}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
