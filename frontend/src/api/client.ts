import type {
  HealthResponse,
  ProjectBudgetSummary,
  ProjectDetail,
  ProjectWorkItem,
  WorkBudgetSummary,
  WorkEquipmentLink,
  WorkMaterialLink,
} from './types'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
const apiBaseUrl = (configuredBaseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new ApiError('API хүсэлт амжилтгүй боллоо.', response.status)
    }

    return (await response.json()) as T
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error
    }

    throw new ApiError('API сервертэй холбогдож чадсангүй.')
  }
}

const projectPath = (projectId: string) =>
  `/api/v1/projects/${encodeURIComponent(projectId)}`

const workPath = (projectId: string, workId: string) =>
  `${projectPath(projectId)}/work-items/${encodeURIComponent(workId)}`

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>('/health')
}

export function getProject(projectId: string): Promise<ProjectDetail> {
  return getJson<ProjectDetail>(projectPath(projectId))
}

export function getProjectBudgetSummary(
  projectId: string,
): Promise<ProjectBudgetSummary> {
  return getJson<ProjectBudgetSummary>(`${projectPath(projectId)}/budget-summary`)
}

export function getProjectWorkItems(
  projectId: string,
): Promise<ProjectWorkItem[]> {
  return getJson<ProjectWorkItem[]>(`${projectPath(projectId)}/work-items`)
}

export function getWorkBudgetSummary(
  projectId: string,
  workId: string,
): Promise<WorkBudgetSummary> {
  return getJson<WorkBudgetSummary>(`${workPath(projectId, workId)}/summary`)
}

export function getWorkMaterials(
  projectId: string,
  workId: string,
): Promise<WorkMaterialLink[]> {
  return getJson<WorkMaterialLink[]>(`${workPath(projectId, workId)}/materials`)
}

export function getWorkEquipment(
  projectId: string,
  workId: string,
): Promise<WorkEquipmentLink[]> {
  return getJson<WorkEquipmentLink[]>(`${workPath(projectId, workId)}/equipment`)
}
