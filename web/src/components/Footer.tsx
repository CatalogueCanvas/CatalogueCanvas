import { useEffect, useState } from 'react'
import * as api from '../api/client'
import { useAuth } from '../api/auth'

declare const __APP_VERSION__: string

export function Footer() {
  const { isAdmin } = useAuth()
  const [latest, setLatest] = useState<string | null>(null)

  useEffect(() => {
    // Only admins can query the update endpoint; the check itself is opt-in and
    // throttled server-side, so this is a cheap cached read for everyone else.
    if (!isAdmin) return
    api.getVersion()
      .then((v) => { if (v.update_available && v.latest) setLatest(v.latest) })
      .catch(() => { /* silent: never surface update-check failures in the footer */ })
  }, [isAdmin])

  return (
    <footer className="cc-footer">
      <span>Designed and built by ToroRojo</span>
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/blob/main/LICENSE" target="_blank" rel="noreferrer">
        Open Source · AGPL-3.0
      </a>
      <span>v{__APP_VERSION__}</span>
      {latest && (
        <a href="https://github.com/CatalogueCanvas/CatalogueCanvas#updating" target="_blank" rel="noreferrer">
          update available → v{latest}
        </a>
      )}
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/issues" target="_blank" rel="noreferrer">
        Report Problem
      </a>
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/discussions" target="_blank" rel="noreferrer">
        Join Community
      </a>
    </footer>
  )
}
