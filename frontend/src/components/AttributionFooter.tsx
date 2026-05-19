// SPEC §15.3 — TMDb sentence + Open Library courtesy line shown site-wide.
// Slim, low-contrast, fixed at the bottom of the scroll area.
export default function AttributionFooter() {
  return (
    <footer
      className="text-[11px] text-center py-3 px-4 leading-relaxed"
      style={{
        color: 'rgba(244,232,192,0.35)',
        borderTop: '1px solid rgba(212,175,55,0.08)',
      }}
    >
      <p>
        This product uses the TMDB API but is not endorsed or certified by{' '}
        <a
          href="https://www.themoviedb.org"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-award-cream-dim"
        >
          TMDB
        </a>
        . Book data from{' '}
        <a
          href="https://openlibrary.org"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-award-cream-dim"
        >
          Open Library
        </a>
        .
      </p>
    </footer>
  )
}
