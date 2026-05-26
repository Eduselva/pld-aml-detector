export type InvestigationStatus = 'pending' | 'running' | 'complete' | 'failed'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'
export type EntityType = 'cpf' | 'cnpj' | 'apelido'
export type AlertSeverity = 'info' | 'warning' | 'danger' | 'critical'

export interface Investigation {
  id: string
  created_at: string
  updated_at: string
  status: InvestigationStatus
  entity_type: EntityType
  entity_id: string
  entity_name: string
  email?: string | null
  phone?: string | null
  nickname?: string | null
  risk_score?: number | null
  risk_level?: RiskLevel | null
  error_message?: string | null
}

export interface InvestigationListResponse {
  investigations: Investigation[]
  total: number
}

export interface InvestigationCreate {
  entity_name: string
  entity_type: EntityType
  entity_id?: string | null
  email?: string
  phone?: string | null
  nickname?: string | null
}

export interface RiskScore {
  total: number
  level: RiskLevel
  corporate: number
  media: number
  lists: number
  social: number
  email: number
}

export interface Alert {
  severity: AlertSeverity
  message: string
  source: string
}

export interface SourceFinding {
  source_name: string
  status: string
  findings?: Record<string, unknown> | null
  risk_contribution: number
  collected_at?: string | null
  error_message?: string | null
}

export interface DossierReport {
  investigation_id: string
  entity_name: string
  entity_type: EntityType
  entity_id: string
  email?: string | null
  status: InvestigationStatus
  created_at: string
  risk_score?: RiskScore | null
  alerts: Alert[]
  sources: SourceFinding[]
}
