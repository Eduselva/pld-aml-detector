import { useState, type JSX } from 'react'
import type { SourceFinding } from '../types'

interface Props {
  source: SourceFinding
}

const sourceLabels: Record<string, string> = {
  cnpj: 'Dados Corporativos (CNPJ)',
  negative_media: 'Mídias Negativas',
  restrictive_lists: 'Listas Restritivas (PEP/OFAC)',
  social_linkedin: 'LinkedIn',
  social_instagram: 'Instagram',
  social_twitter: 'Twitter/X',
  social_tiktok: 'TikTok',
  hibp: 'Inteligência de E-mail (HIBP)',
}

const sourceIcons: Record<string, string> = {
  cnpj: '🏢',
  negative_media: '📰',
  restrictive_lists: '🚫',
  social_linkedin: '💼',
  social_instagram: '📷',
  social_twitter: '🐦',
  social_tiktok: '🎵',
  hibp: '📧',
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score <= 25 ? 'bg-green-500' :
    score <= 50 ? 'bg-yellow-500' :
    score <= 75 ? 'bg-orange-500' :
    'bg-red-500'
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span>Risco</span>
      <div className="w-24 bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${color}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className="font-medium text-gray-700">{Math.round(score)}</span>
    </div>
  )
}

function CNPJData({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-2 text-sm">
      {data.razao_social && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Razão Social</span>
          <span className="font-medium">{String(data.razao_social)}</span>
        </div>
      )}
      {data.situacao_cadastral && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Situação</span>
          <span className={`font-medium ${String(data.situacao_cadastral).includes('ATIVA') ? 'text-green-700' : 'text-red-700'}`}>
            {String(data.situacao_cadastral)}
          </span>
        </div>
      )}
      {data.data_inicio_atividade && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Abertura</span>
          <span>{String(data.data_inicio_atividade)}</span>
        </div>
      )}
      {data.atividade_principal && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Atividade</span>
          <span>{String(data.atividade_principal)}</span>
        </div>
      )}
      {data.municipio && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Município</span>
          <span>{data.municipio as string}/{data.uf as string}</span>
        </div>
      )}
      {data.capital_social !== undefined && (
        <div className="grid grid-cols-2 gap-x-4">
          <span className="text-gray-500">Capital Social</span>
          <span>R$ {Number(data.capital_social).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
        </div>
      )}
      {Array.isArray(data.socios) && data.socios.length > 0 && (
        <div className="mt-3">
          <p className="text-gray-500 mb-1">Sócios ({(data.socios as unknown[]).length})</p>
          <ul className="space-y-1">
            {(data.socios as Array<{ nome: string; qualificacao: string }>).map((s, i) => (
              <li key={i} className="text-xs bg-gray-50 rounded px-2 py-1">
                <span className="font-medium">{s.nome}</span>
                {s.qualificacao && <span className="text-gray-500"> — {s.qualificacao}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function MediaData({ data }: { data: Record<string, unknown> }) {
  const results = (data.results as Array<{ title: string; snippet: string; url: string }>) || []
  if (results.length === 0) {
    return <p className="text-sm text-gray-500">Nenhum resultado encontrado.</p>
  }
  return (
    <div className="space-y-3">
      {results.map((r, i) => (
        <div key={i} className="border-l-2 border-gray-200 pl-3">
          <a
            href={r.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-blue-600 hover:underline line-clamp-2"
          >
            {r.title}
          </a>
          {r.snippet && <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{r.snippet}</p>}
        </div>
      ))}
    </div>
  )
}

function ListsData({ data }: { data: Record<string, unknown> }) {
  const matches = (data.matches as Array<{ list: string; name: string; reason: string; role?: string; match_score: number; match_type: string }>) || []
  if (matches.length === 0) {
    return <p className="text-sm text-green-700 font-medium">Sem correspondências em listas restritivas.</p>
  }
  return (
    <div className="space-y-2">
      {matches.map((m, i) => (
        <div key={i} className="bg-red-50 border border-red-200 rounded p-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-bold text-red-700">{m.list}</span>
            <span className="text-xs text-red-500">Similaridade: {(m.match_score * 100).toFixed(0)}% ({m.match_type})</span>
          </div>
          <p className="text-gray-800 font-medium mt-1">{m.name}</p>
          {m.role && <p className="text-xs text-gray-600">Cargo: {m.role}</p>}
          <p className="text-xs text-gray-600">{m.reason}</p>
        </div>
      ))}
    </div>
  )
}

function SocialData({ data }: { data: Record<string, unknown> }) {
  const profiles = (data.found_profiles as Array<{ username: string; url: string; platform: string }>) || []
  // For LinkedIn format
  const linkedinProfiles = (data.profiles as Array<{ title: string; url: string; snippet: string }>) || []

  if (profiles.length === 0 && linkedinProfiles.length === 0) {
    return <p className="text-sm text-gray-500">Nenhum perfil encontrado.</p>
  }

  return (
    <div className="space-y-2">
      {linkedinProfiles.map((p, i) => (
        <div key={i} className="flex items-start gap-2 text-sm">
          <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">
            {p.title}
          </a>
          {p.snippet && <p className="text-xs text-gray-500">{p.snippet}</p>}
        </div>
      ))}
      {profiles.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
            @{p.username}
          </a>
          <span className="text-gray-500 text-xs">({p.platform})</span>
        </div>
      ))}
    </div>
  )
}

function HIBPData({ data }: { data: Record<string, unknown> }) {
  const breaches = (data.breaches as Array<{ name: string; title: string; breach_date: string; pwn_count: number; data_classes: string[] }>) || []
  if (breaches.length === 0) {
    return (
      <p className="text-sm text-green-700 font-medium">
        {data.skipped ? 'E-mail não fornecido.' : 'Nenhum vazamento encontrado.'}
      </p>
    )
  }
  return (
    <div className="space-y-2">
      {breaches.map((b, i) => (
        <div key={i} className="bg-orange-50 border border-orange-200 rounded p-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-semibold">{b.title || b.name}</span>
            <span className="text-xs text-gray-500">{b.breach_date}</span>
          </div>
          {b.data_classes?.length > 0 && (
            <p className="text-xs text-gray-600 mt-0.5">
              Dados: {b.data_classes.slice(0, 4).join(', ')}
              {b.data_classes.length > 4 && ` +${b.data_classes.length - 4}`}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

function SourceBody({ source }: { source: SourceFinding }) {
  const data = (source.findings?.data as Record<string, unknown>) || {}
  const summary = (source.findings?.summary as string) || ''

  if (source.status === 'failed') {
    return (
      <div className="text-sm text-red-600">
        <p className="font-medium">Falha na coleta</p>
        {source.error_message && <p className="text-xs mt-1 text-gray-500">{source.error_message}</p>}
      </div>
    )
  }

  if (summary) {
    const components: Record<string, JSX.Element> = {
      cnpj: <CNPJData data={data} />,
      negative_media: <MediaData data={data} />,
      restrictive_lists: <ListsData data={data} />,
      hibp: <HIBPData data={data} />,
    }

    const customComponent = components[source.source_name]
    const isSocial = source.source_name.startsWith('social_')

    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-600 italic">{summary}</p>
        {customComponent}
        {isSocial && <SocialData data={data} />}
      </div>
    )
  }

  return <p className="text-sm text-gray-500">Sem dados disponíveis.</p>
}

export default function SourceCard({ source }: Props) {
  const [open, setOpen] = useState(false)
  const label = sourceLabels[source.source_name] || source.source_name
  const icon = sourceIcons[source.source_name] || '🔍'
  const hasRisk = source.risk_contribution > 0

  return (
    <div className={`rounded-xl border bg-white shadow-sm overflow-hidden ${hasRisk ? 'border-orange-200' : 'border-gray-200'}`}>
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{icon}</span>
          <span className="font-semibold text-gray-800">{label}</span>
        </div>
        <div className="flex items-center gap-4">
          {source.risk_contribution > 0 && (
            <ScoreBar score={source.risk_contribution} />
          )}
          <span className={`text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
        </div>
      </button>
      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-gray-100">
          <SourceBody source={source} />
        </div>
      )}
    </div>
  )
}
