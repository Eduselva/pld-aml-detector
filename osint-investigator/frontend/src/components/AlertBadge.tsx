import type { AlertSeverity } from '../types'

interface Props {
  severity: AlertSeverity
  message: string
  source?: string
}

const severityConfig: Record<AlertSeverity, { bg: string; border: string; text: string; icon: string }> = {
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    icon: 'ℹ',
  },
  warning: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-300',
    text: 'text-yellow-800',
    icon: '⚠',
  },
  danger: {
    bg: 'bg-orange-50',
    border: 'border-orange-300',
    text: 'text-orange-800',
    icon: '⚡',
  },
  critical: {
    bg: 'bg-red-50',
    border: 'border-red-300',
    text: 'text-red-800',
    icon: '🚨',
  },
}

export default function AlertBadge({ severity, message, source }: Props) {
  const cfg = severityConfig[severity] || severityConfig.info
  return (
    <div className={`flex items-start gap-2 rounded-lg border px-4 py-3 ${cfg.bg} ${cfg.border}`}>
      <span className="text-lg leading-none mt-0.5 select-none">{cfg.icon}</span>
      <div>
        <p className={`text-sm font-medium ${cfg.text}`}>{message}</p>
        {source && (
          <p className={`text-xs mt-0.5 opacity-70 ${cfg.text}`}>Fonte: {source}</p>
        )}
      </div>
    </div>
  )
}
