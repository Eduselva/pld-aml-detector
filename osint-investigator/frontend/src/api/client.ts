import type {
  Investigation,
  InvestigationCreate,
  InvestigationListResponse,
  DossierReport,
  InvestigationHistory,
} from '../types'

const BASE_URL = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!res.ok) {
    let errorMsg = `Erro HTTP ${res.status}`
    try {
      const body = await res.json()
      errorMsg = body.detail || errorMsg
    } catch {
      // ignore JSON parse error
    }
    throw new Error(errorMsg)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return res.json() as Promise<T>
}

export const api = {
  async createInvestigation(data: InvestigationCreate): Promise<Investigation> {
    return request<Investigation>('/investigations', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async listInvestigations(skip = 0, limit = 50): Promise<InvestigationListResponse> {
    return request<InvestigationListResponse>(`/investigations?skip=${skip}&limit=${limit}`)
  },

  async getInvestigation(id: string): Promise<Investigation> {
    return request<Investigation>(`/investigations/${id}`)
  },

  async getReport(id: string): Promise<DossierReport> {
    return request<DossierReport>(`/investigations/${id}/report`)
  },

  async deleteInvestigation(id: string): Promise<void> {
    return request<void>(`/investigations/${id}`, { method: 'DELETE' })
  },

  async getHistory(id: string): Promise<InvestigationHistory> {
    return request<InvestigationHistory>(`/investigations/${id}/history`)
  },
}
