import type {
  AdminUser,
  AnswerMap,
  Answer,
  AuditEntry,
  DecisionRequest,
  Model,
  Protocol,
  Question,
  RequestStatus,
  RequestSummary,
  User,
} from '@/types/api'

export interface AdminModel extends Model {
  assigned_count?: number
  created_at?: number
}

export interface ModelForm {
  name: string
  display_name: string
  protocol: Protocol | 'both'
  context_window: number
  description: string
  sort_order: number
  enabled: boolean
}

export interface OperatorsResponse {
  operators: AdminUser[]
}

export interface ModelsResponse {
  models: AdminModel[]
}

export interface UserKeyInfo {
  id: string
  name: string
  prefix: string
  last_four: string
  created_at: number
  last_used_at: number | null
  revoked_at: number | null
}

export interface UserUsageRow {
  model: string
  n: number
}

export interface UserRecentRow {
  id: string
  model: string
  protocol: Protocol
  status: RequestStatus
  created_at: number
  duration_ms: number | null
  auto_filled: number
}

export interface UserDetailResponse {
  user: User
  usage: UserUsageRow[]
  keys: UserKeyInfo[]
  recent: UserRecentRow[]
}

export interface RequestDetailResponse {
  request: DecisionRequest
  server_time: number
}

export interface AuditResponse {
  logs: AuditEntry[]
  total: number
}

export interface DraftResponse {
  draft: AnswerMap
}

export interface RandomizeResponse {
  answers: AnswerMap
}

export interface AnswerResponse {
  request: DecisionRequest
}

export type DraftState = 'clean' | 'dirty' | 'saving' | 'saved' | 'error'

export interface QuestionLike {
  id: string
  type: string
  display?: { instructions?: string; criteria?: { key: string; label: string; description: string }[] }
}

export interface ActiveRequest extends RequestSummary {
  answers?: AnswerMap | null
  input?: unknown
}

export type AnswerValue = Answer | undefined
