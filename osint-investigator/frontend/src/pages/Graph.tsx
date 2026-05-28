import { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { GraphResponse, GraphNodeOut, GraphEdgeOut } from '../types'

const W = 860
const H = 540

const RISK_COLOR: Record<string, string> = {
  low: '#16a34a', medium: '#ca8a04', high: '#ea580c', critical: '#dc2626',
}
const RISK_LABEL: Record<string, string> = {
  low: 'Baixo', medium: 'Médio', high: 'Alto', critical: 'Crítico',
}

type Pos = Record<string, { x: number; y: number }>

function runForce(nodes: GraphNodeOut[], edges: GraphEdgeOut[]): Pos {
  if (nodes.length === 0) return {}

  const pos: Record<string, { x: number; y: number; vx: number; vy: number }> = {}

  // Subjects in a ring, others scattered
  const subjects = nodes.filter(n => n.type === 'subject')
  const others = nodes.filter(n => n.type !== 'subject')

  subjects.forEach((n, i) => {
    const angle = (i / Math.max(subjects.length, 1)) * 2 * Math.PI - Math.PI / 2
    const r = Math.min(W, H) * (subjects.length <= 3 ? 0.22 : 0.30)
    pos[n.id] = { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle), vx: 0, vy: 0 }
  })
  others.forEach((n, i) => {
    const angle = (i / Math.max(others.length, 1)) * 2 * Math.PI
    const r = Math.min(W, H) * 0.42
    pos[n.id] = { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle), vx: 0, vy: 0 }
  })

  const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.7

  for (let iter = 0; iter < 250; iter++) {
    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = pos[nodes[i].id], b = pos[nodes[j].id]
        const dx = (b.x - a.x) || 0.1, dy = (b.y - a.y) || 0.1
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.1
        const force = (k * k) / dist * 0.4
        const nx = dx / dist, ny = dy / dist
        a.vx -= nx * force * 0.01; a.vy -= ny * force * 0.01
        b.vx += nx * force * 0.01; b.vy += ny * force * 0.01
      }
    }
    // Attraction along edges
    for (const e of edges) {
      const a = pos[e.source_id], b = pos[e.target_id]
      if (!a || !b) continue
      const dx = b.x - a.x, dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.1
      const force = (dist * dist) / k * 0.06
      const nx = dx / dist, ny = dy / dist
      a.vx += nx * force; a.vy += ny * force
      b.vx -= nx * force; b.vy -= ny * force
    }
    // Center gravity
    for (const n of nodes) {
      const p = pos[n.id]
      p.vx += (W / 2 - p.x) * 0.002; p.vy += (H / 2 - p.y) * 0.002
    }
    // Apply + damping + clamp
    for (const n of nodes) {
      const p = pos[n.id]
      p.x = Math.max(50, Math.min(W - 50, p.x + p.vx))
      p.y = Math.max(40, Math.min(H - 40, p.y + p.vy))
      p.vx *= 0.84; p.vy *= 0.84
    }
  }

  return Object.fromEntries(Object.entries(pos).map(([id, { x, y }]) => [id, { x, y }]))
}

function NodeShape({ node, pos, hovered, onHover, onClick }: {
  node: GraphNodeOut
  pos: { x: number; y: number }
  hovered: boolean
  onHover: (id: string | null) => void
  onClick: () => void
}) {
  const isSubject = node.type === 'subject'
  const isCompany = node.type === 'company'
  const r = isSubject ? 22 : isCompany ? 0 : 14
  const color = isSubject
    ? (RISK_COLOR[node.risk_level || 'low'] || '#6b7280')
    : isCompany ? '#6b7280' : '#93c5fd'

  const label = node.label.length > 18 ? node.label.slice(0, 16) + '…' : node.label

  return (
    <g
      transform={`translate(${pos.x},${pos.y})`}
      style={{ cursor: isSubject ? 'pointer' : 'default' }}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onClick={isSubject ? onClick : undefined}
    >
      {isCompany ? (
        <rect x={-36} y={-14} width={72} height={28} rx={6}
          fill={hovered ? '#e5e7eb' : '#f3f4f6'}
          stroke={hovered ? '#9ca3af' : '#d1d5db'} strokeWidth={1.5} />
      ) : (
        <circle r={r}
          fill={hovered ? color + 'cc' : color + (isSubject ? '' : '55')}
          stroke={color} strokeWidth={isSubject ? 2 : 1.5} />
      )}
      <text
        y={isCompany ? 5 : r + 13}
        textAnchor="middle"
        fontSize={isSubject ? 11 : 10}
        fontWeight={isSubject ? '600' : '400'}
        fill={isCompany ? '#374151' : '#374151'}
      >
        {label}
      </text>
      {isSubject && node.risk_score != null && (
        <text y={6} textAnchor="middle" fontSize={10} fontWeight="700" fill="white">
          {Math.round(node.risk_score)}
        </text>
      )}
    </g>
  )
}

export default function Graph() {
  const [graph, setGraph] = useState<GraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.getGraph()
      .then(setGraph)
      .catch(e => setError(e instanceof Error ? e.message : 'Erro ao carregar grafo'))
      .finally(() => setLoading(false))
  }, [])

  const positions = useMemo(() => {
    if (!graph || graph.nodes.length === 0) return {}
    return runForce(graph.nodes, graph.edges)
  }, [graph])

  const hoveredConnected = useMemo(() => {
    if (!hovered || !graph) return new Set<string>()
    const connected = new Set<string>()
    graph.edges.forEach(e => {
      if (e.source_id === hovered) connected.add(e.target_id)
      if (e.target_id === hovered) connected.add(e.source_id)
    })
    return connected
  }, [hovered, graph])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <p className="text-red-600">{error}</p>
    </div>
  )

  const stats = graph?.stats
  const nodes = graph?.nodes || []
  const edges = graph?.edges || []
  const noInvestigations = nodes.filter(n => n.type === 'subject').length === 0
  const noConnections = !stats?.shared_entities

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="text-gray-400 hover:text-gray-600 text-sm">← Voltar</Link>
            <div>
              <h1 className="text-lg font-bold text-gray-900">🕸️ Rede de Relações</h1>
              <p className="text-xs text-gray-500">Vínculos entre investigados</p>
            </div>
          </div>
          {stats && (
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span><strong>{stats.subjects}</strong> investigados</span>
              <span><strong>{stats.companies}</strong> empresas</span>
              <span><strong>{stats.partners}</strong> sócios</span>
              {stats.shared_entities > 0 && (
                <span className="text-orange-600 font-semibold">
                  🔗 {stats.shared_entities} conexão(ões) compartilhada(s)
                </span>
              )}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {noInvestigations ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <p className="text-4xl mb-4">🕸️</p>
            <p className="text-gray-600 font-medium">Nenhuma investigação concluída ainda.</p>
            <p className="text-gray-400 text-sm mt-1">Realize investigações para descobrir vínculos entre investigados.</p>
            <Link to="/investigacoes/nova" className="mt-4 inline-block text-blue-600 hover:underline text-sm">
              + Nova investigação
            </Link>
          </div>
        ) : noConnections ? (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-sm text-blue-800">
              <strong>Nenhuma conexão entre investigados identificada ainda.</strong>
              <span className="text-blue-600 ml-1">Continue realizando investigações para descobrir vínculos societários compartilhados.</span>
            </div>
            <GraphCanvas nodes={nodes} edges={edges} positions={positions}
              hovered={hovered} hoveredConnected={hoveredConnected}
              setHovered={setHovered} navigate={navigate} />
          </div>
        ) : (
          <GraphCanvas nodes={nodes} edges={edges} positions={positions}
            hovered={hovered} hoveredConnected={hoveredConnected}
            setHovered={setHovered} navigate={navigate} />
        )}

        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-gray-500 bg-white rounded-xl border border-gray-100 px-4 py-3">
          <span className="font-semibold text-gray-600">Legenda:</span>
          {Object.entries(RISK_COLOR).map(([level, color]) => (
            <span key={level} className="flex items-center gap-1.5">
              <span className="w-3.5 h-3.5 rounded-full inline-block" style={{ background: color }} />
              Investigado {RISK_LABEL[level]}
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span className="w-5 h-3.5 rounded inline-block bg-gray-200 border border-gray-300" />
            Empresa (QSA)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full inline-block bg-blue-200 border border-blue-400" />
            Sócio
          </span>
        </div>
      </main>
    </div>
  )
}

function GraphCanvas({ nodes, edges, positions, hovered, hoveredConnected, setHovered, navigate }: {
  nodes: GraphNodeOut[]
  edges: GraphEdgeOut[]
  positions: Pos
  hovered: string | null
  hoveredConnected: Set<string>
  setHovered: (id: string | null) => void
  navigate: ReturnType<typeof useNavigate>
}) {
  if (Object.keys(positions).length === 0) return null

  const edgeIsHighlighted = (e: GraphEdgeOut) =>
    hovered !== null && (e.source_id === hovered || e.target_id === hovered)

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ maxHeight: '60vh' }}
      >
        {/* Edges */}
        {edges.map(e => {
          const a = positions[e.source_id], b = positions[e.target_id]
          if (!a || !b) return null
          const highlighted = edgeIsHighlighted(e)
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
          return (
            <g key={e.id}>
              <line
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={highlighted ? '#6366f1' : '#d1d5db'}
                strokeWidth={highlighted ? 2 : 1}
                strokeOpacity={hovered && !highlighted ? 0.2 : 1}
              />
              {highlighted && (
                <text x={mx} y={my - 5} textAnchor="middle" fontSize={9} fill="#6366f1" fontWeight="600">
                  {e.label}
                </text>
              )}
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map(n => {
          const pos = positions[n.id]
          if (!pos) return null
          const isHovered = hovered === n.id
          const isConnected = hoveredConnected.has(n.id)
          const dimmed = hovered !== null && !isHovered && !isConnected

          return (
            <g key={n.id} opacity={dimmed ? 0.25 : 1}>
              <NodeShape
                node={n}
                pos={pos}
                hovered={isHovered || isConnected}
                onHover={setHovered}
                onClick={() => n.investigation_id && navigate(`/investigacoes/${n.investigation_id}/relatorio`)}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}
