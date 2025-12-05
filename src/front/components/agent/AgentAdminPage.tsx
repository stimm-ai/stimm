'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { PageLayout } from '@/components/ui/PageLayout'
import { NavigationBar } from '@/components/ui/NavigationBar'
import { AgentGrid } from './AgentGrid'
import { AgentCard } from './AgentCard'
import { Agent } from './types'
import { Bot, Plus, Mic } from 'lucide-react'
import { THEME } from '@/lib/theme'

export function AgentAdminPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [defaultAgent, setDefaultAgent] = useState<Agent | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch agents from FastAPI backend
      const response = await fetch('http://localhost:8001/api/agents/')
      if (!response.ok) {
        throw new Error(`Failed to load agents: ${response.statusText}`)
      }

      const agents = await response.json()
      setAgents(agents || [])

      // Fetch default agent separately
      const defaultResponse = await fetch('http://localhost:8001/api/agents/default/current/')
      if (defaultResponse.ok) {
        const defaultAgent = await defaultResponse.json()
        setDefaultAgent(defaultAgent)
      } else {
        setDefaultAgent(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  const handleSetDefault = async (agentId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/agents/${agentId}/set-default/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error('Failed to set default agent')
      }

      await loadAgents() // Reload to get updated default agent
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default agent')
    }
  }

  const handleDelete = async (agentId: string) => {
    if (!confirm('Are you sure you want to delete this agent? This action cannot be undone.')) {
      return
    }

    try {
      const response = await fetch(`http://localhost:8001/api/agents/${agentId}/`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete agent')
      }

      await loadAgents() // Reload to reflect deletion
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete agent')
    }
  }

  if (loading) {
    return (
      <PageLayout title="Agent Management" icon={<Bot className="w-8 h-8" />}>
        <NavigationBar />
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
            <p className={THEME.text.secondary}>Loading agents...</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="Agent Management"
      icon={<Bot className="w-8 h-8" />}
      actions={
        <>
          <Button asChild className={`${THEME.button.ghost} rounded-full px-4`}>
            <a href="/voicebot" className="flex items-center gap-2">
              <Mic className="w-4 h-4" />
              Voicebot
            </a>
          </Button>
          <Button asChild className={`${THEME.button.secondary} rounded-full px-4`}>
            <a href="/agent/create" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Create Agent
            </a>
          </Button>
        </>
      }
      error={error}
    >
      <NavigationBar />

      {agents.length === 0 ? (
        <div className={`${THEME.card.base} p-12 text-center`}>
          <Bot className={`w-16 h-16 mx-auto mb-4 ${THEME.text.muted}`} />
          <h3 className="text-xl font-semibold mb-2">No Agents Found</h3>
          <p className={`${THEME.text.secondary} mb-6`}>
            Create your first agent to get started with the voicebot system.
          </p>
          <Button asChild className={`${THEME.button.secondary} rounded-full px-6`}>
            <a href="/agent/create" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Create First Agent
            </a>
          </Button>
        </div>
      ) : (
        <AgentGrid>
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              isDefault={defaultAgent?.id === agent.id}
              onSetDefault={handleSetDefault}
              onDelete={handleDelete}
            />
          ))}
        </AgentGrid>
      )}
    </PageLayout>
  )
}