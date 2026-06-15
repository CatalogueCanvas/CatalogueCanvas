const ICONS: Record<string, string> = {
  items: `<rect class="cc-ico-acc" x="13.4" y="3.4" width="7.2" height="7.2" rx="1.4"/>
    <rect class="cc-ico-ink" x="3.4" y="3.4" width="7.2" height="7.2" rx="1.4"/>
    <rect class="cc-ico-ink" x="3.4" y="13.4" width="7.2" height="7.2" rx="1.4"/>
    <rect class="cc-ico-ink" x="13.4" y="13.4" width="7.2" height="7.2" rx="1.4"/>`,
  collections: `<rect class="cc-ico-acc" x="6.6" y="3.4" width="14" height="14" rx="1.8"/>
    <rect class="cc-ico-ink cc-ico-surface" x="3.4" y="6.6" width="14" height="14" rx="1.8"/>`,
  portfolios: `<path class="cc-ico-ink" d="M8.1 10.8 15.9 7.2M8.1 13.2 15.9 16.8"/>
    <circle class="cc-ico-acc" cx="6" cy="12" r="2.7"/>
    <circle class="cc-ico-ink cc-ico-surface" cx="18" cy="6" r="2.4"/>
    <circle class="cc-ico-ink cc-ico-surface" cx="18" cy="18" r="2.4"/>`,
  upload: `<path class="cc-ico-ink" d="M4 14.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3.5"/>
    <path class="cc-ico-acc" d="M12 3.2 16.8 9H13.6v6.2h-3.2V9H7.2z"/>`,
  settings: `<path class="cc-ico-ink" d="M4 7.5h16M4 16.5h16"/>
    <circle class="cc-ico-acc" cx="15.5" cy="7.5" r="2.8"/>
    <circle class="cc-ico-acc" cx="8.5" cy="16.5" r="2.8"/>`,
  logout: `<path class="cc-ico-ink" d="M11 4.2H6a2 2 0 0 0-2 2v11.6a2 2 0 0 0 2 2h5"/>
    <path class="cc-ico-acc" d="M15 7.6 20.4 12 15 16.4v-3.1H9.2v-2.6H15z"/>`,
  create: `<rect class="cc-ico-acc" x="3.4" y="3.4" width="17.2" height="17.2" rx="3.4"/>
    <path class="cc-ico-knock" d="M12 7.6v8.8M7.6 12h8.8"/>`,
  edit: `<path class="cc-ico-ink" d="M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5"/>
    <path class="cc-ico-acc" d="M15 3.4 20.6 9 11.7 17.9 6.2 19.8 8.1 14.3z"/>
    <path class="cc-ico-knock" d="M13.6 6.3 17.7 10.4" stroke-width="1.6"/>`,
  view: `<path class="cc-ico-ink" d="M2.6 12S6 5.6 12 5.6 21.4 12 21.4 12 18 18.4 12 18.4 2.6 12 2.6 12z"/>
    <circle class="cc-ico-acc" cx="12" cy="12" r="3.4"/>`,
  save: `<path class="cc-ico-ink" d="M5 4.4h11l3.6 3.6V19A1.6 1.6 0 0 1 18 20.6H5A1.6 1.6 0 0 1 3.4 19V6A1.6 1.6 0 0 1 5 4.4z"/>
    <path class="cc-ico-acc" d="M8 4.4h7v4.8H8z"/>
    <rect class="cc-ico-ink" x="8" y="13" width="8" height="6.6" rx="0.7"/>`,
  copy: `<rect class="cc-ico-acc" x="9" y="9" width="11.6" height="11.6" rx="2.2"/>
    <rect class="cc-ico-ink cc-ico-surface" x="3.4" y="3.4" width="11.6" height="11.6" rx="2.2"/>`,
  download: `<path class="cc-ico-ink" d="M4 14.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3.5"/>
    <path class="cc-ico-acc" d="M12 16.8 7.2 11h3.2V4.8h3.2V11h3.2z"/>`,
  delete: `<path class="cc-ico-acc" d="M3.4 6.4h17.2l-.6 2.2H4z"/>
    <path class="cc-ico-ink" d="M9 6.4V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1.4"/>
    <path class="cc-ico-ink" d="M6 8.8 6.8 19a1.6 1.6 0 0 0 1.6 1.5h7.2a1.6 1.6 0 0 0 1.6-1.5L18 8.8"/>
    <path class="cc-ico-ink" d="M10 11.6v6M14 11.6v6"/>`,
  generate: `<path class="cc-ico-acc" d="M10.5 3 12.2 8.3 17.5 10 12.2 11.7 10.5 17 8.8 11.7 3.5 10 8.8 8.3z"/>
    <path class="cc-ico-ink" d="M17.6 14 18.3 16.2 20.5 16.9 18.3 17.6 17.6 19.8 16.9 17.6 14.7 16.9 16.9 16.2z"/>`,
  filter: `<path class="cc-ico-ink" d="M3.4 4.2h17.2L14 12.4v6.4l-4 2v-8.4z"/>`,
  chevronDown: `<path class="cc-ico-ink" d="M5 9 12 16 19 9" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`,
  heart: `<path class="cc-ico-ink" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M12 20.2 4.6 13C2.6 11 2.6 7.7 4.6 5.7c2-2 5.1-2 7 0L12 6l.4-.3c2-2 5.1-2 7 0 2 2 2 5.3 0 7.3z"/>`,
  heartFilled: `<path class="cc-ico-acc" d="M12 20.2 4.6 13C2.6 11 2.6 7.7 4.6 5.7c2-2 5.1-2 7 0L12 6l.4-.3c2-2 5.1-2 7 0 2 2 2 5.3 0 7.3z"/>`,
}

export function Icon({ name, size = 18, className = '' }: { name: string; size?: number; className?: string }) {
  const svg = ICONS[name]
  if (!svg) return null
  return (
    <svg
      className={`cc-ico ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
