import { useEffect, useState, useMemo, useCallback } from 'react'
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

const RELATIONSHIP_OPTIONS = [
  { value: 'cônjuge',  label: 'Cônjuge / Marido / Esposa' },
  { value: 'pai',      label: 'Pai' },
  { value: 'mãe',      label: 'Mãe' },
  { value: 'filho',    label: 'Filho / Filha' },
  { value: 'irmão',    label: 'Irmão / Irmã' },
  { value: 'parente',  label: 'Outro parente' },
  { value: 'sócio',    label: 'Sócio / Parceiro de negócios' },
  { value: 'outro',    label: 'Outra relação' },
]

const FAMILY_TYPES = new Set(['cônjuge', 'pai', 'mãe', 'filho', 'irmão', 'parente'])
const BUSINESS_TYPES = new Set(['sócio'])

function getEdgeColor(relType: string, highlighted: boolean): string {
  if (relType === 'auto') return highlighted ? '#6366f1' : '#d1d5db'
  if (FAMILY_TYPES.has(relType)) return '#f97316'
  if (BUSINESS_TYPES.has(relType)) return '#3b82f6'
  return '#a855f7'
}

type Pos = Record<string, { x: number; y: number }>

function runForce(nodes: GraphNodeOut[], edges: GraphEdgeOut[]): Pos {
  if (nodes.length === 0) return {}

  const pos: Record<string, { x: number; y: number; vx: number; vy: number }> = {}

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
    for (const n of nodes) {
      const p = pos[n.id]
      p.vx += (W / 2 - p.x) * 0.002; p.vy += (H / 2 - p.y) * 0.002
    }
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
        fill="#374151"
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
  const [hoveredEdge, setHoveredEdge] = useState<string | null>(null)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [linkNodeA, setLinkNodeA] = useState('')
  const [linkNodeB, setLinkNodeB] = useState('')
  const [linkRelType, setLinkRelType] = useState('cônjuge')
  const [linkCustomLabel, setLinkCustomLabel] = useState('')
  const [linkLoading, setLinkLoading] = useState(false)
  const navigate = useNavigate()

  const fetchGraph = useCallback(async () => {
    try {
      const data = await api.getGraph()
      setGraph(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar grafo')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchGraph() }, [fetchGraph])

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

  const handleLink = async () => {
    if (!linkNodeA || !linkNodeB) return
    setLinkLoading(true)
    const label =
      linkCustomLabel.trim() ||
      RELATIONSHIP_OPTIONS.find(o => o.value === linkRelType)?.label ||
      linkRelType
    try {
      await api.createGraphEdge({
        source_node_id: linkNodeA,
        target_node_id: linkNodeB,
        relationship_type: linkRelType,
        label,
      })
      await fetchGraph()
      setShowLinkModal(false)
      setLinkNodeA(''); setLinkNodeB(''); setLinkRelType('cônjuge'); setLinkCustomLabel('')
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Erro ao criar vínculo')
    } finally {
      setLinkLoading(false)
    }
  }

  const handleDeleteEdge = async (edgeId: string) => {
    if (!window.confirm('Remover esta conexão manual?')) return
    try {
      await api.deleteGraphEdge(edgeId)
      await fetchGraph()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Erro ao remover conexão')
    }
  }

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
  const subjects = nodes.filter(n => n.type === 'subject')
  const noInvestigations = subjects.length === 0
  const hasAnyConnection = (stats?.shared_entities ?? 0) > 0 || edges.some(e => e.is_manual)

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
          <div className="flex items-center gap-4">
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
            {subjects.length >= 2 && (
              <button
                onClick={() => setShowLinkModal(true)}
                className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm"
              >
                🔗 Vincular investigados
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {noInvestigations ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <p className="text-4xl mb-4">🕸️</p>
            <p className="text-gray-600 font-medium">Nenhuma investigação concluída ainda.</p>
            <p className="text-gray-400 text-sm mt-1">Realize investigações para que os nós apareçam na rede.</p>
            <Link to="/investigacoes/nova" className="mt-4 inline-block text-blue-600 hover:underline text-sm">
              + Nova investigação
            </Link>
          </div>
        ) : !hasAnyConnection ? (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 text-sm text-blue-800">
              <strong>Nenhuma conexão identificada ainda.</strong>
              <span className="text-blue-600 ml-1">
                Use "Vincular investigados" para registrar relações manuais (família, sócios, etc.),
                ou continue investigando para detectar vínculos societários compartilhados.
              </span>
            </div>
            <GraphCanvas nodes={nodes} edges={edges} positions={positions}
              hovered={hovered} hoveredConnected={hoveredConnected} hoveredEdge={hoveredEdge}
              setHovered={setHovered} setHoveredEdge={setHoveredEdge}
              navigate={navigate} onDeleteEdge={handleDeleteEdge} />
          </div>
        ) : (
          <GraphCanvas nodes={nodes} edges={edges} positions={positions}
            hovered={hovered} hoveredConnected={hoveredConnected} hoveredEdge={hoveredEdge}
            setHovered={setHovered} setHoveredEdge={setHoveredEdge}
            navigate={navigate} onDeleteEdge={handleDeleteEdge} />
        )}

        {/* Legend */}
        <div className="mt-4 bg-white rounded-xl border border-gray-100 px-4 py-3 space-y-2">
          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
            <span className="font-semibold text-gray-600">Nós:</span>
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
          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
            <span className="font-semibold text-gray-600">Vínculos:</span>
            <span className="flex items-center gap-1.5">
              <svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="#d1d5db" strokeWidth="1.5" strokeDasharray="4 3"/></svg>
              Societário (automático)
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="#f97316" strokeWidth="2.5"/></svg>
              Familiar
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="#3b82f6" strokeWidth="2"/></svg>
              Sócio (manual)
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke="#a855f7" strokeWidth="2"/></svg>
              Outro
            </span>
            <span className="text-gray-400 italic">— Passe o mouse sobre um vínculo manual para removê-lo.</span>
          </div>
        </div>
      </main>

      {/* Link Modal */}
      {showLinkModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-bold text-gray-900 mb-1">Vincular Investigados</h2>
            <p className="text-sm text-gray-500 mb-5">
              Registre uma relação confirmada entre dois investigados da rede.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Investigado A</label>
                <select
                  value={linkNodeA}
                  onChange={e => { setLinkNodeA(e.target.value); setLinkNodeB('') }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Selecionar investigado...</option>
                  {subjects.map(n => (
                    <option key={n.id} value={n.id}>{n.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Tipo de Relação</label>
                <select
                  value={linkRelType}
                  onChange={e => setLinkRelType(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <optgroup label="Familiar">
                    {RELATIONSHIP_OPTIONS.filter(o => FAMILY_TYPES.has(o.value)).map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Societário / Negócios">
                    <option value="sócio">Sócio / Parceiro de negócios</option>
                  </optgroup>
                  <optgroup label="Outros">
                    <option value="outro">Outra relação</option>
                  </optgroup>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Investigado B</label>
                <select
                  value={linkNodeB}
                  onChange={e => setLinkNodeB(e.target.value)}
                  disabled={!linkNodeA}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
                >
                  <option value="">Selecionar investigado...</option>
                  {subjects.filter(n => n.id !== linkNodeA).map(n => (
                    <option key={n.id} value={n.id}>{n.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Observação <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <input
                  type="text"
                  value={linkCustomLabel}
                  onChange={e => setLinkCustomLabel(e.target.value)}
                  placeholder={`Ex: ${RELATIONSHIP_OPTIONS.find(o => o.value === linkRelType)?.label} confirmado em processo`}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-xs text-gray-400 mt-1">Se não preenchido, usa o tipo de relação como rótulo.</p>
              </div>
            </div>

            {linkNodeA && linkNodeB && (
              <div className="mt-4 bg-indigo-50 rounded-lg px-3 py-2.5 text-xs text-indigo-700">
                <strong>{subjects.find(n => n.id === linkNodeA)?.label}</strong>
                {' '}↔ <strong>{RELATIONSHIP_OPTIONS.find(o => o.value === linkRelType)?.label}</strong>
                {' '}↔ <strong>{subjects.find(n => n.id === linkNodeB)?.label}</strong>
              </div>
            )}

            <div className="flex gap-3 mt-5">
              <button
                onClick={() => {
                  setShowLinkModal(false)
                  setLinkNodeA(''); setLinkNodeB(''); setLinkRelType('cônjuge'); setLinkCustomLabel('')
                }}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-semibold hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleLink}
                disabled={!linkNodeA || !linkNodeB || linkLoading}
                className="flex-1 bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {linkLoading ? 'Criando vínculo...' : 'Criar Vínculo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function GraphCanvas({ nodes, edges, positions, hovered, hoveredConnected, hoveredEdge, setHovered, setHoveredEdge, navigate, onDeleteEdge }: {
  nodes: GraphNodeOut[]
  edges: GraphEdgeOut[]
  positions: Pos
  hovered: string | null
  hoveredConnected: Set<string>
  hoveredEdge: string | null
  setHovered: (id: string | null) => void
  setHoveredEdge: (id: string | null) => void
  navigate: ReturnType<typeof useNavigate>
  onDeleteEdge: (id: string) => void
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
        {/* Edges rendered before nodes so nodes sit on top */}
        {edges.map(e => {
          const a = positions[e.source_id], b = positions[e.target_id]
          if (!a || !b) return null

          const highlighted = edgeIsHighlighted(e)
          const dimmed = hovered !== null && !highlighted
          const isEdgeHovered = hoveredEdge === e.id
          const relType = e.relationship_type || 'auto'
          const isAuto = relType === 'auto'
          const isManual = e.is_manual

          const edgeColor = getEdgeColor(relType, highlighted)
          const strokeWidth = isAuto
            ? (highlighted ? 2 : 1)
            : FAMILY_TYPES.has(relType) ? 2.5 : 2
          const dashArray = isAuto && !highlighted ? '4 3' : undefined
          const strokeOpacity = dimmed ? 0.15 : 1

          const mx = (a.x + b.x) / 2
          const my = (a.y + b.y) / 2

          return (
            <g key={e.id}
              onMouseEnter={() => setHoveredEdge(e.id)}
              onMouseLeave={() => setHoveredEdge(null)}
            >
              {/* Wide invisible hit area for easy hovering */}
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="transparent" strokeWidth={14}
                style={{ cursor: isManual ? 'pointer' : 'default' }} />
              {/* Visible edge line */}
              <line
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={edgeColor}
                strokeWidth={strokeWidth}
                strokeOpacity={strokeOpacity}
                strokeDasharray={dashArray}
              />
              {/* Label: always visible for manual edges; hover-only for auto */}
              {(highlighted || (isManual && !dimmed)) && (
                <text
                  x={mx} y={my - 7}
                  textAnchor="middle" fontSize={9}
                  fill={edgeColor} fontWeight="600"
                  opacity={isEdgeHovered || highlighted ? 1 : 0.65}
                >
                  {e.label}
                </text>
              )}
              {/* Delete button — only on hover for manual edges */}
              {isManual && isEdgeHovered && (
                <g
                  transform={`translate(${mx}, ${my + 8})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onDeleteEdge(e.id)}
                >
                  <circle r={8} fill="white" stroke="#ef4444" strokeWidth={1.5} />
                  <text textAnchor="middle" y={4} fontSize={9} fill="#ef4444" fontWeight="bold">✕</text>
                </g>
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
