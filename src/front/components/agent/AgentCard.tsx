import { Button } from '@/components/ui/button';
import { Agent } from './types';
import { THEME } from '@/lib/theme';
import { Edit, Star, Trash2 } from 'lucide-react';

interface AgentCardProps {
  agent: Agent;
  isDefault: boolean;
  onSetDefault: (agentId: string) => void;
  onDelete: (agentId: string) => void;
}

export function AgentCard({
  agent,
  isDefault,
  onSetDefault,
  onDelete,
}: AgentCardProps) {
  return (
    <div
      className={`
        ${THEME.card.base} ${THEME.card.hover} 
        ${isDefault ? THEME.card.selected : ''}
        p-5 transition-all duration-300 flex flex-col h-full
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
      <div className="flex flex-wrap gap-2 mb-4">
        {agent.stt_provider && (
          <span className="text-xs bg-cyan-400/20 px-3 py-1.5 rounded-full border border-cyan-400/30">
            {agent.stt_provider.toUpperCase()}
          </span>
        )}
        {agent.llm_provider && (
          <span className="text-xs bg-purple-400/20 px-3 py-1.5 rounded-full border border-purple-400/30">
            {agent.llm_provider.toUpperCase()}
          </span>
        )}
        {agent.tts_provider && (
          <span className="text-xs bg-orange-400/20 px-3 py-1.5 rounded-full border border-orange-400/30">
            {agent.tts_provider.toUpperCase()}
          </span>
        )}
      </div>

      {/* Actions - pushed to bottom with mt-auto */}
      <div className="flex gap-2 flex-wrap pt-3 border-t border-white/10 mt-auto">
        <Button
          variant="outline"
          size="sm"
          asChild
          className={`${THEME.button.ghost} rounded-full flex-1`}
        >
          <a
            href={`/agent/edit/${agent.id}`}
            className="flex items-center gap-2 justify-center"
          >
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
  );
}
