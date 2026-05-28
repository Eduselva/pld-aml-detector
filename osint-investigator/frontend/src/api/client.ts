import type {
  Investigation,
  InvestigationCreate,
  InvestigationListResponse,
  DossierReport,
  InvestigationHistory,
  GraphResponse,
  GraphEdgeOut,
  GraphEdgeCreate,
  Case,
  CaseCreate,
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

  async getGraph(caseId?: string | null): Promise<GraphResponse> {
    const url = caseId ? `/graph?case_id=${encodeURIComponent(caseId)}` : '/graph'
    return request<GraphResponse>(url)
  },

  async createGraphEdge(data: GraphEdgeCreate): Promise<GraphEdgeOut> {
    return request<GraphEdgeOut>('/graph/edges', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async deleteGraphEdge(id: string): Promise<void> {
    return request<void>(`/graph/edges/${id}`, { method: 'DELETE' })
  },

  async listCases(): Promise<Case[]> {
    return request<Case[]>('/cases')
  },

  async createCase(data: CaseCreate): Promise<Case> {
    return request<Case>('/cases', { method: 'POST', body: JSON.stringify(data) })
  },

  async updateCase(id: string, data: { name?: string; description?: string }): Promise<Case> {
    return request<Case>(`/cases/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  },

  async deleteCase(id: string): Promise<void> {
    return request<void>(`/cases/${id}`, { method: 'DELETE' })
  },

  async addInvestigationToCase(caseId: string, invId: string): Promise<void> {
    return request<void>(`/cases/${caseId}/investigations/${invId}`, { method: 'POST' })
  },

  async removeInvestigationFromCase(caseId: string, invId: string): Promise<void> {
    return request<void>(`/cases/${caseId}/investigations/${invId}`, { method: 'DELETE' })
  },
}
