import { useEffect, useState, useCallback, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { DossierReport, Investigation } from '../types'
import RiskGauge from '../components/RiskGauge'
import AlertBadge from '../components/AlertBadge'
import SourceCard from '../components/SourceCard'
import StatusBadge from '../components/StatusBadge'

const SOURCE_META: Record<string, { label: string; icon: string }> = {
  cnpj:              { label: 'CNPJ / Receita Federal',       icon: '🏢' },
  qsa_search:        { label: 'Vínculos Societários',          icon: '🤝' },
  negative_media:    { label: 'Mídias Negativas',              icon: '📰' },
  restrictive_lists: { label: 'Listas PEP/OFAC',               icon: '🚫' },
  transparency_gov:  { label: 'Portal da Transparência',       icon: '🏛️' },
  gazettes:          { label: 'Diários Oficiais',              icon: '📜' },
  court_records:     { label: 'Processos Judiciais (DataJud)', icon: '⚖️' },
  social_linkedin:   { label: 'LinkedIn',                      icon: '💼' },
  social_instagram:  { label: 'Instagram',                     icon: '📷' },
  social_twitter:    { label: 'Twitter / X',                   icon: '🐦' },
  social_tiktok:     { label: 'TikTok',                        icon: '🎵' },
  social_facebook:   { label: 'Facebook',                      icon: '👥' },
  social_pinterest:  { label: 'Pinterest',                     icon: '📌' },
  social_flickr:     { label: 'Flickr',                        icon: '🖼️' },
  hibp:              { label: 'Vazamentos (HIBP)',              icon: '📧' },
}

const SOURCE_ORDER = Object.keys(SOURCE_META)

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatEntityId(type: string, id?: string | null) {
  if (!id) return '—'
  const d = id.replace(/\D/g, '')
  if (type === 'cpf' && d.length === 11)
    return `${d.slice(0,3)}.${d.slice(3,6)}.${d.slice(6,9)}-${d.slice(9)}`
  if (type === 'cnpj' && d.length === 14)
    return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12)}`
  return id
}

function ScoreBreakdown({ score }: { score: NonNullable<DossierReport['risk_score']> }) {
  const items = [
    { label: 'Governo / Transparência', value: score.government, weight: '20%' },
    { label: 'Mídias Negativas',        value: score.media,      weight: '25%' },
    { label: 'Listas Restritivas',      value: score.lists,      weight: '15%' },
    { label: 'Processos Judiciais',     value: score.legal,      weight: '10%' },
    { label: 'Corporativo / QSA',       value: score.corporate,  weight: '15%' },
    { label: 'Redes Sociais',           value: score.social,     weight: '10%' },
    { label: 'E-mail',                  value: score.email,      weight: '5%' },
  ]
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <h3 className="font-semibold text-gray-700 mb-4 text-sm uppercase tracking-wide">Detalhamento do Score</h3>
      <div className="space-y-3">
        {items.map(({ label, value, weight }) => {
          const barColor =
            value <= 25 ? 'bg-green-500' :
            value <= 50 ? 'bg-yellow-500' :
            value <= 75 ? 'bg-orange-500' : 'bg-red-500'
          return (
            <div key={label}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-600">{label} <span className="text-gray-400">({weight})</span></span>
                <span className="font-bold text-gray-800">{Math.round(value)}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${barColor} transition-all`}
                  style={{ width: `${Math.min(value, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
        <span className="text-sm font-bold text-gray-700">Score Final</span>
        <span className="text-lg font-extrabold text-gray-900">{Math.round(score.total)}</span>
      </div>
    </div>
  )
}

function SourceFilter({
  sources,
  visible,
  onChange,
}: {
  sources: string[]
  visible: Set<string>
  onChange: (name: string) => void
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Fontes visíveis no relatório
      </h3>
      <div className="flex flex-wrap gap-2">
        {sources.map((name) => {
          const meta = SOURCE_META[name] || { label: name, icon: '🔍' }
          const checked = visible.has(name)
          return (
            <button
              key={name}
              type="button"
              onClick={() => onChange(name)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                checked
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'
              }`}
            >
              {meta.icon} {meta.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function Report() {
  const { id } = useParams<{ id: string }>()
  const [investigation, setInvestigation] = useState<Investigation | null>(null)
  const [report, setReport] = useState<DossierReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleSources, setVisibleSources] = useState<Set<string>>(new Set(SOURCE_ORDER))
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async () => {
    if (!id) return
    try {
      const inv = await api.getInvestigation(id)
      setInvestigation(inv)
      if (inv.status === 'complete' || inv.status === 'failed') {
        if (pollRef.current) clearInterval(pollRef.current)
        if (inv.status === 'complete') {
          const rep = await api.getReport(id)
          setReport(rep)
          // Initialize filter with all returned sources visible
          setVisibleSources(new Set(rep.sources.map((s) => s.source_name)))
        }
      }
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar relatório')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchData()
    pollRef.current = setInterval(fetchData, 3000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [fetchData])

  const toggleSource = (name: string) => {
    setVisibleSources((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 font-medium">Carregando dados da investigação...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-600 font-medium mb-3">{error}</p>
          <Link to="/dashboard" className="text-blue-600 hover:underline">← Voltar ao painel</Link>
        </div>
      </div>
    )
  }

  if (!investigation) return null

  const isRunning = investigation.status === 'pending' || investigation.status === 'running'
  const entityLabel = investigation.entity_type === 'apelido'
    ? 'Apelido'
    : investigation.entity_type.toUpperCase()
  const entityIdFormatted = formatEntityId(investigation.entity_type, investigation.entity_id)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="text-gray-400 hover:text-gray-600 transition-colors text-sm">
              ← Voltar
            </Link>
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                {investigation.entity_name || investigation.nickname || entityIdFormatted}
              </h1>
              <p className="text-xs text-gray-500">
                {entityLabel}
                {entityIdFormatted !== '—' && ` · ${entityIdFormatted}`}
                {investigation.nickname && investigation.entity_name && ` · apelido: ${investigation.nickname}`}
                {investigation.email && ` · ${investigation.email}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={investigation.status} />
            {investigation.status === 'complete' && (
              <button
                className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
                onClick={() => window.print()}
              >
                📄 Exportar PDF
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {isRunning && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-6 flex items-center gap-4">
            <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
            <div>
              <p className="font-semibold text-blue-800">Investigação em andamento</p>
              <p className="text-sm text-blue-600 mt-0.5">Coletando dados de múltiplas fontes em paralelo. Aguarde...</p>
            </div>
          </div>
        )}

        {investigation.status === 'failed' && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
            <p className="font-semibold text-red-800">Investigação falhou</p>
            {investigation.error_message && (
              <p className="text-sm text-red-600 mt-1">{investigation.error_message}</p>
            )}
          </div>
        )}

        {report && (
          <div className="space-y-6">
            {/* Score */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 flex flex-col items-center justify-center">
                {report.risk_score ? (
                  <>
                    <p className="text-xs font-semibold uppercase text-gray-500 tracking-wide mb-2">Score de Risco</p>
                    <RiskGauge score={report.risk_score.total} level={report.risk_score.level} size={180} />
                    <p className="text-xs text-gray-400 mt-2">Investigado em {formatDate(report.created_at)}</p>
                  </>
                ) : (
                  <p className="text-gray-400">Score não disponível</p>
                )}
              </div>
              <div className="md:col-span-2">
                {report.risk_score && <ScoreBreakdown score={report.risk_score} />}
              </div>
            </div>

            {/* Alerts */}
            {report.alerts.length > 0 && (
              <div>
                <h2 className="text-base font-bold text-gray-800 mb-3">
                  Alertas Principais ({report.alerts.length})
                </h2>
                <div className="space-y-2">
                  {report.alerts.slice(0, 10).map((alert, i) => (
                    <AlertBadge key={i} severity={alert.severity} message={alert.message} source={alert.source} />
                  ))}
                </div>
              </div>
            )}

            {/* Source filter */}
            <SourceFilter
              sources={[...report.sources]
                .sort((a, b) => {
                  const ia = SOURCE_ORDER.indexOf(a.source_name)
                  const ib = SOURCE_ORDER.indexOf(b.source_name)
                  return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
                })
                .map((s) => s.source_name)}
              visible={visibleSources}
              onChange={toggleSource}
            />

            {/* Sources */}
            <div>
              <h2 className="text-base font-bold text-gray-800 mb-3">Fontes de Dados</h2>
              <div className="space-y-3">
                {[...report.sources]
                  .sort((a, b) => {
                    const ia = SOURCE_ORDER.indexOf(a.source_name)
                    const ib = SOURCE_ORDER.indexOf(b.source_name)
                    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
                  })
                  .filter((s) => visibleSources.has(s.source_name))
                  .map((source) => (
                    <SourceCard key={source.source_name} source={source} />
                  ))}
                {[...report.sources].filter((s) => visibleSources.has(s.source_name)).length === 0 && (
                  <p className="text-sm text-gray-400 text-center py-6">
                    Nenhuma fonte selecionada. Use os filtros acima para exibir os resultados.
                  </p>
                )}
              </div>
            </div>

            <p className="text-xs text-gray-400 text-center pb-4">
              Relatório gerado em {formatDate(report.created_at)} · OSINT Investigador v1.1
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
