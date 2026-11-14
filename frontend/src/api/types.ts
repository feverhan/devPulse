export type Platform = 'gitea' | 'gitee'
export type PeriodType = 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'custom'

export interface Repo {
  id: number
  name: string
  project: string
  platform: Platform
  owner: string
  repo: string
  base_url: string
  token_set: boolean
  enabled: boolean
  include_keywords: string
  exclude_keywords: string
  last_sync_at: string | null
  last_sync_status: string
  last_sync_message: string
  created_at: string
}

export interface RepoPayload {
  name: string
  project: string
  platform: Platform
  owner: string
  repo: string
  base_url: string
  repo_url: string
  token: string
  enabled: boolean
  include_keywords: string
  exclude_keywords: string
}

export interface Commit {
  id: number
  repo_id: number
  repo_name: string
  sha: string
  short_sha: string
  message: string
  author_name: string
  author_email: string
  author_login: string
  url: string
  additions: number
  deletions: number
  changed_files: number
  committed_at: string
}

export interface Project {
  id: number | null
  name: string
  source: string
  note: string
  repos: number
  commits: number
  works: number
}

export interface WorkEntry {
  id: number
  work_date: string
  title: string
  content: string
  category: string
  project: string
  tags: string
  hours: number | null
  created_at: string
  updated_at: string
}

export interface WorkPayload {
  work_date: string
  title: string
  content: string
  category: string
  project: string
  tags: string
  hours: number | null
}

export interface ReportStats {
  project_count: number
  commit_count: number
  work_count: number
  hours: number
  additions: number
  deletions: number
  changed_files: number
  repo_count: number
  active_days: number
  by_repo: Array<{ name: string; count: number; additions: number; deletions: number }>
  by_project: Array<{ name: string; commits: number; works: number }>
  by_category: Array<{ name: string; count: number }>
  by_day: Array<{ date: string; count: number }>
}

export interface Report {
  id: number
  title: string
  period_type: PeriodType
  start_date: string
  end_date: string
  summary: string
  content: string
  stats: ReportStats | null
  model: string
  status: string
  created_at: string
  updated_at: string
}

export interface ReviewTask {
  id: number
  repo_id: number
  repo_name: string
  status: string
  limit: number
  only_new: boolean
  total: number
  processed: number
  finding_count: number
  model: string
  message: string
  created_at: string | null
  updated_at: string | null
  finished_at: string | null
}

export interface ReviewFinding {
  id: number
  review_id: number
  file_path: string
  line: number
  severity: string
  category: string
  title: string
  detail: string
  status: string
  issue_number: number | null
  issue_url: string
  created_at: string | null
}

export interface CodeReview {
  id: number
  task_id: number | null
  repo_id: number
  repo_name: string
  commit_sha: string
  short_sha: string
  commit_subject: string
  commit_url: string
  author_name: string
  status: string
  finding_count: number
  model: string
  message: string
  created_at: string | null
  findings: ReviewFinding[]
}

export interface Monitor {
  id: number
  name: string
  url: string
  health_path: string
  method: string
  expect_status: number
  keyword: string
  interval_minutes: number
  timeout: number
  enabled: boolean
  alert_enabled: boolean
  last_status: string
  last_check_at: string | null
  next_check_at: string | null
  last_latency_ms: number
  last_error: string
  fail_count: number
  total_checks: number
  uptime: number
  created_at: string | null
}

export interface MonitorPayload {
  name: string
  url: string
  health_path: string
  method: string
  expect_status: number
  keyword: string
  interval_minutes: number
  timeout: number
  enabled: boolean
  alert_enabled: boolean
}

export interface MonitorCheck {
  id: number
  status: string
  status_code: number
  latency_ms: number
  error: string
  checked_at: string | null
}

export interface MonitorOverview {
  total: number
  ok: number
  fail: number
  pending: number
  avg_latency_ms: number
  monitors: Monitor[]
}

export interface ProbeResult {
  path: string
  url: string
  ok: boolean
  status: number | null
  latency_ms: number
  error: string
}

export interface ActivityItem {
  kind: 'commit' | 'report' | 'review'
  text: string
  meta: string
  time: string
}

export interface Overview {
  repo_count: number
  commit_total: number
  commit_today: number
  commit_week: number
  commit_week_prev: number
  work_total: number
  work_week: number
  hours_week: number
  report_count: number
  project_count: number
  monitor_total: number
  monitor_ok: number
  monitor_fail: number
  review_count: number
  finding_total: number
  finding_pending: number
  review_running: number
  total_additions: number
  total_deletions: number
  llm_ready: boolean
  llm_model: string
  last_sync_at: string | null
  trend: Array<{ date: string; count: number }>
  by_repo: Array<{ name: string; count: number; additions: number; deletions: number }>
  by_project: Array<{ name: string; count: number }>
  recent_commits: Array<{
    id: number
    repo_name: string
    short_sha: string
    subject: string
    author_name: string
    committed_at: string
  }>
  recent_reports: Array<{
    id: number
    title: string
    period_type: PeriodType
    finding_count: number
    created_at: string
  }>
  recent_reviews: Array<{
    id: number
    repo_id: number
    short_sha: string
    subject: string
    status: string
    finding_count: number
    created_at: string
  }>
  activity: ActivityItem[]
}

export interface LLMConfig {
  base_url: string
  api_key_set: boolean
  model: string
  temperature: number
}

export interface AppSettings {
  llm: LLMConfig
  sync_interval_minutes: number
  fetch_commit_files: boolean
  max_pages_per_sync: number
  my_authors: string[]
  wechat_webhook: string
  app_password_set: boolean
}

export interface SetupStep {
  key: string
  title: string
  done: boolean
  detail: string
}

export interface SetupStatus {
  initialized: boolean
  database: { driver: string; target: string; source: string }
  steps: SetupStep[]
}

export interface Paged<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}