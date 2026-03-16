export type IntelItem = {
  id: number;
  org_id: number;
  indicator_type: string;
  value: string;
  tags: string[];
  source: string;
  timestamp: string;
  confidence: number;
  severity: number;
  credibility: number;
  context_text: string;
  evidence: string;
  classification: string;
  classification_labels: string[];
  model_confidence: number;
  predicted_probs: Record<string, number>;
  explanation_terms: string[];
  visibility: string;
  shared_from_org_id?: number | null;
  created_at: string;
};

export type FeedResponse = {
  items: IntelItem[];
  total: number;
};

export type SimilarIntel = {
  id: number;
  org_id: number;
  value: string;
  indicator_type: string;
  distance: number;
};

export type Contributor = {
  id: number;
  name: string;
  org_id: number;
  reputation: number;
  role: string;
};

export type IngestionSource = {
  id: number;
  name: string;
  source_kind: string;
  org_id: number;
  contributor_id?: number | null;
  enabled: boolean;
  interval_minutes: number;
  max_rows: number;
  config: Record<string, unknown>;
  last_polled_at?: string | null;
  last_success_at?: string | null;
  last_status: string;
  last_error?: string | null;
  last_created_count: number;
  created_at: string;
  updated_at: string;
};

export type IngestionRun = {
  id: number;
  source_id: number;
  org_id: number;
  status: string;
  trigger: string;
  task_id?: string | null;
  created_count: number;
  error_message?: string | null;
  started_at: string;
  finished_at?: string | null;
};

export type FederationPolicy = {
  id: number;
  from_org_id: number;
  to_org_id: number;
  min_credibility: number;
  min_reputation: number;
  enabled: boolean;
};

export type AdminUser = {
  id: number;
  name: string;
  org_id: number;
  role: string;
  reputation: number;
  is_active: boolean;
  key_rotated_at?: string | null;
  created_at: string;
};

export type AdminOverview = {
  org_id: number;
  org_name: string;
  user_count: number;
  contributor_count: number;
  source_count: number;
  source_enabled_count: number;
  source_error_count: number;
  recent_run_count: number;
  policy_count: number;
  active_intel_count: number;
  critical_intel_count: number;
  avg_credibility: number;
  avg_severity: number;
  ready: boolean;
  generated_at: string;
};

export type SourceReliabilityRow = {
  id: number;
  pattern: string;
  reliability: number;
  weight: number;
  enabled: boolean;
  notes: string;
};
