export interface Agent {
  id: string
  name: string
  description?: string
  system_prompt?: string
  rag_config_id?: string
  llm_provider?: string
  llm_config?: {
    model?: string
    api_key?: string
  }
  tts_provider?: string
  tts_config?: {
    voice?: string
    model?: string
    api_key?: string
  }
  stt_provider?: string
  stt_config?: {
    model?: string
    api_key?: string
  }
}

export interface AgentResponse {
  agents: Agent[]
  default_agent?: Agent
}