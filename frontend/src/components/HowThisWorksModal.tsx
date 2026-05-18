interface Props {
  onClose: () => void
}

export default function HowThisWorksModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        className="award-card rounded-xl max-w-md w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="font-serif text-xl font-semibold text-award-cream">How this works</h2>
            <div className="gold-hairline mt-2" style={{ width: '60px' }} />
          </div>
          <button
            onClick={onClose}
            className="text-award-cream-dim hover:text-award-cream-muted text-2xl leading-none transition-colors mt-0.5"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="space-y-3 text-sm text-award-cream-muted leading-relaxed">
          <p>
            You type a title and click Search. The app looks it up in Open Library (for books) or
            TMDb (for films and TV) to confirm which work you mean and pull basic metadata — author,
            year, cover image. If the match is unambiguous it skips straight to generation; if
            there are multiple plausible results it shows you a small picker.
          </p>
          <p>
            Once you confirm the work, the request goes to the AI model you chose. The model returns
            a structured list of characters, relationships, and factions rendered as an interactive
            diagram you can pan, zoom, drag, and download as PNG, SVG, PDF, or Markdown.
            Nothing is saved longer than 90 days; no account needed.
          </p>
        </div>
        <button
          onClick={onClose}
          className="mt-5 w-full py-2.5 rounded-lg text-sm font-medium transition-all"
          style={{
            border: '1px solid rgba(61,48,32,0.9)',
            color: '#C4B49A',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.border = '1px solid rgba(212,175,55,0.4)'
            e.currentTarget.style.color = '#F4F0EC'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.border = '1px solid rgba(61,48,32,0.9)'
            e.currentTarget.style.color = '#C4B49A'
          }}
        >
          Got it
        </button>
      </div>
    </div>
  )
}
