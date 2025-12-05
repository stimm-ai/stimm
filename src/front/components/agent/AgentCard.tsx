import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Agent } from './types'
import { THEME, getProviderAccent } from '@/lib/theme'
import { Edit, Star, Trash2 } from 'lucide-react'

interface AgentCardProps {
  agent: Agent
  isDefault: boolean
  onSetDefault: (agentId: string) => void
  onDelete: (agentId: string) => void
}

export function AgentCard({ agent, isDefault, onSetDefault, onDelete }: AgentCardProps) {
  return (
    <div
      className={`
        ${THEME.card.base} ${THEME.card.hover} 
        ${isDefault ? THEME.card.selected : ''}
        p-5 transition-all duration-300
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold mb-1 flex items-center gap-2">
            {agent.name}
            {isDefault && (
              <Star className={`w-4 h-4 ${THEME.accent.cyan} fill-current`} />
            )}
          </h3>
          <p className={`text-sm ${THEME.text.muted}`}>
            {agent.description || 'No description'}
          </p>
        </div>
      </div>

      {/* Provider Info */}
      <div className="space-y-3 mb-4">
        {agent.llm_provider && (
          <div className={`p-3 rounded-lg ${getProviderAccent('llm').bg} border ${getProviderAccent('llm').border}`}>
            <div className={`font-semibold text-sm ${getProviderAccent('llm').text} mb-1`}>
              LLM: {agent.llm_provider.toUpperCase()}
            </div>
            <div className={`text-xs ${THEME.text.secondary}`}>
              {agent.llm_config?.model || 'Default model'}
            </div>
          </div>
        )}

        {agent.tts_provider && (
          <div className={`p-3 rounded-lg ${getProviderAccent('tts').bg} border ${getProviderAccent('tts').border}`}>
            <div className={`font-semibold text-sm ${getProviderAccent('tts').text} mb-1`}>
              TTS: {agent.tts_provider.toUpperCase()}
            </div>
            <div className={`text-xs ${THEME.text.secondary}`}>
              {agent.tts_config?.voice || 'Default voice'}
            </div>
          </div>
        )}

        {agent.stt_provider && (
          <div className={`p-3 rounded-lg ${getProviderAccent('stt').bg} border ${getProviderAccent('stt').border}`}>
            <div className={`font-semibold text-sm ${getProviderAccent('stt').text} mb-1`}>
              STT: {agent.stt_provider.toUpperCase()}
            </div>
            <div className={`text-xs ${THEME.text.secondary}`}>
              {agent.stt_config?.model || 'Default model'}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap pt-3 border-t border-white/10">
        <Button
          variant="outline"
          size="sm"
          asChild
          className={`${THEME.button.ghost} rounded-full flex-1`}
        >
          <a href={`/agent/edit/${agent.id}`} className="flex items-center gap-2 justify-center">
            <Edit className="w-3 h-3" />
            Edit
          </a>
        </Button>

        {!isDefault && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSetDefault(agent.id)}
            className={`${THEME.button.secondary} rounded-full flex-1`}
          >
            <Star className="w-3 h-3 mr-1" />
            Set Default
          </Button>
        )}

        <Button
          variant="destructive"
          size="sm"
          onClick={() => onDelete(agent.id)}
          className={`${THEME.button.danger} rounded-full`}
        >
          <Trash2 className="w-3 h-3" />
        </Button>
      </div>
    </div>
  )
}