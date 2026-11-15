export type Protocol = 'systemone' | 'google'
export type QuestionType = 'noul' | 'choice' | 'score'
export type RequestStatus = 'queued' | 'assigned' | 'answered' | 'timed_out' | 'cancelled'
export type Role = 'admin' | 'operator'

export interface SiteConfig {
  site_name: string
  tagline: string
  description: string
  announcement: string
  registration_enabled: boolean
  support_email: string
  sound_default: boolean
  show_register_cta: boolean
  version: string
}

export interface Model {
  id: string
  name: string
  display_name: string
  protocol: Protocol | 'both'
  description: string
  context_window: number
  enabled: boolean
  sort_order: number
  protocols?: Protocol[]
  assigned_count?: number
  created_at?: number
  today?: number
}

export interface User {
  id: string
  email: string
  name: string
  disabled: boolean
  created_at: number
  last_login_at: number | null
  request_count?: number
  last_request_at?: number | null
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: Role
  disabled?: boolean
  models: string[]
  created_at?: number
  last_login_at?: number | null
  last_assigned_at?: number | null
  online?: boolean
  active_requests?: number
}

export interface OperatorSummary {
  id: string
  name: string
  role: Role
  online: boolean
  last_assigned_at: number | null
}

export interface ApiKey {
  id: string
  name: string
  prefix: string
  last_four: string
  masked: string
  created_at: number
  last_used_at: number | null
  revoked_at: number | null
}

export interface QuestionDisplayCriterion {
  key: string
  label: string
  description: string
}

export interface Question {
  id: string
  type: QuestionType
  instructions: unknown
  criteria: unknown
  display: {
    instructions: string
    criteria: QuestionDisplayCriterion[]
  }
}

export interface NoulAnswer {
  type: 'noul'
  noul: number
  confidence?: number
}

export interface ChoiceAnswer {
  type: 'choice'
  choice: string
  probabilities: Record<string, number>
  confidence: number
}

export interface ScoreAnswer {
  type: 'score'
  score: number
  probabilities: Record<string, number>
  confidence: number
  legend?: Record<string, string>
}

export type Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer
export type AnswerMap = Record<string, Answer>

export interface RequestSummary {
  id: string
  model: string
  protocol: Protocol
  status: RequestStatus
  input_text: string
  input_kind: string
  questions: Question[]
  created_at: number
  deadline_at: number
  auto_fill_at: number | null
  timeout_seconds: number
  auto_filled: boolean
  duration_ms: number | null
  error: string | null
  assigned_to: { id: string; name: string | null } | null
  answered_by: { id: string; name: string | null } | null
  answered_count: number
  total_questions: number
  draft?: AnswerMap
  remaining_ms?: number
  notify?: boolean
}

export interface DecisionRequest extends RequestSummary {
  input: unknown
  answers: AnswerMap | null
  user?: User | null
  raw_request?: unknown
}

export interface Page<T> {
  total: number
  limit?: number
  offset?: number
}

export interface RequestList extends Page<RequestSummary> {
  requests: RequestSummary[]
  server_time: number
}

export interface AuditEntry {
  id: string
  actor_kind: string
  actor_id: string | null
  actor_name: string
  action: string
  target: string | null
  detail: unknown
  created_at: number
}

export interface Usage {
  days: number
  total: number
  answered: number
  timed_out: number
  avg_duration_ms: number
  by_model: { model: string; n: number; answered: number }[]
  recent: {
    id: string
    model: string
    protocol: Protocol
    status: RequestStatus
    created_at: number
    duration_ms: number | null
    auto_filled: number
  }[]
}

export interface AdminOverview {
  status_counts: Record<string, number>
  active: number
  queued: number
  assigned: number
  today: { total: number; answered: number; auto_filled: number; timed_out: number }
  average_duration_ms: number
  oldest_pending_ms: number
  models: Model[]
  online_operators: { id: string; name: string; role: Role }[]
  recent: RequestSummary[]
  server_time: number
}

export interface SettingsPayload {
  values: Record<string, string | number | boolean>
  version: string
  limits: Record<string, [number, number]>
}

export interface WsHello {
  admin: AdminUser
  server_time: number
  pending: RequestSummary[]
  presence: OperatorSummary[]
  settings: {
    sound_default: boolean
    timeout_fill_enabled: boolean
    timeout_fill_lead_seconds: number
    admin_receive_all: boolean
  }
}

export type WsEvent =
  | { type: 'hello'; data: WsHello & { notify?: boolean } }
  | { type: 'request.created'; data: { request: DecisionRequest; notify: boolean } }
  | { type: 'request.assigned'; data: { request: DecisionRequest; notify: boolean } }
  | { type: 'request.updated'; data: { request: DecisionRequest; notify: boolean } }
  | { type: 'request.completed'; data: { request: DecisionRequest; notify: boolean } }
  | { type: 'presence'; data: { operators: OperatorSummary[]; notify: boolean } }
  | { type: 'ping'; data: { time: number; notify?: boolean } }

export interface PlaygroundResult {
  request_id: string
  protocol: Protocol
  model: string
  response: unknown
  elapsed_ms: number
}

export interface ApiErrorBody {
  detail?: string | { msg?: string }[] | unknown
  code?: string
  error?: unknown
}

export interface SessionResponse {
  user: User | null
  admin: { id: string; email: string; name: string; role: Role } | null
}

export interface RequestDetailResponse {
  request: DecisionRequest
  server_time: number
}

export interface AnswerResponse {
  request: DecisionRequest
}
