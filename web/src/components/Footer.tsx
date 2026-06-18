declare const __APP_VERSION__: string

export function Footer() {
  return (
    <footer className="cc-footer">
      <span>Designed and built by ToledoEM</span>
      <a href="https://github.com/ToledoEM/CatalogueCanvas/blob/main/LICENSE" target="_blank" rel="noreferrer">
        Open Source · AGPL-3.0
      </a>
      <span>v{__APP_VERSION__}</span>
      <a href="https://github.com/ToledoEM/CatalogueCanvas/issues" target="_blank" rel="noreferrer">
        Report Problem
      </a>
      <a href="https://github.com/ToledoEM/CatalogueCanvas/discussions" target="_blank" rel="noreferrer">
        Join Community
      </a>
    </footer>
  )
}
