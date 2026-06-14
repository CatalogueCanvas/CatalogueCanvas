import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as api from '../api/client'
import type { Item, DescribeResult, AppSettings } from '../api/client'
import { LLMButton } from '../components/LLMButton'
import { MetadataForm } from '../components/MetadataForm'
import { NotesPanel } from '../components/NotesPanel'

export function ItemEdit() {
  const { id } = useParams<{ id: string }>()
  const [item, setItem] = useState<Item | null>(null)
  const [llmResult, setLlmResult] = useState<DescribeResult | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (id) api.getItem(id).then(setItem)
  }, [id])

  useEffect(() => {
    api.getSettings().then(setSettings)
  }, [])

  if (!item) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">Loading...</p></div></div>

  const applyDescription = async () => {
    if (!llmResult) return
    const note = [llmResult.summary, '', ...llmResult.descriptions.map((d) => `- ${d}`)].join('\n')
    const updated = await api.updateItem(item.id, { note })
    setItem(updated)
    setLlmResult(null)
  }

  const remove = async () => {
    if (!confirm(`Delete item ${item.id}? This cannot be undone.`)) return
    await api.deleteItem(item.id)
    navigate('/')
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Catalog</p>
          <h1 className="cc-h1">{item.title}</h1>
        </div>
        <button className="cc-btn cc-btn--danger" onClick={remove}>Delete</button>
      </div>
      <div className="cc-itemedit">
        <div className="cc-itemedit__media">
          <div className="cc-thumb cc-thumb--lg">
            {item.preview_url ? <img src={item.preview_url} alt={item.title} /> : <span className="cc-thumb__label">no preview</span>}
          </div>
          {item.download_urls.filter((d) => d.type === 'image').length > 0 && (
            <div className="cc-thumbrow">
              {item.download_urls.filter((d) => d.type === 'image').map((d) => (
                <a key={d.url} href={d.url} target="_blank" rel="noreferrer">
                  <img src={d.url} alt={d.name} />
                </a>
              ))}
            </div>
          )}
        </div>
        <div className="cc-stack">
          <div className="cc-row__meta"><span className="cc-mono">ID: {item.id}</span></div>
          {item.download_urls.length > 0 && (
            <div className="cc-field">
              <label className="cc-label">Files</label>
              <div className="cc-files">
                {item.download_urls.map((d) => (
                  d.type === 'other'
                    ? (
                      <a key={d.url} className="cc-pill" href={d.url} download>
                        {d.name} <span className="cc-pill-type">{d.type}</span>
                      </a>
                    )
                    : (
                      <a key={d.url} className="cc-pill" href={d.url} target="_blank" rel="noreferrer">
                        {d.name} <span className="cc-pill-type">{d.type}</span>
                      </a>
                    )
                ))}
              </div>
            </div>
          )}
          <div>
            <a className="cc-btn" href={api.itemArchiveUrl(item.id)} download>Download all as ZIP</a>
          </div>
          <div className="cc-panel">
            <MetadataForm item={item} onSaved={setItem} />
          </div>
          {settings?.llm_auto_generate === 'true' && <LLMButton itemId={item.id} onResult={setLlmResult} />}
          {llmResult && (
            <div className="cc-llm__result">
              <strong>Summary:</strong> {llmResult.summary}
              <ul>
                {llmResult.descriptions.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
              <button className="cc-btn cc-btn--primary" onClick={applyDescription} type="button">Apply to note</button>
            </div>
          )}
        </div>
      </div>
      <NotesPanel item={item} onSaved={setItem} />
    </div>
  )
}
