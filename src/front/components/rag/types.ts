export interface RagConfig {
  id: string;
  name: string;
  description?: string;
  provider_type: string;
  provider: string;
  provider_config: Record<string, any>;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RagConfigListResponse {
  configs: RagConfig[];
  total: number;
}
