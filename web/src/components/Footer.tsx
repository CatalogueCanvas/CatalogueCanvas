declare const __APP_VERSION__: string

export function Footer() {
  return (
    <footer className="cc-footer">
      <span>Designed and built by ToroRojo</span>
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/blob/main/LICENSE" target="_blank" rel="noreferrer">
        Open Source · AGPL-3.0
      </a>
      <span>v{__APP_VERSION__}</span>
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/issues" target="_blank" rel="noreferrer">
        Report Problem
      </a>
      <a href="https://github.com/ToroRojo-code/CatalogueCanvas/discussions" target="_blank" rel="noreferrer">
        Join Community
      </a>
    </footer>
  )
}
