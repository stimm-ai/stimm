'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AgentGrid } from './AgentGrid'
import { AgentCard } from './AgentCard'
import { Agent } from './types'

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
      <div className="container mx-auto py-8">
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading agents...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Agent Management</CardTitle>
            <Button asChild>
              <a href="/agent/create">Create New Agent</a>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {agents.length === 0 ? (
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold mb-2">No Agents Found</h3>
              <p className="text-muted-foreground mb-4">
                Create your first agent to get started with the voicebot system.
              </p>
              <Button asChild>
                <a href="/agent/create">Create First Agent</a>
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
        </CardContent>
      </Card>
    </div>
  )
}