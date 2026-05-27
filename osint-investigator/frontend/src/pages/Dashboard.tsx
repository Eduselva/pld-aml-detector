import { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Investigation } from '../types'
import StatusBadge from '../components/StatusBadge'

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function RiskScoreCell({ score, level }: { score?: number | null; level?: string | null }) {
  if (score === null || score === undefined) {
    return <span className="text-gray-400 text-sm">—</span>
  }
  const colorMap: Record<string, string> = {
    low: 'text-green-700 bg-green-50',
    medium: 'text-yellow-700 bg-yellow-50',
    high: 'text-orange-700 bg-orange-50',
    critical: 'text-red-700 bg-red-50',
  }
  const cls = colorMap[level || 'low'] || 'text-gray-700 bg-gray-50'
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-sm font-bold ${cls}`}>
      {Math.round(score)}
    </span>
  )
}

function formatEntityId(type: string, id?: string | null) {
  if (!id) return '—'
  if (type === 'cpf') {
    const d = id.replace(/\D/g, '')
    if (d.length === 11) {
      return `${d.slice(0,3)}.${d.slice(3,6)}.${d.slice(6,9)}-${d.slice(9)}`
    }
  } else if (type === 'cnpj') {
    const d = id.replace(/\D/g, '')
    if (d.length === 14) {
      return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12)}`
    }
  }
  return id
}

export default function Dashboard() {
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const fetchInvestigations = useCallback(async () => {
    try {
      const data = await api.listInvestigations()
      setInvestigations(data.investigations)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInvestigations()
  }, [fetchInvestigations])

  // Auto-refresh if any investigation is running
  useEffect(() => {
    const hasRunning = investigations.some(
      (i) => i.status === 'running' || i.status === 'pending'
    )
    if (!hasRunning) return
    const interval = setInterval(fetchInvestigations, 5000)
    return () => clearInterval(interval)
  }, [investigations, fetchInvestigations])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('Deseja excluir esta investigação?')) return
    try {
      await api.deleteInvestigation(id)
      await fetchInvestigations()
    } catch (err) {
      alert('Erro ao excluir investigação')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">OSINT Investigador</h1>
            <p className="text-sm text-gray-500 mt-0.5">Plataforma de Inteligência Financeira</p>
          </div>
          <Link
            to="/investigacoes/nova"
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors shadow-sm"
          >
            <span>+</span>
            Nova Investigação
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats bar */}
        <div className="flex items-center gap-6 mb-6">
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3 shadow-sm">
            <p className="text-xs text-gray-500">Total</p>
            <p className="text-2xl font-bold text-gray-900">{total}</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3 shadow-sm">
            <p className="text-xs text-gray-500">Em andamento</p>
            <p className="text-2xl font-bold text-blue-600">
              {investigations.filter(i => i.status === 'running' || i.status === 'pending').length}
            </p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 px-4 py-3 shadow-sm">
            <p className="text-xs text-gray-500">Risco alto/crítico</p>
            <p className="text-2xl font-bold text-red-600">
              {investigations.filter(i => i.risk_level === 'high' || i.risk_level === 'critical').length}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-gray-500">
            <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-3"></div>
            <p>Carregando investigações...</p>
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-600 font-medium">{error}</p>
            <button onClick={fetchInvestigations} className="mt-3 text-blue-600 hover:underline text-sm">
              Tentar novamente
            </button>
          </div>
        ) : investigations.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
            <p className="text-4xl mb-4">🔍</p>
            <p className="text-gray-600 font-medium text-lg">Nenhuma investigação encontrada</p>
            <p className="text-gray-400 text-sm mt-1">Crie sua primeira investigação OSINT</p>
            <Link
              to="/investigacoes/nova"
              className="inline-block mt-4 bg-blue-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-blue-700"
            >
              Nova Investigação
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Nome</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Tipo</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Documento</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Data</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Status</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Score</th>
                  <th className="text-right px-5 py-3 font-semibold text-gray-600">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {investigations.map((inv) => (
                  <tr
                    key={inv.id}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => inv.status === 'complete' && navigate(`/investigacoes/${inv.id}/relatorio`)}
                  >
                    <td className="px-5 py-3.5 font-medium text-gray-900">
                      {inv.entity_name || inv.nickname || inv.entity_id || '—'}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="uppercase text-xs font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                        {inv.entity_type}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-gray-600 font-mono text-xs">
                      {formatEntityId(inv.entity_type, inv.entity_id)}
                    </td>
                    <td className="px-5 py-3.5 text-gray-500">{formatDate(inv.created_at)}</td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={inv.status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <RiskScoreCell score={inv.risk_score} level={inv.risk_level} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {inv.status === 'complete' && (
                          <Link
                            to={`/investigacoes/${inv.id}/relatorio`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-blue-600 hover:underline text-xs font-medium"
                          >
                            Ver relatório
                          </Link>
                        )}
                        <button
                          onClick={(e) => handleDelete(inv.id, e)}
                          className="text-red-500 hover:text-red-700 text-xs"
                          title="Excluir"
                        >
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
