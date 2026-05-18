import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { Character } from '../types/characterMap'

export interface CardNodeData {
  character: Character
  colour: string
}

export function CharacterCardNode({ data }: NodeProps) {
  const { character: c, colour } = data as unknown as CardNodeData
  const initials = c.name
    .split(' ')
    .slice(0, 2)
    .map((w: string) => w[0])
    .join('')
    .toUpperCase()

  return (
    <>
      <Handle id="src-right"  type="source" position={Position.Right}  style={{ opacity: 0 }} />
      <Handle id="src-bottom" type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle id="src-left"   type="source" position={Position.Left}   style={{ opacity: 0 }} />
      <Handle id="src-top"    type="source" position={Position.Top}    style={{ opacity: 0 }} />
      <Handle id="tgt-left"   type="target" position={Position.Left}   style={{ opacity: 0 }} />
      <Handle id="tgt-top"    type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <Handle id="tgt-right"  type="target" position={Position.Right}  style={{ opacity: 0 }} />
      <Handle id="tgt-bottom" type="target" position={Position.Bottom} style={{ opacity: 0 }} />

      <div
        style={{ borderColor: colour }}
        className="flex items-center gap-3.5 bg-[#1e1e1e] rounded-[10px] border-[1.5px] px-4 py-3 cursor-grab active:cursor-grabbing hover:shadow-[0_0_0_2px_rgba(255,255,255,0.1)] transition-shadow select-none"
      >
        {/* Avatar (headshot when actor present, initials otherwise). The
            anchor catches mousedown so React Flow doesn't initiate a drag. */}
        <div className="relative flex-shrink-0">
          {c.actor?.headshot_url && c.actor?.tmdb_person_id ? (
            <a
              href={`https://www.themoviedb.org/person/${c.actor.tmdb_person_id}`}
              target="_blank"
              rel="noopener noreferrer"
              title={`${c.actor.name} on TMDB`}
              onMouseDown={e => e.stopPropagation()}
              onClick={e => e.stopPropagation()}
              className="block w-14 h-14 rounded-full overflow-hidden ring-2 ring-transparent hover:ring-white/30 transition cursor-pointer"
              style={{ outlineColor: colour }}
            >
              <img
                src={c.actor.headshot_url}
                alt={c.actor.name}
                draggable={false}
                loading="lazy"
                className="w-full h-full object-cover"
              />
            </a>
          ) : (
            <div
              style={{ backgroundColor: colour }}
              className="w-14 h-14 rounded-full flex items-center justify-center text-base font-extrabold text-white"
            >
              {initials}
            </div>
          )}
        </div>

        {/* Name + role */}
        <div className="min-w-0">
          <div className="text-[22px] font-bold text-white leading-snug">{c.name}</div>
          <div className="text-[18px] text-[#9ca3af] mt-0.5">{c.role}</div>
        </div>
      </div>
    </>
  )
}
