'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RagConfig } from './types'

export function RagAdminPage() {
  const [configs, setConfigs] = useState<RagConfig[]>([])
  const [defaultConfig, setDefaultConfig] = useState<RagConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadConfigs()
  }, [])

  const loadConfigs = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch RAG configs from FastAPI backend
      const response = await fetch('http://localhost:8001/api/rag-configs/')
      if (!response.ok) {
        throw new Error(`Failed to load RAG configs: ${response.statusText}`)
      }

      const data = await response.json()
      // API returns array directly, not wrapped in object
      const configsList = Array.isArray(data) ? data : []
      setConfigs(configsList)

      // Find default config
      const defaultConfig = configsList.find((config: RagConfig) => config.is_default)
      setDefaultConfig(defaultConfig || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load RAG configs')
    } finally {
      setLoading(false)
    }
  }

  const handleSetDefault = async (configId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/rag-configs/${configId}/set-default/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error('Failed to set default RAG config')
      }

      await loadConfigs() // Reload to get updated default config
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default RAG config')
    }
  }

  const handleDelete = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this RAG configuration? This action cannot be undone.')) {
      return
    }

    try {
      const response = await fetch(`http://localhost:8001/api/rag-configs/${configId}/`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete RAG config')
      }

      await loadConfigs() // Reload to reflect deletion
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete RAG config')
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading RAG configurations...</p>
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
            <CardTitle>RAG Configuration Management</CardTitle>
            <div className="flex gap-2">
              <Button asChild variant="outline">
                <a href="/agent/admin">👥 Agent Management</a>
              </Button>
              <Button asChild>
                <a href="/rag/create">Create New RAG Configuration</a>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {configs.length === 0 ? (
            <div className="text-center py-12">
              <h3 className="text-lg font-semibold mb-2">No RAG Configurations Found</h3>
              <p className="text-muted-foreground mb-4">
                Create your first RAG configuration to enable retrieval-augmented generation.
              </p>
              <Button asChild>
                <a href="/rag/create">Create First RAG Configuration</a>
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {configs.map((config) => (
                <div key={config.id} className="border rounded-lg p-4 space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-lg">{config.name}</h3>
                      <p className="text-sm text-muted-foreground">{config.description || 'No description'}</p>
                    </div>
                    {defaultConfig?.id === config.id && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary text-primary-foreground">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Provider:</span>
                      <span>{config.provider}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Type:</span>
                      <span>{config.provider_type}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Status:</span>
                      <span className={config.is_active ? 'text-green-600' : 'text-red-600'}>
                        {config.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-2">
                      Created {new Date(config.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                    >
                      <a href={`/rag/edit/${config.id}`}>Edit</a>
                    </Button>
                    {defaultConfig?.id !== config.id && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleSetDefault(config.id)}
                      >
                        Set as Default
                      </Button>
                    )}
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(config.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}