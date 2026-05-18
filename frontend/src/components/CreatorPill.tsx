import type { CreatorInfo } from '../types/characterMap'

interface Props {
  creator: CreatorInfo
}

function hrefFor(creator: CreatorInfo): string | null {
  if (creator.kind === 'director' && creator.tmdb_person_id) {
    return `https://www.themoviedb.org/person/${creator.tmdb_person_id}`
  }
  if (creator.kind === 'author') {
    return `https://openlibrary.org/search/authors?q=${encodeURIComponent(creator.name)}`
  }
  return null
}

export function CreatorPill({ creator }: Props) {
  const href = hrefFor(creator)
  const icon = creator.kind === 'author' ? '✍' : '🎬'
  const verb = creator.kind === 'author' ? 'by' : ''

  const inner = (
    <>
      {creator.headshot_url ? (
        <img
          src={creator.headshot_url}
          alt={creator.name}
          draggable={false}
          loading="lazy"
          className="w-8 h-8 rounded-full object-cover -ml-1.5"
        />
      ) : (
        <span className="text-[15px] opacity-80">{icon}</span>
      )}
      {verb && <span className="text-[12px] uppercase tracking-wider text-[#888]">{verb}</span>}
      <span className="text-[14px] font-medium text-[#e5e7eb]">{creator.name}</span>
      {href && <span className="text-[11px] text-[#666] ml-0.5">↗</span>}
    </>
  )

  const baseClass =
    'inline-flex items-center gap-2 pl-1.5 pr-3 py-1 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] backdrop-blur transition-colors'

  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={`${baseClass} hover:border-[#555] hover:bg-[#202020]`}
        title={
          creator.kind === 'author'
            ? `Search Open Library for ${creator.name}`
            : `${creator.name} on TMDB`
        }
      >
        {inner}
      </a>
    )
  }
  return <span className={baseClass}>{inner}</span>
}
