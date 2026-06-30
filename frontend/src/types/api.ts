// TypeScript interfaces matching backend Pydantic schemas

// --- Auth & Users ---

export interface UserResponse {
  sub: string
  email: string
  groups: string[]
  tier: 'free' | 'pro' | 'enterprise'
}

export interface MeResponse {
  user: UserResponse | null
  auth_disabled: boolean
}

// --- Resources ---

export interface ResourceResponse {
  id: string
  resource_arn: string
  resource_id: string
  resource_type: string
  service_name: string
  region: string
  account_id: string
  account_name?: string
  created_by?: string
  created_at?: string
  discovered_at?: string
  last_scanned_at?: string
  current_tags?: Record<string, string>
  metadata_json?: Record<string, unknown>
  lifecycle_state?: string
  expires_at?: string
  protected?: boolean
  compliance_status?: string
  // Legacy aliases (kept for compatibility)
  tags?: Record<string, string>
  attributes?: Record<string, unknown>
  updated_at?: string
  // Linked data (populated in detail endpoint)
  recommendations?: { id: string; recommendation_type: string; region_name: string; last_updated?: string; attributes?: Record<string, unknown> }[]
  misconfig_findings?: { id: string; misconfig_id: string; status: string; risk_type?: string; risk_value?: number; scenario?: string; recommendation?: string; evaluation_tier?: string; detected_at?: string }[]
}

export interface ResourceSummary {
  total: number
  by_service: { service_name: string; count: number }[]
  by_region: { region: string; count: number }[]
  by_account: { account_id: string; account_name: string; count: number }[]
}

// --- Recommendations ---

export interface RecommendationNote {
  id: string
  recommendation_id: string
  body: string
  author?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface RecommendationResponse {
  id: string
  unique_id: string
  recommendation_type: string
  region_name: string
  account_id: string
  account_name?: string
  last_updated?: string
  attributes?: Record<string, unknown>
  resource_id?: string
  // Embedded by the backend on list + get. Most-recent first.
  notes?: RecommendationNote[]
}

export interface RecommendationTypeCount {
  recommendation_type: string
  count: number
}

export interface RecommendationSummary {
  total: number
  by_type: RecommendationTypeCount[]
  by_account: { account_id: string; account_name: string; count: number }[]
  by_region: { region: string; count: number }[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// --- Accounts ---

export interface AccountResponse {
  id: string
  account_id: string
  account_name: string
  account_email?: string
  role_arn?: string
  enabled_for_discovery?: boolean
  access_check_status?: string
  last_discovery_at?: string
  total_resources_discovered?: number
  regions?: string[]
  created_at?: string
  updated_at?: string
}

// Lighter account record shape used by the multi-account view.
// Alias of AccountResponse for API compatibility with Tag Manager CLI.
export type AccountRecord = AccountResponse

// --- Multi-Account / StackSet ---

export interface StackInstanceInfo {
  account_id: string
  region: string
  status: string
  status_reason?: string
}

export interface StackSetStatusResponse {
  exists: boolean
  status?: string
  status_reason?: string
  template_version?: string
  versions_match?: boolean
  local_version?: string
  instance_count: number
  instances: StackInstanceInfo[]
}

export interface AccountValidationResponse {
  is_management_account: boolean
  is_delegated_admin: boolean
  can_deploy: boolean
  current_account_id?: string
  management_account_id?: string
  organization_id?: string
  error?: string
  guidance?: string
}

export interface DeployRequest {
  accounts?: string[]
  regions?: string[]
  force_recreate?: boolean
}

// --- CloudFormation Templates ---

export interface TemplateMetadata {
  name: string
  description: string
  public_url?: string
  version?: string
}

export interface TemplateDetail extends TemplateMetadata {
  content: string
}

// --- Generic Jobs (multi-account, delete, etc.) ---

export interface JobResponse {
  id: string
  job_type: string
  status: 'pending' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled'
  progress: number
  progress_message?: string
  progress_data?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  created_at?: string
  started_at?: string
  completed_at?: string
}

export interface JobSubmittedResponse {
  job_id: string
  job_type: string
  status: string
  message: string
}

// --- Scans & Jobs ---

export interface ScanJobResponse {
  id: string
  job_id?: string
  product?: string
  source?: string
  job_type?: string
  status: string
  message?: string
  progress?: number
  progress_message?: string
  progress_data?: ScanJob['progress_data']
  requested_services?: string[]
  services?: string[]
  account_id?: string
  region?: string
  regions?: string[]
  total_resources?: number
  resources_written?: number
  result?: Record<string, unknown>
  errors?: Record<string, unknown>[]
  error?: string
  created_at?: string
  started_at?: string
  completed_at?: string
}

export interface ScanWarning {
  type?: string
  service?: string
  severity?: string
  account_id?: string
  region?: string
  code?: string
  message: string
  suggestion?: string
  action_label?: string
  action_route?: string
}

export interface PermissionErrorDetail {
  type?: string
  service?: string
  region?: string
  account_id?: string
  code?: string
  message?: string
  resource_name?: string
  resource_types?: string[]
  suggestion?: string
}

export interface ScanJob {
  id: string
  product?: string
  source?: string
  job_type?: string
  status: 'pending' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled'
  message?: string
  result?: Record<string, unknown>
  error?: string
  created_at: string
  started_at?: string
  completed_at?: string
  progress?: number
  progress_message?: string
  requested_services?: string[]
  services?: string[]
  account_id?: string
  region?: string
  regions?: string[]
  total_resources?: number
  resources_written?: number
  errors?: Record<string, unknown>[]
  progress_data?: {
    total_resources?: number
    total_jobs?: number
    completed_jobs?: number
    current_service?: string
    current_region?: string
    by_service?: Record<string, number>
    by_region?: Record<string, number>
    account_id?: string
    warnings?: ScanWarning[]
    warnings_count?: number
    errors_count?: number
    permission_errors_count?: number
    permission_error_details?: PermissionErrorDetail[]
    permission_error_resource_types?: string[]
  }
}

export interface ScanHistoryItem {
  id: string
  scan_mode?: string
  collected_by?: string
  product?: string
  source?: string
  job_type?: string
  message?: string
  created_at?: string
  started_at?: string
  completed_at?: string
  status: string
  total_resources?: number
  resources_found?: number
  resources_written?: number
  result?: Record<string, unknown>
  error_message?: string
  error?: string
}

// --- System ---

export interface HealthResponse {
  status: string
  version: string
  timestamp: string
  database: { connected: boolean }
  aws: { connected: boolean; account_id?: string; error?: string }
}

export interface SystemStats {
  resources: number
  recommendations: number
  accounts: number
}

// --- Setup ---

export interface SetupCheckItem {
  name: string
  status: 'ok' | 'warning' | 'error'
  message: string
  details?: Record<string, unknown>
}

export interface SetupValidation {
  ok: boolean
  overall: 'healthy' | 'degraded' | 'unhealthy'
  checks: SetupCheckItem[]
}

export interface IamPolicy {
  Version: string
  Statement: IAMPolicyStatement[]
}

export interface IAMPolicyStatement {
  Sid: string
  Effect: string
  Action: string[] | string
  Resource?: string[] | string
}

// --- Assume Role ---

export interface AssumeRoleConfig {
  id: string
  account_id: string
  account_name?: string
  role_arn: string
  role_name?: string
  external_id?: string
  status?: 'active' | 'inactive' | 'error'
  last_tested?: string
  error_message?: string
}

// Richer record returned by the TM-aligned /configs endpoint
export interface AssumeRoleConfigRecord {
  id: string
  account_id: string
  role_arn: string
  role_name: string
  external_id_configured?: boolean
  is_active: boolean
  enabled: boolean
  alias?: string
  created_at?: string
  updated_at?: string
  last_used_at?: string
}

// Matches backend AssumeRoleStatusResponse from assume_role.py
export interface AssumeRoleStatusResponse {
  configured: boolean
  enabled: boolean
  role_arn?: string
  role_name?: string
  account_id?: string
  external_id_configured: boolean
  last_used_at?: string
  stack_exists: boolean
  stack_status?: string
}

// Legacy alias (kept for backward compatibility)
export interface AssumeRoleStatus {
  configured: boolean
  configs: AssumeRoleConfig[]
}

// --- Context ---

export interface ContextInfo {
  account_id: string
  account_name: string
  region: string
  role_arn?: string
}

export interface AccountContextResponse {
  id?: string
  account_id?: string
  account_alias?: string
  aws_profile?: string
  region?: string
  user_arn?: string
  is_current: boolean
  created_at?: string
  last_used_at?: string
}

export interface AccountContextListResponse {
  contexts: AccountContextResponse[]
  current_account_id?: string
}

export interface ContextGateResponse {
  status: 'ok' | 'first_run' | 'switch_required' | 'add_required' | 'new_context' | 'mismatch' | 'error'
  message: string
  context?: AccountContextResponse
}

export interface ServicePermissionStatus {
  available: boolean
  missing?: string[]
}

export interface FeatureStatus {
  available: boolean
  partial?: boolean
  missing?: string[]
  services?: Record<string, ServicePermissionStatus>
  reason?: string
  note?: string
}

export interface UpgradePath {
  next_tier: string
  action: string
  unlocks: string[]
}

export interface PermissionStatusResponse {
  account_id?: string
  tier: string
  features: Record<string, FeatureStatus>
  checked_at?: string
  expires_at?: string
  upgrade_path?: UpgradePath
}

// --- Misconfig ---

export interface MisconfigDashboard {
  total_open: number
  total_acknowledged: number
  total_resolved: number
  total_suppressed: number
  by_severity: { risk_value: number; count: number }[]
  by_service: { service: string; count: number }[]
  by_tier: { tier: string; count: number }[]
}

export interface MisconfigFinding {
  id: string
  policy_id?: string
  misconfig_id: string
  status: string
  risk_type?: string
  risk_value?: number
  scenario?: string
  recommendation?: string
  resource_id?: string
  resource_arn?: string
  resource_type?: string
  service_name?: string
  evaluation_tier?: string
  evaluation_details?: string
  detected_at?: string
}

export interface MisconfigFindingGroup {
  misconfig_id: string
  scenario: string
  recommendation?: string
  service_name: string
  risk_type: string
  risk_value: number
  total_findings: number
  confirmed_count: number
  advisory_count: number
  account_count: number
  region_count: number
  resource_type_count: number
  accounts: string[]
  regions: string[]
  resource_types: string[]
  latest_detected_at?: string
  sample_finding_id?: string
}

export interface MisconfigFindingGroupsResponse {
  items: MisconfigFindingGroup[]
  total: number
  limit: number
}

export interface MisconfigPolicy {
  id: string
  name: string
  description?: string
  enabled: boolean
  risk_types?: string[]
  min_risk_value?: number
  misconfig_ids?: string[]
  resource_types?: string[]
  resources_flagged?: number
  last_scanned_at?: string
  created_at?: string
}

export interface MisconfigCatalogItem {
  id: string
  service_name?: string
  scenario?: string
  risk_detail?: string
  risk_value?: number
  recommendation_action?: string
  recommendation_description_detailed?: string
  evaluation_criteria?: string
  support_level?: 'executable' | 'mapped' | 'unsupported'
  selectable?: boolean
  supported?: boolean
  has_evaluator?: boolean
  resource_types?: string[]
  support_reason?: string
}

export interface MisconfigCatalogResponse {
  items: MisconfigCatalogItem[]
  total: number
  services: string[]
  risk_types: string[]
  support_summary?: {
    executable: number
    mapped: number
    unsupported: number
  }
}

// --- Frameworks ---

export interface FrameworkPillarCoverage {
  id: string
  label: string
  catalog_count: number
  executable_count: number
  open_findings: number
}

export interface FrameworkMappingCount {
  id: string
  label: string
  external_ref_key: string
  catalog_count: number
  explicit_count: number
  inferred_count: number
  open_findings: number
}

export interface FrameworkScanContextRow {
  key: string
  label?: string
  count: number
}

export interface FrameworkScanContext {
  resource_total: number
  account_count: number
  region_count: number
  service_count: number
  by_service: FrameworkScanContextRow[]
  by_region: FrameworkScanContextRow[]
  by_account: FrameworkScanContextRow[]
  status: 'available' | 'unavailable'
  error?: string
}

export interface FrameworkCoverage {
  status: 'available' | 'unmapped'
  catalog_total: number
  mapped_catalog_total: number
  unmapped_catalog_total: number
  unassigned_mapped_total: number
  open_findings_total: number
  pillars: FrameworkPillarCoverage[]
  frameworks: FrameworkMappingCount[]
  scan_context: FrameworkScanContext
}

export interface FrameworkControl {
  catalog_id: string
  title: string
  service?: string
  risk_detail?: string
  risk_value?: number | null
  executable: boolean
  support_status?: 'executable' | 'planned' | 'unsupported'
  support_reason?: string | null
  pillars: string[]
  external_refs: Record<string, string[]>
  mapping_source?: 'explicit' | 'inferred' | 'none'
  mapping_sources?: Record<string, 'explicit' | 'inferred' | 'none'>
  open_findings: number
}

export interface FrameworkControlsResponse {
  items: FrameworkControl[]
  total: number
  limit: number
}

export interface FrameworkPolicyPack {
  id: string
  pillar: string
  name: string
  description: string
  catalog_count: number
  executable_count: number
  planned_count?: number
  unsupported_count?: number
  open_findings: number
  misconfig_ids: string[]
  enabled: boolean
  misconfig_policy_id?: string | null
  resources_flagged: number
  last_scanned_at?: string | null
}

export interface FrameworkPoliciesResponse {
  items: FrameworkPolicyPack[]
  total: number
}

// --- AI Chat ---

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  tool_calls?: unknown[]
  tokens?: { input: number; output: number }
}

export interface ConversationSummary {
  id: string
  title: string
  model: string
  message_count: number
  updated_at: string
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tool_calls?: unknown[]
  tokens?: { input: number; output: number }
  created_at: string
}

export interface ChatStreamEvent {
  type: 'text' | 'tool_call' | 'tool_result' | 'suggestions' | 'done' | 'error'
  content: unknown
}

// --- Alarms ---

export interface NotificationTarget {
  type: 'slack' | 'sns' | 'email'
  value: string
  label?: string
}

export interface AlarmResponse {
  id: string
  name: string
  description?: string
  trigger_type: 'recommendation' | 'misconfig' | 'both'
  recommendation_types: string[]
  misconfig_ids: string[]
  resource_types: string[]
  account_ids: string[]
  regions: string[]
  severity_filter?: string
  threshold: number
  notification_targets: NotificationTarget[]
  enabled: boolean
  last_evaluated_at?: string
  last_triggered_at?: string
  last_match_count: number
  trigger_count: number
  created_at?: string
  updated_at?: string
  created_by?: string
}

export interface AlarmCreate {
  name: string
  description?: string
  trigger_type: 'recommendation' | 'misconfig' | 'both'
  recommendation_types: string[]
  misconfig_ids: string[]
  resource_types: string[]
  account_ids: string[]
  regions: string[]
  severity_filter?: string
  threshold: number
  notification_targets: NotificationTarget[]
  enabled: boolean
}

export type AlarmUpdate = Partial<AlarmCreate>

export interface AlarmEventResponse {
  id: string
  alarm_id: string
  triggered_at: string
  match_count: number
  match_sample?: Record<string, unknown>[]
  notification_sent: boolean
  notification_error?: string
}

export interface AlarmEvaluateResponse {
  alarm_id: string
  evaluated_at: string
  match_count: number
  threshold: number
  triggered: boolean
  event_id?: string
  notification_status?: string
}

export interface AlarmOptions {
  recommendation_types: string[]
  misconfig_ids: string[]
  account_ids: string[]
  regions: string[]
  resource_types: string[]
  severities: string[]
  notification_types: string[]
}

export interface ProductNotification {
  id: string
  source: string
  event_key: string
  severity: string
  title: string
  message?: string
  payload?: Record<string, unknown>
  notification_sent: boolean
  notification_error?: string
  created_at?: string
  sent_at?: string
}

// --- Infrastructure Status ---

export interface StackSetSummary {
  name: string
  component: string
  status: string
  instance_count: number
  healthy_count: number
  failed_count: number
  version?: string
}

export interface StackInfo {
  stack_name: string
  stack_type: string
  component: string
  status: string
  region: string
  last_updated?: string
  version?: string
  outputs?: Record<string, unknown>
}

export interface ResourceGroupInfo {
  exists: boolean
  name: string
  arn?: string
  resource_count: number
  error?: string
}

export interface InfrastructureHealthSummary {
  total_stacksets: number
  total_instances: number
  total_stacks: number
  healthy: number
  degraded: number
  failed: number
  overall_status: string
}

export interface InfrastructureStatusResponse {
  health: InfrastructureHealthSummary
  stacksets: StackSetSummary[]
  stacks: StackInfo[]
  resource_group: ResourceGroupInfo
  account_id?: string
  organization_id?: string
  region?: string
  local_version?: string
}

export interface EventTrackingInstanceStatus {
  account_id: string
  region: string
  status: string
  queue_url: string
  queue_arn: string
  stack_id?: string
  last_polled_at?: string
  last_event_at?: string
  messages_processed: number
  events_today: number
  error_message?: string
}

export interface EventTrackingStatusResponse {
  stackset_exists: boolean
  stackset_status: string
  instances: EventTrackingInstanceStatus[]
  service_running: boolean
  service_paused: boolean
  total_queues: number
  active_queues: number
}

export interface NotificationEvent {
  id: string
  source: string
  event_key: string
  severity: string
  title: string
  message?: string
  payload: Record<string, unknown>
  notification_sent: boolean
  notification_error?: string
  created_at?: string
  sent_at?: string
}
