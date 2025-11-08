'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { Agent } from './types'

interface ProviderConfig {
  providers: { value: string; label: string }[]
  configurable_fields: Record<string, { type: string; label: string; required: boolean }>
}

interface AvailableProviders {
  llm: ProviderConfig
  tts: ProviderConfig
  stt: ProviderConfig
}

interface AgentEditPageProps {
  agentId?: string
}

export function AgentEditPage({ agentId }: AgentEditPageProps) {
  const [agent, setAgent] = useState<Partial<Agent>>({
    name: '',
    description: '',
    llm_provider: '',
    tts_provider: '',
    stt_provider: '',
    llm_config: { model: '', api_key: '' },
    tts_config: { voice: '', api_key: '', model: '' },
    stt_config: { model: '', api_key: '' }
  })
  const [providers, setProviders] = useState<AvailableProviders | null>(null)
  const [loading, setLoading] = useState(!!agentId)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadProviders()
    if (agentId) {
      loadAgent()
    }
  }, [agentId])

  const loadProviders = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/agents/providers/available')
      if (!response.ok) {
        throw new Error(`Failed to load providers: ${response.statusText}`)
      }
      const providerData = await response.json()
      setProviders(providerData)
    } catch (err) {
      console.error('Failed to load providers:', err)
    }
  }

  const loadAgent = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch(`http://localhost:8001/api/agents/${agentId}`)
      if (!response.ok) {
        throw new Error(`Failed to load agent: ${response.statusText}`)
      }
      
      const agentData = await response.json()
      setAgent(agentData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)

      // Build payload with proper ProviderConfig structure
      const payload = {
        name: agent.name || '',
        description: agent.description || '',
        llm_config: agent.llm_provider ? {
          provider: agent.llm_provider,
          config: {
            model: agent.llm_config?.model || '',
            api_key: agent.llm_config?.api_key || ''
          }
        } : undefined,
        tts_config: agent.tts_provider ? {
          provider: agent.tts_provider,
          config: {
            voice: agent.tts_config?.voice || '',
            model: agent.tts_config?.model || '',
            api_key: agent.tts_config?.api_key || ''
          }
        } : undefined,
        stt_config: agent.stt_provider ? {
          provider: agent.stt_provider,
          config: {
            model: agent.stt_config?.model || '',
            api_key: agent.stt_config?.api_key || ''
          }
        } : undefined
      }

      const url = agentId 
        ? `http://localhost:8001/api/agents/${agentId}/`
        : 'http://localhost:8001/api/agents/'
      
      const method = agentId ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to save agent: ${response.statusText} - ${errorText}`)
      }

      // Redirect back to admin page after successful save
      window.location.href = '/agent/admin'
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save agent')
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field: string, value: string | object) => {
    setAgent(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleConfigChange = (configField: string, field: string, value: string) => {
    setAgent(prev => ({
      ...prev,
      [configField]: {
        ...(prev[configField as keyof Agent] as object || {}),
        [field]: value
      }
    }))
  }

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading agent...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>
            {agentId ? 'Edit Agent' : 'Create New Agent'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Agent Name</Label>
              <Input
                id="name"
                value={agent.name || ''}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Enter agent name"
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={agent.description || ''}
                onChange={(e) => handleInputChange('description', e.target.value)}
                placeholder="Enter agent description"
              />
            </div>

            {/* Provider Selection */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="llm_provider">LLM Provider</Label>
                <Select value={agent.llm_provider || ''} onValueChange={(value) => handleInputChange('llm_provider', value)}>
                  <SelectTrigger id="llm_provider">
                    <SelectValue placeholder="Select LLM Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers?.llm.providers.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>
                        {provider.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="tts_provider">TTS Provider</Label>
                <Select value={agent.tts_provider || ''} onValueChange={(value) => handleInputChange('tts_provider', value)}>
                  <SelectTrigger id="tts_provider">
                    <SelectValue placeholder="Select TTS Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers?.tts.providers.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>
                        {provider.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="stt_provider">STT Provider</Label>
                <Select value={agent.stt_provider || ''} onValueChange={(value) => handleInputChange('stt_provider', value)}>
                  <SelectTrigger id="stt_provider">
                    <SelectValue placeholder="Select STT Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers?.stt.providers.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>
                        {provider.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* LLM Configuration */}
            {agent.llm_provider && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">LLM Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="llm_model">Model</Label>
                    <Input
                      id="llm_model"
                      value={agent.llm_config?.model || ''}
                      onChange={(e) => handleConfigChange('llm_config', 'model', e.target.value)}
                      placeholder="e.g., llama-3.1-8b-instant"
                    />
                  </div>
                  <div>
                    <Label htmlFor="llm_api_key">API Key</Label>
                    <Input
                      id="llm_api_key"
                      type="password"
                      value={agent.llm_config?.api_key || ''}
                      onChange={(e) => handleConfigChange('llm_config', 'api_key', e.target.value)}
                      placeholder="Enter LLM API key"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TTS Configuration */}
            {agent.tts_provider && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">TTS Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="tts_voice">Voice</Label>
                    <Input
                      id="tts_voice"
                      value={agent.tts_config?.voice || ''}
                      onChange={(e) => handleConfigChange('tts_config', 'voice', e.target.value)}
                      placeholder="e.g., EXAVITQu4vr4xnSDxMaL"
                    />
                  </div>
                  <div>
                    <Label htmlFor="tts_model">Model</Label>
                    <Input
                      id="tts_model"
                      value={agent.tts_config?.model || ''}
                      onChange={(e) => handleConfigChange('tts_config', 'model', e.target.value)}
                      placeholder="e.g., eleven_multilingual_v2"
                    />
                  </div>
                  <div>
                    <Label htmlFor="tts_api_key">API Key</Label>
                    <Input
                      id="tts_api_key"
                      type="password"
                      value={agent.tts_config?.api_key || ''}
                      onChange={(e) => handleConfigChange('tts_config', 'api_key', e.target.value)}
                      placeholder="Enter TTS API key"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* STT Configuration */}
            {agent.stt_provider && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">STT Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="stt_model">Model</Label>
                    <Input
                      id="stt_model"
                      value={agent.stt_config?.model || ''}
                      onChange={(e) => handleConfigChange('stt_config', 'model', e.target.value)}
                      placeholder="e.g., base, small, medium, large"
                    />
                  </div>
                  <div>
                    <Label htmlFor="stt_api_key">API Key</Label>
                    <Input
                      id="stt_api_key"
                      type="password"
                      value={agent.stt_config?.api_key || ''}
                      onChange={(e) => handleConfigChange('stt_config', 'api_key', e.target.value)}
                      placeholder="Enter STT API key"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-4">
            <Button 
              onClick={handleSave} 
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Agent'}
            </Button>
            <Button variant="outline" asChild>
              <a href="/agent/admin">Cancel</a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}