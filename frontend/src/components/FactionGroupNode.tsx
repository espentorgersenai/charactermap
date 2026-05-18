import type { NodeProps } from '@xyflow/react'

export interface FactionGroupData {
  label: string
  colour: string
  description: string
}

export function FactionGroupNode({ data, width, height }: NodeProps) {
  const { label, colour } = data as unknown as FactionGroupData

  return (
    <div
      style={{
        width:  width  ?? '100%',
        height: height ?? '100%',
        borderColor: colour,
        backgroundColor: `${colour}12`,
      }}
      className="rounded-[14px] border-[1.5px] pointer-events-none absolute inset-0"
    >
      <span
        style={{ color: `${colour}dd` }}
        className="absolute top-3 left-4 text-[11px] font-bold tracking-[0.07em] uppercase select-none"
      >
        {label}
      </span>
    </div>
  )
}
