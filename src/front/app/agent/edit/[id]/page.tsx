import { AgentEditPage } from '@/components/agent/AgentEditPage'

interface PageProps {
  params: Promise<{
    id: string
  }>
}

export default async function AgentEdit({ params }: PageProps) {
  const resolvedParams = await params
  return <AgentEditPage agentId={resolvedParams.id} />
}