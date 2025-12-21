'use client';

import { useState, useEffect, useCallback } from 'react';
import { PageLayout } from '@/components/ui/PageLayout';
import { PageCard } from '@/components/ui/PageCard';
import { ModalWrapper } from '@/components/ui/ModalWrapper';
import { useModalRouter } from '@/hooks/use-modal-router';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RagConfig } from './types';
import { DocumentUpload } from './DocumentUpload';
import { DocumentList } from './DocumentList';
import { THEME } from '@/lib/theme';
import { Database, ArrowLeft, Save, Trash2, FileText } from 'lucide-react';

interface ProviderConfig {
  providers: { value: string; label: string }[];
  configurable_fields: Record<
    string,
    Record<string, { type: string; label: string; required: boolean }>
  >;
}

interface ProviderFieldDefinition {
  type: string;
  label: string;
  required: boolean;
  description?: string;
  default?: any;
  options?: Array<{ value: string; label: string }>;
  min?: number;
  max?: number;
}

interface ProviderFields {
  [key: string]: ProviderFieldDefinition;
}

interface RagEditPageProps {
  configId?: string;
}

export function RagEditPage({ configId }: RagEditPageProps) {
  const { isModalMode, closeModal } = useModalRouter();

  const [config, setConfig] = useState<Partial<RagConfig>>({
    name: '',
    description: '',
    provider_type: '',
    provider: '',
    provider_config: {},
    is_default: false,
    is_active: true,
  });
  const [providers, setProviders] = useState<ProviderConfig | null>(null);
  const [providerFields, setProviderFields] = useState<ProviderFields>({});
  const [loading, setLoading] = useState(!!configId);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('configuration');
  const [documentsRefresh, setDocumentsRefresh] = useState(0);

  const loadProviders = useCallback(async () => {
    try {
      const response = await fetch(
        'http://localhost:8001/api/rag-configs/providers/available'
      );
      if (!response.ok) {
        throw new Error(`Failed to load providers: ${response.statusText}`);
      }
      const providerData = await response.json();
      setProviders(providerData);
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `http://localhost:8001/api/rag-configs/${configId}`
      );
      if (!response.ok) {
        throw new Error(`Failed to load RAG config: ${response.statusText}`);
      }

      const configData = await response.json();
      setConfig(configData);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load RAG config'
      );
    } finally {
      setLoading(false);
    }
  }, [configId]);

  const loadProviderFields = useCallback(
    async (providerName: string): Promise<ProviderFields> => {
      try {
        const response = await fetch(
          `http://localhost:8001/api/rag-configs/providers/${providerName}/fields`
        );
        if (!response.ok) {
          throw new Error(
            `Failed to load provider fields: ${response.statusText}`
          );
        }
        const fields = await response.json();
        setProviderFields(fields);
        return fields;
      } catch (err) {
        console.error(`Failed to load fields for rag.${providerName}:`, err);
        return {};
      }
    },
    []
  );

  useEffect(() => {
    loadProviders();
    if (configId) {
      loadConfig();
    }
  }, [configId, loadProviders, loadConfig]);

  useEffect(() => {
    if (config.provider) {
      loadProviderFields(config.provider);
    }
  }, [config.provider, loadProviderFields]);

  const handleProviderChange = async (providerName: string) => {
    handleInputChange('provider', providerName);

    if (providerName) {
      const fields = await loadProviderFields(providerName);

      const newConfig: Record<string, any> = {};
      Object.entries(fields).forEach(([field, fieldDef]) => {
        // Validate field name before using it
        if (typeof field === 'string' && field.length > 0) {
          newConfig[field] =
            fieldDef.default !== undefined ? fieldDef.default : '';
        }
      });
      handleInputChange('provider_config', newConfig);
    } else {
      handleInputChange('provider_config', {});
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const payload = {
        name: config.name || '',
        description: config.description || '',
        provider_config: config.provider
          ? {
              provider: config.provider,
              config: (config.provider_config as Record<string, any>) || {},
            }
          : undefined,
        is_default: config.is_default || false,
        is_active: config.is_active ?? true,
      };

      const url = configId
        ? `http://localhost:8001/api/rag-configs/${configId}/`
        : 'http://localhost:8001/api/rag-configs/';

      const method = configId ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to save RAG config: ${response.statusText} - ${errorText}`
        );
      }

      if (isModalMode) {
        closeModal();
      } else {
        window.location.href = '/rag/admin';
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to save RAG config'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (
    field: string,
    value: string | boolean | object
  ) => {
    setConfig((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleConfigChange = (
    field: string,
    value: string | boolean | number
  ) => {
    // Validate field name to prevent object injection
    if (typeof field !== 'string' || field.length === 0) {
      console.warn('Invalid field name in handleConfigChange:', field);
      return;
    }

    setConfig((prev) => ({
      ...prev,
      provider_config: {
        ...((prev.provider_config as object) || {}),
        [field]: value,
      },
    }));
  };

  const handleUploadComplete = () => {
    setDocumentsRefresh((prev) => prev + 1);
  };

  const handleDelete = async () => {
    if (!configId) return;
    if (
      !confirm(
        'Are you sure you want to delete this RAG configuration? This action cannot be undone.'
      )
    ) {
      return;
    }
    try {
      const response = await fetch(
        `http://localhost:8001/api/rag-configs/${configId}/`,
        {
          method: 'DELETE',
        }
      );
      if (!response.ok) {
        throw new Error('Failed to delete RAG config');
      }
      if (isModalMode) {
        closeModal();
      } else {
        window.location.href = '/rag/admin';
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to delete RAG config'
      );
    }
  };

  const content = (
    <>
      {error && (
        <Alert
          variant="destructive"
          className="mb-6 bg-red-900/50 border-red-500/50"
        >
          <AlertDescription className="text-white">{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList
          className={`mb-6 ${THEME.panel.base} ${THEME.panel.border} border p-1`}
        >
          <TabsTrigger
            value="configuration"
            className={`${THEME.text.secondary} data-[state=active]:${THEME.accent.cyanBg} data-[state=active]:${THEME.accent.cyan}`}
          >
            Configuration
          </TabsTrigger>
          {configId && (
            <TabsTrigger
              value="documents"
              className={`${THEME.text.secondary} data-[state=active]:${THEME.accent.cyanBg} data-[state=active]:${THEME.accent.cyan}`}
            >
              Documents
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="configuration">
          <PageCard>
            <div className="space-y-6">
              {/* Basic Info */}
              <div className="space-y-4">
                <h3
                  className={`text-lg font-semibold ${THEME.text.accent} flex items-center gap-2`}
                >
                  <Database className="w-5 h-5" />
                  Basic Information
                </h3>

                <div>
                  <Label htmlFor="name" className={THEME.text.secondary}>
                    Configuration Name *
                  </Label>
                  <Input
                    id="name"
                    value={config.name || ''}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="Enter RAG configuration name"
                    className={`${THEME.input.base} mt-1`}
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="description" className={THEME.text.secondary}>
                    Description
                  </Label>
                  <Input
                    id="description"
                    value={config.description || ''}
                    onChange={(e) =>
                      handleInputChange('description', e.target.value)
                    }
                    placeholder="Enter description (optional)"
                    className={`${THEME.input.base} mt-1`}
                  />
                </div>
              </div>

              {/* Provider Section */}
              <div className="space-y-4 pt-6 border-t border-white/10">
                <h3 className={`text-lg font-semibold ${THEME.text.accent}`}>
                  RAG Provider
                </h3>

                <div>
                  <Label htmlFor="provider" className={THEME.text.secondary}>
                    Provider
                  </Label>
                  <Select
                    value={config.provider || ''}
                    onValueChange={(value) => handleProviderChange(value)}
                  >
                    <SelectTrigger
                      id="provider"
                      className={`${THEME.input.select} mt-1`}
                    >
                      <SelectValue placeholder="Select RAG Provider" />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-900 border-white/20">
                      {providers?.providers.map((provider) => (
                        <SelectItem
                          key={provider.value}
                          value={provider.value}
                          className="text-white"
                        >
                          {provider.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {config.provider && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-green-500/30">
                    {Object.entries(providerFields).map(([field, fieldDef]) => {
                      // Validate field name before accessing config
                      const value =
                        typeof field === 'string' &&
                        config.provider_config &&
                        (config.provider_config as Record<string, any>)[field]
                          ? (config.provider_config as Record<string, any>)[
                              field
                            ]
                          : fieldDef.default || '';
                      if (fieldDef.type === 'select') {
                        return (
                          <div key={field}>
                            <Label
                              htmlFor={`provider_${field}`}
                              className={THEME.text.secondary}
                            >
                              {fieldDef.label}
                            </Label>
                            <Select
                              value={value || fieldDef.default || ''}
                              onValueChange={(val) =>
                                handleConfigChange(field, val)
                              }
                            >
                              <SelectTrigger
                                id={`provider_${field}`}
                                className={`${THEME.input.select} mt-1`}
                              >
                                <SelectValue
                                  placeholder={`Select ${fieldDef.label}`}
                                />
                              </SelectTrigger>
                              <SelectContent className="bg-gray-900 border-white/20">
                                {fieldDef.options?.map((opt) => (
                                  <SelectItem
                                    key={opt.value}
                                    value={opt.value}
                                    className="text-white"
                                  >
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
                          <div
                            key={field}
                            className="flex items-center space-x-2"
                          >
                            <input
                              type="checkbox"
                              id={`provider_${field}`}
                              checked={!!value}
                              onChange={(e) =>
                                handleConfigChange(field, e.target.checked)
                              }
                              className="h-4 w-4 rounded border-white/20 bg-white/10"
                            />
                            <Label
                              htmlFor={`provider_${field}`}
                              className={THEME.text.secondary}
                            >
                              {fieldDef.label}
                            </Label>
                          </div>
                        );
                      }
                      if (fieldDef.type === 'number') {
                        return (
                          <div key={field}>
                            <Label
                              htmlFor={`provider_${field}`}
                              className={THEME.text.secondary}
                            >
                              {fieldDef.label}
                            </Label>
                            <Input
                              id={`provider_${field}`}
                              type="number"
                              min={fieldDef.min}
                              max={fieldDef.max}
                              value={value || fieldDef.default || ''}
                              onChange={(e) =>
                                handleConfigChange(
                                  field,
                                  e.target.valueAsNumber ||
                                    parseInt(e.target.value) ||
                                    0
                                )
                              }
                              placeholder={`Enter ${fieldDef.label}`}
                              className={`${THEME.input.base} mt-1`}
                            />
                          </div>
                        );
                      }
                      return (
                        <div key={field}>
                          <Label
                            htmlFor={`provider_${field}`}
                            className={THEME.text.secondary}
                          >
                            {fieldDef.label}
                          </Label>
                          <Input
                            id={`provider_${field}`}
                            type={
                              fieldDef.type === 'password' ? 'password' : 'text'
                            }
                            value={value || ''}
                            onChange={(e) =>
                              handleConfigChange(field, e.target.value)
                            }
                            placeholder={`Enter ${fieldDef.label}`}
                            className={`${THEME.input.base} mt-1`}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Options */}
              <div className="space-y-4 pt-6 border-t border-white/10">
                <h3 className={`text-lg font-semibold ${THEME.text.accent}`}>
                  Options
                </h3>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_default"
                    checked={config.is_default || false}
                    onChange={(e) =>
                      handleInputChange('is_default', e.target.checked)
                    }
                    className="h-4 w-4 rounded border-white/20 bg-white/10"
                  />
                  <Label htmlFor="is_default" className={THEME.text.secondary}>
                    Set as default RAG configuration
                  </Label>
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={config.is_active ?? true}
                    onChange={(e) =>
                      handleInputChange('is_active', e.target.checked)
                    }
                    className="h-4 w-4 rounded border-white/20 bg-white/10"
                  />
                  <Label htmlFor="is_active" className={THEME.text.secondary}>
                    Active (can be used by agents)
                  </Label>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-4 pt-6 border-t border-white/10">
                <Button
                  onClick={handleSave}
                  disabled={saving}
                  className={`${THEME.button.secondary} rounded-full px-6 flex items-center gap-2`}
                >
                  <Save className="w-4 h-4" />
                  {saving ? 'Saving...' : 'Save Configuration'}
                </Button>

                <Button
                  variant="outline"
                  onClick={() => {
                    if (isModalMode) {
                      closeModal();
                    } else {
                      window.location.href = '/rag/admin';
                    }
                  }}
                  className={`${THEME.button.ghost} rounded-full px-6 flex items-center gap-2`}
                >
                  <ArrowLeft className="w-4 h-4" />
                  Cancel
                </Button>

                {configId && (
                  <Button
                    variant="destructive"
                    onClick={handleDelete}
                    disabled={saving}
                    className={`${THEME.button.danger} rounded-full px-6 flex items-center gap-2`}
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </Button>
                )}
              </div>
            </div>
          </PageCard>
        </TabsContent>

        {configId && (
          <TabsContent value="documents">
            <PageCard
              title="Document Management"
              icon={<FileText className="w-5 h-5" />}
            >
              <div className="space-y-6">
                <div>
                  <h3
                    className={`text-md font-semibold ${THEME.text.secondary} mb-4`}
                  >
                    Upload Documents
                  </h3>
                  <DocumentUpload
                    ragConfigId={configId}
                    onUploadComplete={handleUploadComplete}
                  />
                </div>

                <div className="pt-6 border-t border-white/10">
                  <h3
                    className={`text-md font-semibold ${THEME.text.secondary} mb-4`}
                  >
                    Uploaded Documents
                  </h3>
                  <DocumentList
                    ragConfigId={configId}
                    refreshTrigger={documentsRefresh}
                  />
                </div>
              </div>
            </PageCard>
          </TabsContent>
        )}
      </Tabs>
    </>
  );

  if (loading) {
    return (
      <PageLayout
        title={configId ? 'Edit RAG Configuration' : 'Create RAG Configuration'}
        icon={<Database className="w-8 h-8" />}
      >
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
            <p className={THEME.text.secondary}>Loading RAG configuration...</p>
          </div>
        </div>
      </PageLayout>
    );
  }

  if (isModalMode) {
    return (
      <ModalWrapper
        isOpen={true}
        onClose={closeModal}
        title={configId ? 'Edit RAG Configuration' : 'Create RAG Configuration'}
      >
        {content}
      </ModalWrapper>
    );
  }

  return (
    <PageLayout
      title={configId ? 'Edit RAG Configuration' : 'Create RAG Configuration'}
      icon={<Database className="w-8 h-8" />}
      breadcrumbs={[
        { label: 'RAG Configs', href: '/rag/admin' },
        { label: configId ? 'Edit' : 'Create', href: '#' },
      ]}
    >
      {content}
    </PageLayout>
  );
}
