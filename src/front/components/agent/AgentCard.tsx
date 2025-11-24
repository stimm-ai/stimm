import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Agent } from './types'

interface AgentCardProps {
  agent: Agent
  isDefault: boolean
  onSetDefault: (agentId: string) => void
  onDelete: (agentId: string) => void
}

export function AgentCard({ agent, isDefault, onSetDefault, onDelete }: AgentCardProps) {
  return (
    <Card className={isDefault ? 'border-green-200 bg-green-50' : ''}>
      <CardHeader className="relative">
        <CardTitle className="flex items-center justify-between">
          <span>{agent.name}</span>
          {isDefault && (
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Default
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm text-muted-foreground">
          {agent.description || 'No description'}
        </div>

        {agent.llm_provider && (
          <div className="bg-white p-3 rounded-lg border-l-4 border-blue-500">
            <div className="font-medium text-blue-600">LLM: {agent.llm_provider}</div>
            <div className="text-xs text-gray-600 mt-1">
              Model: {agent.llm_config?.model || 'Default'}
              {agent.llm_config?.api_key && <><br />API Key: ••••••••</>}
            </div>
          </div>
        )}

        {agent.tts_provider && (
          <div className="bg-white p-3 rounded-lg border-l-4 border-purple-500">
            <div className="font-medium text-purple-600">TTS: {agent.tts_provider}</div>
            <div className="text-xs text-gray-600 mt-1">
              Voice: {agent.tts_config?.voice || 'Default'}
              {agent.tts_config?.api_key && <><br />API Key: ••••••••</>}
            </div>
          </div>
        )}

        {agent.stt_provider && (
          <div className="bg-white p-3 rounded-lg border-l-4 border-orange-500">
            <div className="font-medium text-orange-600">STT: {agent.stt_provider}</div>
            <div className="text-xs text-gray-600 mt-1">
              Model: {agent.stt_config?.model || 'Default'}
              {agent.stt_config?.api_key && <><br />API Key: ••••••••</>}
            </div>
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" size="sm" asChild>
            <a href={`/agent/edit/${agent.id}`}>Edit</a>
          </Button>
          {!isDefault && (
            <Button variant="secondary" size="sm" onClick={() => onSetDefault(agent.id)}>
              Set Default
            </Button>
          )}
          <Button variant="destructive" size="sm" onClick={() => onDelete(agent.id)}>
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}