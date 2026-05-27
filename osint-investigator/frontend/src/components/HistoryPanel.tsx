import { useState } from 'react'
import type { HistoryEntry } from '../types'

const LEVEL_COLOR: Record<string, string> = {
  low: 'text-green-700 bg-green-50 border-green-200',
  medium: 'text-yellow-700 bg-yellow-50 border-yellow-200',
  high: 'text-orange-700 bg-orange-50 border-orange-200',
  critical: 'text-red-700 bg-red-50 border-red-200',
}
const LEVEL_LABEL: Record<string, string> = {
  low: 'Baixo', medium: 'Médio', high: 'Alto', critical: 'Crítico',
}
const SEV_COLOR: Record<string, string> = {
  critical: 'text-red-700', danger: 'text-orange-600', warning: 'text-yellow-600', info: 'text-blue-600',
}

const SOURCE_LABEL: Record<string, string> = {
  corporate: 'Corporativo', media: 'Mídias', lists: 'Listas',
  government: 'Governo', legal: 'Processos', social: 'Social', email: 'E-mail',
  cnpj: 'CNPJ', qsa_search: 'QSA', negative_media: 'Mídias', gazettes: 'Diários',
  restrictive_lists: 'Listas', transparency_gov: 'Transparência',
  court_records: 'Processos', hibp: 'HIBP',
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function ScoreDelta({ prev, curr }: { prev: number; curr: number }) {
  const delta = Math.round(curr - prev)
  if (Math.abs(delta) < 1) return <span className="text-gray-400 text-xs">sem alteração</span>
  const up = delta > 0
  return (
    <span className={`text-xs font-bold ${up ? 'text-red-600' : 'text-green-600'}`}>
      {up ? '▲' : '▼'} {Math.abs(delta)} pts
    </span>
  )
}

function DiffPanel({ prev, curr }: { prev: HistoryEntry; curr: HistoryEntry }) {
  const prevMessages = new Set(prev.alerts.map(a => a.message))
  const currMessages = new Set(curr.alerts.map(a => a.message))

  const newAlerts = curr.alerts.filter(a => !prevMessages.has(a.message))
  const resolvedAlerts = prev.alerts.filter(a => !currMessages.has(a.message))

  const allSources = new Set([
    ...Object.keys(prev.source_scores),
    ...Object.keys(curr.source_scores),
  ])
  const changedSources = [...allSources]
    .map(src => ({
      src,
      prev: prev.source_scores[src] ?? 0,
      curr: curr.source_scores[src] ?? 0,
      delta: (curr.source_scores[src] ?? 0) - (prev.source_scores[src] ?? 0),
    }))
    .filter(s => Math.abs(s.delta) >= 5)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))

  const hasChanges = newAlerts.length > 0 || resolvedAlerts.length > 0 || changedSources.length > 0

  return (
    <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-gray-700">Score</span>
        <span className="text-sm text-gray-500">
          {Math.round(prev.risk_score ?? 0)} → {Math.round(curr.risk_score ?? 0)}
        </span>
        <ScoreDelta prev={prev.risk_score ?? 0} curr={curr.risk_score ?? 0} />
      </div>

      {!hasChanges && (
        <p className="text-xs text-gray-400">Nenhuma alteração significativa em relação à investigação anterior.</p>
      )}

      {newAlerts.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Novos alertas ({newAlerts.length})</p>
          <ul className="space-y-1">
            {newAlerts.map((a, i) => (
              <li key={i} className={`text-xs flex gap-1.5 ${SEV_COLOR[a.severity] || 'text-gray-600'}`}>
                <span>＋</span><span>{a.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {resolvedAlerts.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Alertas resolvidos ({resolvedAlerts.length})</p>
          <ul className="space-y-1">
            {resolvedAlerts.map((a, i) => (
              <li key={i} className="text-xs text-gray-400 flex gap-1.5 line-through">
                <span>✓</span><span>{a.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {changedSources.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Fontes com variação</p>
          <div className="flex flex-wrap gap-2">
            {changedSources.map(({ src, prev: p, curr: c, delta }) => (
              <span key={src} className={`text-xs px-2 py-0.5 rounded-full border font-medium
                ${delta > 0 ? 'bg-red-50 border-red-200 text-red-700' : 'bg-green-50 border-green-200 text-green-700'}`}>
                {SOURCE_LABEL[src] || src}: {Math.round(p)} → {Math.round(c)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface Props {
  currentId: string
  entries: HistoryEntry[]
}

export default function HistoryPanel({ currentId, entries }: Props) {
  const [open, setOpen] = useState(false)
  const [compareIdx, setCompareIdx] = useState<number | null>(null)

  if (entries.length <= 1) return null

  const currentEntry = entries.find(e => e.id === currentId)!
  const otherEntries = entries.filter(e => e.id !== currentId)
  const selectedCompare = compareIdx !== null ? otherEntries[compareIdx] : otherEntries[0]

  return (
    <div className="bg-white rounded-xl border border-indigo-200 shadow-sm overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">🕑</span>
          <div className="text-left">
            <span className="font-semibold text-gray-800">Histórico de Investigações</span>
            <span className="ml-2 text-xs text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded-full">
              {otherEntries.length} anterior{otherEntries.length > 1 ? 'es' : ''}
            </span>
          </div>
        </div>
        <span className={`text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-gray-100">
          {/* Timeline */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Linha do tempo</p>
            <div className="space-y-2">
              {entries.map((entry, idx) => {
                const isCurrent = entry.id === currentId
                const level = entry.risk_level || 'low'
                return (
                  <div key={entry.id}
                    className={`flex items-center justify-between rounded-lg px-3 py-2 border text-sm
                      ${isCurrent ? 'border-indigo-300 bg-indigo-50' : 'border-gray-100 bg-gray-50'}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        level === 'critical' ? 'bg-red-500' :
                        level === 'high' ? 'bg-orange-400' :
                        level === 'medium' ? 'bg-yellow-400' : 'bg-green-400'
                      }`} />
                      <span className="text-gray-600 text-xs">{formatDate(entry.created_at)}</span>
                      {isCurrent && <span className="text-xs text-indigo-600 font-medium">← atual</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      {idx > 0 && <ScoreDelta prev={entries[idx - 1].risk_score ?? 0} curr={entry.risk_score ?? 0} />}
                      <span className={`text-xs font-bold px-2 py-0.5 rounded border ${LEVEL_COLOR[level] || ''}`}>
                        {Math.round(entry.risk_score ?? 0)} — {LEVEL_LABEL[level] || level}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Comparison selector */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Comparar com investigação anterior
              </p>
              {otherEntries.length > 1 && (
                <select
                  className="text-xs border border-gray-200 rounded px-2 py-1 text-gray-600"
                  value={compareIdx ?? 0}
                  onChange={e => setCompareIdx(Number(e.target.value))}
                >
                  {otherEntries.map((e, i) => (
                    <option key={e.id} value={i}>{formatDate(e.created_at)}</option>
                  ))}
                </select>
              )}
            </div>
            <DiffPanel prev={selectedCompare} curr={currentEntry} />
          </div>
        </div>
      )}
    </div>
  )
}
