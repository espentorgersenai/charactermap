import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { Character } from '../types/characterMap'

export interface CardNodeData {
  character: Character
  colour: string
  showBadges: boolean
}

export function CharacterCardNode({ data }: NodeProps) {
  const { character: c, colour, showBadges } = data as unknown as CardNodeData
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
        className="flex items-center gap-3 bg-[#1e1e1e] rounded-[10px] border-[1.5px] px-3.5 py-2.5 cursor-grab active:cursor-grabbing hover:shadow-[0_0_0_2px_rgba(255,255,255,0.1)] transition-shadow select-none"
      >
        {/* Avatar circle */}
        <div className="relative flex-shrink-0">
          <div
            style={{ backgroundColor: colour }}
            className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-extrabold text-white"
          >
            {initials}
          </div>

          {/* Spoiler badge */}
          {c.spoiler_level != null && c.spoiler_level >= 2 && (
            <span
              className={`absolute -top-1 -right-1 w-[17px] h-[17px] rounded-full
                bg-amber-500 text-black text-[9px] font-bold
                flex items-center justify-center border-[1.5px] border-[#111]
                transition-all duration-200
                ${showBadges ? 'opacity-100 scale-100' : 'opacity-0 scale-50 pointer-events-none'}`}
            >
              ⚠
            </span>
          )}

          {/* Death badge */}
          {c.is_deceased_in_work && (
            <span
              className={`absolute -top-1 -left-1 w-[17px] h-[17px] rounded-full
                bg-[#374151] text-[#d1d5db] text-[12px] font-bold leading-none
                flex items-center justify-center border-[1.5px] border-[#111]
                transition-all duration-200
                ${showBadges ? 'opacity-100 scale-100' : 'opacity-0 scale-50 pointer-events-none'}`}
            >
              †
            </span>
          )}
        </div>

        {/* Name + role */}
        <div className="min-w-0">
          <div className="text-sm font-bold text-white leading-snug">{c.name}</div>
          <div className="text-[11px] text-[#9ca3af] mt-0.5">{c.role}</div>
        </div>
      </div>
    </>
  )
}
