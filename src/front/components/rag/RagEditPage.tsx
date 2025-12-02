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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RagConfig } from './types'
import { DocumentUpload } from './DocumentUpload'
import { DocumentList } from './DocumentList'

interface ProviderConfig {
  providers: { value: string; label: string }[]
  configurable_fields: Record<string, Record<string, { type: string; label: string; required: boolean }>>
}

interface ProviderFieldDefinition {
  type: string
  label: string
  required: boolean
  description?: string
  default?: any
  options?: Array<{ value: string; label: string }>
  min?: number
  max?: number
}

interface ProviderFields {
  [key: string]: ProviderFieldDefinition
}

interface RagEditPageProps {
  configId?: string
}

export function RagEditPage({ configId }: RagEditPageProps) {
  const [config, setConfig] = useState<Partial<RagConfig>>({
    name: '',
    description: '',
    provider_type: '',
    provider: '',
    provider_config: {},
    is_default: false,
    is_active: true
  })
  const [providers, setProviders] = useState<ProviderConfig | null>(null)
  const [providerFields, setProviderFields] = useState<ProviderFields>({})
  const [loading, setLoading] = useState(!!configId)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('configuration')
  const [documentsRefresh, setDocumentsRefresh] = useState(0)

  useEffect(() => {
    loadProviders()
    if (configId) {
      loadConfig()
    }
  }, [configId])

  // Load provider fields when provider is selected
  useEffect(() => {
    if (config.provider) {
      loadProviderFields(config.provider)
    }
  }, [config.provider])

  const loadProviders = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/rag-configs/providers/available')
      if (!response.ok) {
        throw new Error(`Failed to load providers: ${response.statusText}`)
      }
      const providerData = await response.json()
      setProviders(providerData)
    } catch (err) {
      console.error('Failed to load providers:', err)
    }
  }

  const loadConfig = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`http://localhost:8001/api/rag-configs/${configId}`)
      if (!response.ok) {
        throw new Error(`Failed to load RAG config: ${response.statusText}`)
      }

      const configData = await response.json()
      setConfig(configData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load RAG config')
    } finally {
      setLoading(false)
    }
  }

  const loadProviderFields = async (providerName: string): Promise<ProviderFields> => {
    try {
      const response = await fetch(`http://localhost:8001/api/rag-configs/providers/${providerName}/fields`)
      if (!response.ok) {
        throw new Error(`Failed to load provider fields: ${response.statusText}`)
      }
      const fields = await response.json()
      setProviderFields(fields)
      return fields
    } catch (err) {
      console.error(`Failed to load fields for rag.${providerName}:`, err)
      return {}
    }
  }

  const handleProviderChange = async (providerName: string) => {
    // Update the provider selection
    handleInputChange('provider', providerName)

    // Load provider-specific fields
    if (providerName) {
      const fields = await loadProviderFields(providerName)

      // Initialize config with default values for the new provider
      const newConfig: Record<string, any> = {}
      Object.entries(fields).forEach(([field, fieldDef]) => {
        newConfig[field] = fieldDef.default !== undefined ? fieldDef.default : ''
      })
      handleInputChange('provider_config', newConfig)
    } else {
      // Clear config when no provider is selected
      handleInputChange('provider_config', {})
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)

      // Build payload with proper ProviderConfig structure
      const payload = {
        name: config.name || '',
        description: config.description || '',
        provider_config: config.provider ? {
          provider: config.provider,
          config: config.provider_config as Record<string, any> || {}
        } : undefined,
        is_default: config.is_default || false,
        is_active: config.is_active ?? true
      }

      const url = configId
        ? `http://localhost:8001/api/rag-configs/${configId}/`
        : 'http://localhost:8001/api/rag-configs/'

      const method = configId ? 'PUT' : 'POST'

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to save RAG config: ${response.statusText} - ${errorText}`)
      }

      // Redirect back to admin page after successful save
      window.location.href = '/rag/admin'
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save RAG config')
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field: string, value: string | boolean | object) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleConfigChange = (field: string, value: string | boolean | number) => {
    setConfig(prev => ({
      ...prev,
      provider_config: {
        ...(prev.provider_config as object || {}),
        [field]: value
      }
    }))
  }

  const handleUploadComplete = () => {
    setDocumentsRefresh(prev => prev + 1)
  }

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading RAG configuration...</p>
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
            {configId ? 'Edit RAG Configuration' : 'Create New RAG Configuration'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-6">
              <TabsTrigger value="configuration">Configuration</TabsTrigger>
              {configId && <TabsTrigger value="documents">Documents</TabsTrigger>}
            </TabsList>

            <TabsContent value="configuration" className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="name">Configuration Name *</Label>
                  <Input
                    id="name"
                    value={config.name || ''}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="Enter RAG configuration name"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    value={config.description || ''}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Enter description (optional)"
                  />
                </div>

                {/* Provider Section */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">RAG Provider</h3>
                  <div>
                    <Label htmlFor="provider">Provider</Label>
                    <Select value={config.provider || ''} onValueChange={(value) => handleProviderChange(value)}>
                      <SelectTrigger id="provider">
                        <SelectValue placeholder="Select RAG Provider" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers?.providers.map((provider) => (
                          <SelectItem key={provider.value} value={provider.value}>
                            {provider.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Provider Configuration */}
                  {config.provider && (
                    <div className="space-y-4 pl-4 border-l-2 border-gray-200">
                      <h4 className="text-md font-medium">Provider Configuration</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(providerFields).map(([field, fieldDef]) => {
                          const value = (config.provider_config as Record<string, any>)?.[field];
                          if (fieldDef.type === 'select') {
                            return (
                              <div key={field}>
                                <Label htmlFor={`provider_${field}`}>{fieldDef.label}</Label>
                                <Select
                                  value={value || fieldDef.default || ''}
                                  onValueChange={(val) => handleConfigChange(field, val)}
                                >
                                  <SelectTrigger id={`provider_${field}`}>
                                    <SelectValue placeholder={`Select ${fieldDef.label}`} />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {fieldDef.options?.map((opt) => (
                                      <SelectItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            );
                          }
                          if (fieldDef.type === 'boolean') {
                            return (
                              <div key={field} className="flex items-center space-x-2">
                                <input
                                  type="checkbox"
                                  id={`provider_${field}`}
                                  checked={!!value}
                                  onChange={(e) => handleConfigChange(field, e.target.checked)}
                                  className="h-4 w-4 rounded border-gray-300"
                                />
                                <Label htmlFor={`provider_${field}`}>{fieldDef.label}</Label>
                              </div>
                            );
                          }
                          if (fieldDef.type === 'number') {
                            return (
                              <div key={field}>
                                <Label htmlFor={`provider_${field}`}>{fieldDef.label}</Label>
                                <Input
                                  id={`provider_${field}`}
                                  type="number"
                                  min={fieldDef.min}
                                  max={fieldDef.max}
                                  value={value || fieldDef.default || ''}
                                  onChange={(e) => handleConfigChange(field, e.target.valueAsNumber || parseInt(e.target.value) || 0)}
                                  placeholder={`Enter ${fieldDef.label}`}
                                />
                              </div>
                            );
                          }
                          // text, password, etc.
                          return (
                            <div key={field}>
                              <Label htmlFor={`provider_${field}`}>{fieldDef.label}</Label>
                              <Input
                                id={`provider_${field}`}
                                type={fieldDef.type === 'password' ? 'password' : 'text'}
                                value={value || ''}
                                onChange={(e) => handleConfigChange(field, e.target.value)}
                                placeholder={`Enter ${fieldDef.label}`}
                              />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Options */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Options</h3>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="is_default"
                      checked={config.is_default || false}
                      onChange={(e) => handleInputChange('is_default', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <Label htmlFor="is_default">Set as default RAG configuration</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={config.is_active ?? true}
                      onChange={(e) => handleInputChange('is_active', e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <Label htmlFor="is_active">Active (can be used by agents)</Label>
                  </div>
                </div>
              </div>

              <div className="flex gap-4">
                <Button
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Save Configuration'}
                </Button>
                <Button variant="outline" asChild>
                  <a href="/rag/admin">Cancel</a>
                </Button>
              </div>
            </TabsContent>

            {configId && (
              <TabsContent value="documents" className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">Upload Documents</h3>
                  <DocumentUpload
                    ragConfigId={configId}
                    onUploadComplete={handleUploadComplete}
                  />
                </div>

                <div>
                  <h3 className="text-lg font-semibold mb-4">Uploaded Documents</h3>
                  <DocumentList
                    ragConfigId={configId}
                    refreshTrigger={documentsRefresh}
                  />
                </div>
              </TabsContent>
            )}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}