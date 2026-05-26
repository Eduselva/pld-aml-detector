import type { RiskLevel } from '../types'

interface Props {
  score: number
  level: RiskLevel
  size?: number
}

function getColor(level: RiskLevel): { stroke: string; text: string; label: string } {
  switch (level) {
    case 'low':
      return { stroke: '#22c55e', text: 'text-green-600', label: 'Baixo' }
    case 'medium':
      return { stroke: '#eab308', text: 'text-yellow-600', label: 'Médio' }
    case 'high':
      return { stroke: '#f97316', text: 'text-orange-600', label: 'Alto' }
    case 'critical':
      return { stroke: '#ef4444', text: 'text-red-600', label: 'Crítico' }
  }
}

export default function RiskGauge({ score, level, size = 160 }: Props) {
  const { stroke, text, label } = getColor(level)
  const radius = 54
  const strokeWidth = 10
  const circumference = 2 * Math.PI * radius
  // Only draw 270 degrees (¾ of the circle) for a gauge look
  const arcLength = circumference * 0.75
  const dashOffset = arcLength - (score / 100) * arcLength
  const center = size / 2
  const rotation = 135  // start at bottom-left

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform={`rotate(${rotation}, ${center}, ${center})`}
        />
        {/* Foreground arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          transform={`rotate(${rotation}, ${center}, ${center})`}
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
        {/* Score text */}
        <text
          x={center}
          y={center - 6}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.22}
          fontWeight="700"
          fill={stroke}
        >
          {Math.round(score)}
        </text>
        {/* Level label */}
        <text
          x={center}
          y={center + 18}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.1}
          fontWeight="500"
          fill="#6b7280"
        >
          {label}
        </text>
      </svg>
    </div>
  )
}
