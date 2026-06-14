import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import * as api from '../api/client'
import type { PublicPortfolio } from '../api/client'
import './deck.css'

export function Deck() {
  const { slug } = useParams<{ slug: string }>()
  const [portfolio, setPortfolio] = useState<PublicPortfolio | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) return
    api.getPublicPortfolio(slug)
      .then(setPortfolio)
      .catch(() => setError('Portfolio not found.'))
  }, [slug])

  if (error) return <div className="cc-deck"><section className="cc-deck__sec"><div className="cc-empty"><p className="cc-empty__title">{error}</p></div></section></div>
  if (!portfolio) return <div className="cc-deck"><section className="cc-deck__sec" /></div>

  const items = portfolio.items
  const total = items.length

  return (
    <div className="cc-deck">
      <section className="cc-deck__sec cc-deck__cover">
        <p className="cc-deck__kicker">Portfolio · {total} works</p>
        <h1 className="cc-deck__title">{portfolio.title}</h1>
        {portfolio.description && <div className="cc-deck__desc"><ReactMarkdown>{portfolio.description}</ReactMarkdown></div>}
        <div className="cc-deck__cover-foot">
          <span>CatalogCanvas</span>
          <span>/p/{portfolio.slug}</span>
        </div>
      </section>

      <section className="cc-deck__sec">
        <div className="cc-deck__indexhead">
          <h2>Works</h2>
          <span className="cc-mono">{portfolio.slug}</span>
        </div>
        <div className="cc-deck__indexgrid">
          {items.map((item, i) => (
            <div className="cc-deck__idxitem" key={item.id}>
              <span className="cc-deck__idxnum">{String(i + 1).padStart(2, '0')}</span>
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

      {items.map((item, i) => (
        <section className="cc-deck__sec cc-deck__art" key={item.id}>
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
      ))}

      <section className="cc-deck__sec cc-deck__colo">
        <div>
          <h2>About this work</h2>
          {portfolio.description && <ReactMarkdown>{portfolio.description}</ReactMarkdown>}
          <p>A portfolio of {total} works shared via CatalogCanvas.</p>
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
    </div>
  )
}
