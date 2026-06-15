import { Uploader } from '../components/Uploader'

export function Upload() {
  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Catalogue</p>
          <h1 className="cc-h1">Upload</h1>
        </div>
      </div>
      <Uploader onUploaded={() => {}} />
    </div>
  )
}
