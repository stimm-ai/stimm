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
  configurable_fields: Record<string, Record<string, { type: string; label: string; required: boolean }>>
}

interface AvailableProviders {
  llm: ProviderConfig
  tts: ProviderConfig
  stt: ProviderConfig
}

interface ProviderFields {
  [key: string]: { type: string; label: string; required: boolean }
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
    llm_config: {},
    tts_config: {},
    stt_config: {}
  })
  const [providers, setProviders] = useState<AvailableProviders | null>(null)
  const [providerFields, setProviderFields] = useState<Record<string, ProviderFields>>({
    llm: {},
    tts: {},
    stt: {}
  })
  const [loading, setLoading] = useState(!!agentId)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadProviders()
    if (agentId) {
      loadAgent()
    }
  }, [agentId])

  // Load provider fields when agent data is loaded and providers are available
  useEffect(() => {
    if (agent && providers) {
      // Load provider fields for existing agent providers
      const loadExistingProviderFields = async () => {
        if (agent.llm_provider) {
          await loadProviderFields('llm', agent.llm_provider)
        }
        if (agent.tts_provider) {
          await loadProviderFields('tts', agent.tts_provider)
        }
        if (agent.stt_provider) {
          await loadProviderFields('stt', agent.stt_provider)
        }
      }
      
      loadExistingProviderFields()
    }
  }, [agent, providers])

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

  const loadProviderFields = async (providerType: string, providerName: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/agents/providers/${providerType}/${providerName}/fields`)
      if (!response.ok) {
        throw new Error(`Failed to load provider fields: ${response.statusText}`)
      }
      const fields = await response.json()
      
      setProviderFields(prev => ({
        ...prev,
        [providerType]: fields
      }))
    } catch (err) {
      console.error(`Failed to load fields for ${providerType}.${providerName}:`, err)
    }
  }

  const handleProviderChange = async (providerType: string, providerName: string) => {
    // Update the provider selection
    handleInputChange(`${providerType}_provider`, providerName)
    
    // Load provider-specific fields
    if (providerName) {
      await loadProviderFields(providerType, providerName)
      
      // Initialize config with empty values for the new provider
      const configFields = providerFields[providerType]
      const newConfig: Record<string, string> = {}
      
      Object.keys(configFields).forEach(field => {
        newConfig[field] = ''
      })
      
      handleInputChange(`${providerType}_config`, newConfig)
    } else {
      // Clear config when no provider is selected
      handleInputChange(`${providerType}_config`, {})
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)

      // Build payload with proper ProviderConfig structure using dynamic fields
      const payload = {
        name: agent.name || '',
        description: agent.description || '',
        llm_config: agent.llm_provider ? {
          provider: agent.llm_provider,
          config: agent.llm_config as Record<string, string> || {}
        } : undefined,
        tts_config: agent.tts_provider ? {
          provider: agent.tts_provider,
          config: agent.tts_config as Record<string, string> || {}
        } : undefined,
        stt_config: agent.stt_provider ? {
          provider: agent.stt_provider,
          config: agent.stt_config as Record<string, string> || {}
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

            {/* LLM Section */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">LLM</h3>
              <div>
                <Label htmlFor="llm_provider">Provider</Label>
                <Select value={agent.llm_provider || ''} onValueChange={(value) => handleProviderChange('llm', value)}>
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

              {/* LLM Configuration */}
              {agent.llm_provider && (
                <div className="space-y-4 pl-4 border-l-2 border-gray-200">
                  <h4 className="text-md font-medium">Configuration</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(providerFields.llm).map(([field, fieldDef]) => (
                      <div key={field}>
                        <Label htmlFor={`llm_${field}`}>{fieldDef.label}</Label>
                        <Input
                          id={`llm_${field}`}
                          type={fieldDef.type === 'password' ? 'password' : 'text'}
                          value={(agent.llm_config as Record<string, string>)?.[field] || ''}
                          onChange={(e) => handleConfigChange('llm_config', field, e.target.value)}
                          placeholder={`Enter ${fieldDef.label}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* TTS Section */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">TTS</h3>
              <div>
                <Label htmlFor="tts_provider">Provider</Label>
                <Select value={agent.tts_provider || ''} onValueChange={(value) => handleProviderChange('tts', value)}>
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

              {/* TTS Configuration */}
              {agent.tts_provider && (
                <div className="space-y-4 pl-4 border-l-2 border-gray-200">
                  <h4 className="text-md font-medium">Configuration</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(providerFields.tts).map(([field, fieldDef]) => (
                      <div key={field}>
                        <Label htmlFor={`tts_${field}`}>{fieldDef.label}</Label>
                        <Input
                          id={`tts_${field}`}
                          type={fieldDef.type === 'password' ? 'password' : 'text'}
                          value={(agent.tts_config as Record<string, string>)?.[field] || ''}
                          onChange={(e) => handleConfigChange('tts_config', field, e.target.value)}
                          placeholder={`Enter ${fieldDef.label}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* STT Section */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">STT</h3>
              <div>
                <Label htmlFor="stt_provider">Provider</Label>
                <Select value={agent.stt_provider || ''} onValueChange={(value) => handleProviderChange('stt', value)}>
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

              {/* STT Configuration */}
              {agent.stt_provider && (
                <div className="space-y-4 pl-4 border-l-2 border-gray-200">
                  <h4 className="text-md font-medium">Configuration</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.entries(providerFields.stt).map(([field, fieldDef]) => (
                      <div key={field}>
                        <Label htmlFor={`stt_${field}`}>{fieldDef.label}</Label>
                        <Input
                          id={`stt_${field}`}
                          type={fieldDef.type === 'password' ? 'password' : 'text'}
                          value={(agent.stt_config as Record<string, string>)?.[field] || ''}
                          onChange={(e) => handleConfigChange('stt_config', field, e.target.value)}
                          placeholder={`Enter ${fieldDef.label}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
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