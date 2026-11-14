import http from './client'
import type {
  AppSettings,
  CodeReview,
  Commit,
  Overview,
  Paged,
  PeriodType,
  Project,
  Repo,
  RepoPayload,
  Monitor,
  MonitorCheck,
  MonitorOverview,
  MonitorPayload,
  ProbeResult,
  Report,
  ReviewTask,
  SetupStatus,
  WorkEntry,
  WorkPayload,
} from './types'

export const repoApi = {
  list: () => http.get<Repo[]>('/repos').then((r) => r.data),
  create: (payload: RepoPayload) => http.post<Repo>('/repos', payload).then((r) => r.data),
  update: (id: number, payload: Partial<RepoPayload>) =>
    http.put<Repo>(`/repos/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/repos/${id}`).then((r) => r.data),
  sync: (id: number) => http.post(`/repos/${id}/sync`).then((r) => r.data),
  syncAll: () => http.post('/repos/sync').then((r) => r.data),
  test: (id: number) => http.post(`/repos/${id}/test`).then((r) => r.data),
  probe: (payload: RepoPayload) =>
    http
      .post<{ ok: boolean; user: string; detected_platform: string; message: string }>('/repos/probe', payload)
      .then((r) => r.data),
}

export const commitApi = {
  authors: () =>
    http
      .get<Array<{ author_name: string; author_email: string; author_login: string; count: number }>>(
        '/commits/authors',
      )
      .then((r) => r.data),
  list: (params: {
    repo_id?: number | null
    keyword?: string
    author?: string
    start_date?: string | null
    end_date?: string | null
    page?: number
    page_size?: number
  }) => http.get<Paged<Commit>>('/commits', { params }).then((r) => r.data),
}

export const setupApi = {
  status: () => http.get<SetupStatus>('/setup/status').then((r) => r.data),
  setDatabase: (database_url: string) =>
    http.post<SetupStatus>('/setup/database', { database_url }).then((r) => r.data),
  setLlm: (payload: { base_url: string; api_key: string; model: string; temperature: number }) =>
    http.post<SetupStatus>('/setup/llm', payload).then((r) => r.data),
  setPassword: (password: string) =>
    http.post<SetupStatus>('/setup/password', { password }).then((r) => r.data),
  exportUrl: '/api/setup/export',
  importData: (payload: Record<string, unknown>) =>
    http.post<{ counts: Record<string, number> }>('/setup/import', { payload }).then((r) => r.data),
  migrate: (payload: { from_url?: string; to_url?: string }) =>
    http.post<SetupStatus & { migrated: Record<string, number> }>('/setup/migrate', payload).then((r) => r.data),
  resetDatabaseSource: () =>
    http.post<SetupStatus>('/setup/reset-database-source').then((r) => r.data),
  complete: () => http.post<SetupStatus>('/setup/complete').then((r) => r.data),
  reset: () => http.post<SetupStatus>('/setup/reset').then((r) => r.data),
}

export const projectApi = {
  list: () => http.get<Project[]>('/projects').then((r) => r.data),
  create: (payload: { name: string; note?: string }) =>
    http.post<Project>('/projects', payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/projects/${id}`).then((r) => r.data),
}

export const workApi = {
  list: (params: {
    keyword?: string
    category?: string
    project?: string
    start_date?: string | null
    end_date?: string | null
    page?: number
    page_size?: number
  }) => http.get<Paged<WorkEntry>>('/works', { params }).then((r) => r.data),
  create: (payload: WorkPayload) => http.post<WorkEntry>('/works', payload).then((r) => r.data),
  update: (id: number, payload: Partial<WorkPayload>) =>
    http.put<WorkEntry>(`/works/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/works/${id}`).then((r) => r.data),
}

export const reportApi = {
  list: (params: { period_type?: PeriodType | null; keyword?: string; page?: number; page_size?: number }) =>
    http.get<Paged<Report>>('/reports', { params }).then((r) => r.data),
  get: (id: number) => http.get<Report>(`/reports/${id}`).then((r) => r.data),
  generate: (payload: {
    period_type: PeriodType
    start_date?: string | null
    end_date?: string | null
    reference_date?: string | null
    title?: string
    focus?: string
    include_commits?: boolean
    include_works?: boolean
    use_llm?: boolean
  }) => http.post<Report>('/reports/generate', payload).then((r) => r.data),
  update: (id: number, payload: Partial<Pick<Report, 'title' | 'summary' | 'content' | 'status'>>) =>
    http.put<Report>(`/reports/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/reports/${id}`).then((r) => r.data),
}

export const monitorApi = {
  list: () => http.get<Monitor[]>('/monitors').then((r) => r.data),
  overview: () => http.get<MonitorOverview>('/monitors/overview').then((r) => r.data),
  create: (payload: MonitorPayload) => http.post<Monitor>('/monitors', payload).then((r) => r.data),
  update: (id: number, payload: MonitorPayload) =>
    http.put<Monitor>(`/monitors/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/monitors/${id}`).then((r) => r.data),
  probe: (payload: { url: string; use_llm?: boolean }) =>
    http
      .post<{ base_url: string; suggested: string[]; results: ProbeResult[]; available: ProbeResult[] }>(
        '/monitors/probe',
        payload,
      )
      .then((r) => r.data),
  check: (id: number) =>
    http.post<{ status: string; status_code: number; latency_ms: number; error: string; alert: string }>(
      `/monitors/${id}/check`,
    ).then((r) => r.data),
  history: (id: number) => http.get<MonitorCheck[]>(`/monitors/${id}/checks`).then((r) => r.data),
}

export const reviewApi = {
  createTask: (payload: { repo_id: number; limit?: number; only_new?: boolean }) =>
    http.post<ReviewTask>('/reviews/tasks', payload).then((r) => r.data),
  listTasks: (limit?: number) =>
    http.get<ReviewTask[]>('/reviews/tasks', { params: { limit: limit ?? 30 } }).then((r) => r.data),
  getTask: (id: number) => http.get<ReviewTask>(`/reviews/tasks/${id}`).then((r) => r.data),
  cancelTask: (id: number) => http.post<ReviewTask>(`/reviews/tasks/${id}/cancel`).then((r) => r.data),
  list: (params: { repo_id?: number | null; task_id?: number | null; limit?: number }) =>
    http.get<CodeReview[]>('/reviews', { params }).then((r) => r.data),
  get: (id: number) => http.get<CodeReview>(`/reviews/${id}`).then((r) => r.data),
  run: (payload: { repo_id: number; limit?: number; only_new?: boolean }) =>
    http
      .post<{ total: number; results: Array<Record<string, unknown>> }>('/reviews/run', payload)
      .then((r) => r.data),
  pushIssues: (id: number) =>
    http.post<{ created: number; failed: number }>(`/reviews/${id}/issues`).then((r) => r.data),
  ignoreFinding: (findingId: number) =>
    http.post(`/reviews/findings/${findingId}/ignore`).then((r) => r.data),
  remove: (id: number) => http.delete(`/reviews/${id}`).then((r) => r.data),
}

export const settingsApi = {
  get: () => http.get<AppSettings>('/settings').then((r) => r.data),
  save: (payload: Record<string, unknown>) => http.put<AppSettings>('/settings', payload).then((r) => r.data),
  testLlm: () => http.post<{ ok: boolean; reply: string; model: string }>('/settings/llm/test').then((r) => r.data),
}

export const dashboardApi = {
  overview: () => http.get<Overview>('/dashboard/overview').then((r) => r.data),
}