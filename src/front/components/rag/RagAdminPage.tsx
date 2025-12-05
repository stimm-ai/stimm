'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { PageLayout } from '@/components/ui/PageLayout'
import { NavigationBar } from '@/components/ui/NavigationBar'
import { RagConfig } from './types'
import { THEME, getProviderAccent } from '@/lib/theme'
import { Database, Plus, Mic, Edit, Star, Trash2, CheckCircle, XCircle } from 'lucide-react'

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

      const response = await fetch('http://localhost:8001/api/rag-configs/')
      if (!response.ok) {
        throw new Error(`Failed to load RAG configs: ${response.statusText}`)
      }

      const data = await response.json()
      const configsList = Array.isArray(data) ? data : []
      setConfigs(configsList)

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

      await loadConfigs()
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

      await loadConfigs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete RAG config')
    }
  }

  if (loading) {
    return (
      <PageLayout title="RAG Configuration Management" icon={<Database className="w-8 h-8" />}>
        <NavigationBar />
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
            <p className={THEME.text.secondary}>Loading RAG configurations...</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="RAG Configuration Management"
      icon={<Database className="w-8 h-8" />}
      actions={
        <>
           <Button asChild className={`${THEME.button.ghost} rounded-full px-4`}>
            <a href="/voicebot" className="flex items-center gap-2">
              <Mic className="w-4 h-4" />
              Speak with an agent
            </a>
          </Button>
          <Button asChild className={`${THEME.button.secondary} rounded-full px-4`}>
            <a href="/rag/create" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Create RAG Config
            </a>
          </Button>
        </>
      }
      error={error}
    >
      <NavigationBar />

      {configs.length === 0 ? (
        <div className={`${THEME.card.base} p-12 text-center`}>
          <Database className={`w-16 h-16 mx-auto mb-4 ${THEME.text.muted}`} />
          <h3 className="text-xl font-semibold mb-2">No RAG Configurations Found</h3>
          <p className={`${THEME.text.secondary} mb-6`}>
            Create your first RAG configuration to enable retrieval-augmented generation.
          </p>
          <Button asChild className={`${THEME.button.secondary} rounded-full px-6`}>
            <a href="/rag/create" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Create First RAG Configuration
            </a>
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {configs.map((config) => (
            <div
              key={config.id}
              className={`
                ${THEME.card.base} ${THEME.card.hover}
                ${defaultConfig?.id === config.id ? THEME.card.selected : ''}
                p-5 transition-all duration-300
              `}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold mb-1 flex items-center gap-2">
                    {config.name}
                    {defaultConfig?.id === config.id && (
                      <Star className={`w-4 h-4 ${THEME.accent.cyan} fill-current`} />
                    )}
                  </h3>
                  <p className={`text-sm ${THEME.text.muted}`}>
                    {config.description || 'No description'}
                  </p>
                </div>
              </div>

              {/* Config Info */}
              <div className="space-y-3 mb-4">
                <div className={`p-3 rounded-lg ${getProviderAccent('rag').bg} border ${getProviderAccent('rag').border}`}>
                  <div className={`font-semibold text-sm ${getProviderAccent('rag').text} mb-2`}>
                    {config.provider?.toUpperCase() || 'No Provider'}
                  </div>
                  <div className={`text-xs ${THEME.text.secondary} space-y-1`}>
                    <div className="flex items-center gap-2">
                      <span className="opacity-60">Type:</span>
                      <span>{config.provider_type || 'N/A'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="opacity-60">Status:</span>
                      {config.is_active ? (
                        <span className="flex items-center gap-1">
                          <CheckCircle className="w-3 h-3 text-green-400" />
                          Active
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <XCircle className="w-3 h-3 text-red-400" />
                          Inactive
                        </span>
                      )}
                    </div>
                    <div className={`text-xs ${THEME.text.muted} mt-2`}>
                      Created {new Date(config.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 flex-wrap pt-3 border-t border-white/10">
                <Button
                  variant="outline"
                  size="sm"
                  asChild
                  className={`${THEME.button.ghost} rounded-full flex-1`}
                >
                  <a href={`/rag/edit/${config.id}`} className="flex items-center gap-2 justify-center">
                    <Edit className="w-3 h-3" />
                    Edit
                  </a>
                </Button>

                {defaultConfig?.id !== config.id && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleSetDefault(config.id)}
                    className={`${THEME.button.secondary} rounded-full flex-1`}
                  >
                    <Star className="w-3 h-3 mr-1" />
                    Set Default
                  </Button>
                )}

                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(config.id)}
                  className={`${THEME.button.danger} rounded-full`}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageLayout>
  )
}