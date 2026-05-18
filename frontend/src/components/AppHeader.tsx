import { Link } from 'react-router-dom'

export default function AppHeader() {
  return (
    <header className="flex-shrink-0 sticky top-0 z-40"
      style={{
        background: 'rgba(13,11,9,0.88)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(212,175,55,0.12)',
      }}
    >
      <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link
          to="/"
          className="font-serif text-xl font-semibold tracking-wide transition-colors"
          style={{ color: '#E2CA78' }}
        >
          CharacterMap
        </Link>
        <nav className="flex items-center gap-1">
          <Link
            to="/privacy"
            className="px-3 py-1.5 text-sm text-award-cream-dim hover:text-award-cream-muted transition-colors"
          >
            Privacy
          </Link>
          <Link
            to="/terms"
            className="px-3 py-1.5 text-sm text-award-cream-dim hover:text-award-cream-muted transition-colors"
          >
            Terms
          </Link>
        </nav>
      </div>
      {/* Gold gradient hairline at the bottom of the header */}
      <div className="gold-hairline opacity-70" />
    </header>
  )
}
