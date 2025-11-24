'use client'

import { AgentEditPage } from '@/components/agent/AgentEditPage'

export default function AgentCreatePage() {
  // No agentId: AgentEditPage runs in "create" mode
  return <AgentEditPage />
}