import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="container">
      <div className="cc-empty cc-notfound">
        <p className="cc-notfound__code">404</p>
        <p className="cc-empty__title">Page not found</p>
        <p className="cc-empty__sub">The page you’re looking for doesn’t exist or has been moved.</p>
        <Link className="cc-btn cc-btn--primary" to="/">Back to items</Link>
      </div>
    </div>
  )
}
