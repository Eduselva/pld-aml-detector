import type { InvestigationStatus } from '../types'

interface Props {
  status: InvestigationStatus
}

const statusConfig: Record<InvestigationStatus, { label: string; className: string }> = {
  pending: {
    label: 'Aguardando',
    className: 'bg-gray-100 text-gray-700 border border-gray-200',
  },
  running: {
    label: 'Em andamento',
    className: 'bg-blue-100 text-blue-700 border border-blue-200 animate-pulse',
  },
  complete: {
    label: 'Concluída',
    className: 'bg-green-100 text-green-700 border border-green-200',
  },
  failed: {
    label: 'Falhou',
    className: 'bg-red-100 text-red-700 border border-red-200',
  },
}

export default function StatusBadge({ status }: Props) {
  const config = statusConfig[status] || statusConfig.pending
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
