import { useState, useMemo, useCallback } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { buildLayout, pickHandles, NODE_WIDTH, NODE_HEIGHT } from '../layout/layout'
import { CharacterCardNode } from './CharacterCardNode'
import { FactionGroupNode } from './FactionGroupNode'
import { CreatorPill } from './CreatorPill'
import { ExportMenu } from './ExportMenu'
import { ShareButton } from './ShareButton'
import type { CharacterMap } from '../types/characterMap'

const NODE_TYPES = {
  characterCard: CharacterCardNode,
  factionGroup:  FactionGroupNode,
}

function LegendPanel() {
  const EDGE_LEGEND = [
    { label: 'Alliance / Family', colour: '#22c55e', dashed: false },
    { label: 'Romantic',          colour: '#ec4899', dashed: false },
    { label: 'Antagonism',        colour: '#ef4444', dashed: false },
    { label: 'Professional',      colour: '#94a3b8', dashed: true  },
    { label: 'Mentorship',        colour: '#f59e0b', dashed: false },
    { label: 'Criminal',          colour: '#eab308', dashed: true  },
  ]
  return (
    <div className="mb-1.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-3 min-w-[210px]">
      <p className="text-[10px] font-bold text-[#555] uppercase tracking-[0.06em] mb-2">Relationships</p>
      {EDGE_LEGEND.map(e => (
        <div key={e.label} className="flex items-center gap-2 mb-1.5 last:mb-0">
          <div
            style={{
              width: 28, height: e.dashed ? 0 : 2,
              background: e.dashed ? 'transparent' : e.colour,
              borderTop: e.dashed ? `2px dashed ${e.colour}` : 'none',
              flexShrink: 0,
            }}
          />
          <span className="text-[12px] text-[#ccc]">{e.label}</span>
        </div>
      ))}
    </div>
  )
}

function SettingPreamble({ text }: { text: string }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="mx-4 mt-3 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-semibold text-[#aaa] hover:text-white transition-colors"
      >
        <span>📖 Setting</span>
        <span className={`text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▲</span>
      </button>
      {open && (
        <div className="px-4 pb-3 text-sm text-[#ccc] leading-relaxed border-t border-[#2a2a2a]">
          <p className="mt-3">{text}</p>
        </div>
      )}
    </div>
  )
}

interface CanvasProps { charMap: CharacterMap; jobId: string }

function InnerCanvas({ charMap, jobId }: CanvasProps) {
  const [showLabels, setShowLabels] = useState(false)
  const [showLegend, setShowLegend] = useState(false)
  const coverageKey = `cm-coverage-dismissed-${jobId}`
  const [coverageDismissed, setCoverageDismissed] = useState(() => {
    try { return localStorage.getItem(coverageKey) === '1' } catch { return false }
  })
  const dismissCoverage = useCallback(() => {
    setCoverageDismissed(true)
    try { localStorage.setItem(coverageKey, '1') } catch {}
  }, [coverageKey])

  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildLayout(charMap),
    [charMap],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, , onEdgesChange] = useEdgesState(initEdges)

  // Absolute centers of character nodes, accounting for parent (faction) offset.
  // Recomputed whenever nodes move so edge handles pick the facing side live.
  const centers = useMemo(() => {
    const parentPos = new Map<string, { x: number; y: number }>()
    nodes.forEach(n => {
      if (n.type === 'factionGroup') parentPos.set(n.id, n.position)
    })
    const m = new Map<string, { x: number; y: number }>()
    nodes.forEach(n => {
      if (n.type !== 'characterCard') return
      const pp = n.parentId ? parentPos.get(n.parentId) : undefined
      const px = pp?.x ?? 0
      const py = pp?.y ?? 0
      m.set(n.id, {
        x: px + n.position.x + NODE_WIDTH / 2,
        y: py + n.position.y + NODE_HEIGHT / 2,
      })
    })
    return m
  }, [nodes])

  const liveEdges = useMemo(
    () => edges.map(e => {
      const src = centers.get(e.source)
      const tgt = centers.get(e.target)
      const handles = src && tgt
        ? pickHandles(src, tgt)
        : { sourceHandle: e.sourceHandle, targetHandle: e.targetHandle }
      return {
        ...e,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        label: showLabels ? e.label : undefined,
        zIndex: showLabels ? 10 : 0,
      }
    }),
    [edges, showLabels, centers],
  )

  const resetLayout = useCallback(() => {
    const { nodes: fresh } = buildLayout(charMap)
    setNodes(fresh)
  }, [charMap, setNodes])

  return (
    <div className="flex flex-col h-full bg-[#111]">

      {/* Title strip */}
      <div className="bg-[#161616] border-b border-[#222] px-6 py-3 flex-shrink-0">
        <h1 className="text-lg font-bold text-white leading-tight">
          {charMap.title}
        </h1>
        {charMap.subtitle && (
          <p className="text-[12px] text-[#888] mt-0.5">{charMap.subtitle}</p>
        )}
        {charMap.blurb && (
          <p className="text-[12px] text-[#aaa] mt-1.5 leading-relaxed max-w-4xl">
            {charMap.blurb}
          </p>
        )}
      </div>

      {/* Top toolbar */}
      <div className="bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-2.5 flex items-center gap-2.5 flex-shrink-0">
        <button
          onClick={() => setShowLabels(v => !v)}
          title="Toggle relationship labels on edges"
          className={`px-4 py-2 text-sm font-semibold rounded-lg border-[1.5px] transition-colors ${
            showLabels
              ? 'bg-[#2563eb] text-white border-[#2563eb]'
              : 'bg-transparent text-[#555] border-[#2a2a2a] hover:border-[#555] hover:text-[#aaa]'
          }`}
        >
          Labels
        </button>

        <div className="w-px h-6 bg-[#2a2a2a] mx-1" />

        <ShareButton jobId={jobId} />
        <ExportMenu jobId={jobId} />

        <div className="w-px h-6 bg-[#2a2a2a] mx-1" />

        <button
          onClick={resetLayout}
          className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
        >
          Reset layout
        </button>
      </div>

      {/* Optional banners */}
      {charMap.coverage_note && !coverageDismissed && (
        <div className="mx-4 mt-3 px-4 py-2.5 bg-amber-900/15 border border-amber-500/40 rounded-lg text-amber-300 text-sm flex items-start gap-2 flex-shrink-0">
          <span className="flex-shrink-0 mt-0.5">⚠</span>
          <span className="flex-1"><strong>Coverage note:</strong> {charMap.coverage_note}</span>
          <button
            onClick={dismissCoverage}
            className="flex-shrink-0 ml-2 text-amber-500 hover:text-amber-200 transition-colors leading-none text-base"
            title="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {charMap.setting_preamble && (
        <div className="flex-shrink-0">
          <SettingPreamble text={charMap.setting_preamble} />
        </div>
      )}

      {/* React Flow canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={liveEdges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          minZoom={0.08}
          maxZoom={2.5}
          deleteKeyCode={null}
          className="bg-[#111]"
        >
          <MiniMap
            style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 6 }}
            nodeColor="#2a2a2a"
          />
          <Controls
            style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 6 }}
          />
          <Background color="#1e1e1e" variant={BackgroundVariant.Dots} gap={20} />
        </ReactFlow>

        {/* Creator pill (author / director) */}
        {charMap.creator && (
          <div className="absolute top-3.5 left-3.5 z-10">
            <CreatorPill creator={charMap.creator} />
          </div>
        )}

        {/* Legend toggle */}
        <div className="absolute bottom-3.5 left-3.5 z-10">
          {showLegend && <LegendPanel />}
          <button
            onClick={() => setShowLegend(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg text-[12px] font-semibold text-[#aaa] hover:border-[#444] hover:text-[#e5e7eb] transition-colors"
          >
            Legend
            <span className={`text-[10px] transition-transform duration-200 ${showLegend ? 'rotate-180' : ''}`}>
              ▲
            </span>
          </button>
        </div>
      </div>
    </div>
  )
}

export function CharacterMapCanvas({ charMap, jobId }: CanvasProps) {
  return (
    <ReactFlowProvider>
      <InnerCanvas charMap={charMap} jobId={jobId} />
    </ReactFlowProvider>
  )
}
