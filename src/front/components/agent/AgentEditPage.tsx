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
import { Agent } from './types';
import { THEME } from '@/lib/theme';
import { Bot, Database, ArrowLeft, Save } from 'lucide-react';

interface ProviderConfig {
  providers: { value: string; label: string }[];
  configurable_fields: Record<
    string,
    Record<string, { type: string; label: string; required: boolean }>
  >;
}

interface AvailableProviders {
  llm: ProviderConfig;
  tts: ProviderConfig;
  stt: ProviderConfig;
}

interface ProviderFields {
  [key: string]: { type: string; label: string; required: boolean };
}

interface AgentEditPageProps {
  agentId?: string;
}

export function AgentEditPage({ agentId }: AgentEditPageProps) {
  const { isModalMode, closeModal } = useModalRouter();

  const [agent, setAgent] = useState<Partial<Agent>>({
    name: '',
    description: '',
    system_prompt: '',
    llm_provider: '',
    tts_provider: '',
    stt_provider: '',
    rag_config_id: null,
    llm_config: {},
    tts_config: {},
    stt_config: {},
  });
  const [providers, setProviders] = useState<AvailableProviders | null>(null);
  const [ragConfigs, setRagConfigs] = useState<{ id: string; name: string }[]>(
    []
  );
  const [providerFields, setProviderFields] = useState<
    Record<string, ProviderFields>
  >({
    llm: {},
    tts: {},
    stt: {},
  });
  const [loading, setLoading] = useState(!!agentId);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      const response = await fetch(
        'http://localhost:8001/api/agents/providers/available'
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

  const loadRagConfigs = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8001/api/rag-configs/');
      if (!response.ok) {
        throw new Error(`Failed to load RAG configs: ${response.statusText}`);
      }
      const data = await response.json();
      setRagConfigs(
        data.map((config: any) => ({ id: config.id, name: config.name }))
      );
    } catch (err) {
      console.error('Failed to load RAG configs:', err);
    }
  }, []);

  const loadAgent = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `http://localhost:8001/api/agents/${agentId}`
      );
      if (!response.ok) {
        throw new Error(`Failed to load agent: ${response.statusText}`);
      }

      const agentData = await response.json();
      setAgent(agentData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent');
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  const loadProviderFields = useCallback(
    async (providerType: string, providerName: string) => {
      try {
        const response = await fetch(
          `http://localhost:8001/api/agents/providers/${providerType}/${providerName}/fields`
        );
        if (!response.ok) {
          throw new Error(
            `Failed to load provider fields: ${response.statusText}`
          );
        }
        const fields = await response.json();

        setProviderFields((prev) => ({
          ...prev,
          [providerType]: fields,
        }));
      } catch (err) {
        console.error(
          `Failed to load fields for ${providerType}.${providerName}:`,
          err
        );
      }
    },
    []
  );

  useEffect(() => {
    loadProviders();
    loadRagConfigs();
    if (agentId) {
      loadAgent();
    }
  }, [agentId, loadProviders, loadRagConfigs, loadAgent]);

  useEffect(() => {
    if (agent && providers) {
      const loadExistingProviderFields = async () => {
        if (agent.llm_provider) {
          await loadProviderFields('llm', agent.llm_provider);
        }
        if (agent.tts_provider) {
          await loadProviderFields('tts', agent.tts_provider);
        }
        if (agent.stt_provider) {
          await loadProviderFields('stt', agent.stt_provider);
        }
      };

      loadExistingProviderFields();
    }
  }, [agent, providers, loadProviderFields]);

  const handleProviderChange = async (
    providerType: string,
    providerName: string
  ) => {
    handleInputChange(`${providerType}_provider`, providerName);

    if (providerName) {
      await loadProviderFields(providerType, providerName);

      const configFields = providerFields[providerType];
      const newConfig: Record<string, string> = {};

      // Validate field names before using them
      Object.keys(configFields).forEach((field) => {
        if (typeof field === 'string' && field.length > 0) {
          newConfig[field] = '';
        }
      });

      handleInputChange(`${providerType}_config`, newConfig);
    } else {
      handleInputChange(`${providerType}_config`, {});
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const payload = {
        name: agent.name || '',
        description: agent.description || '',
        system_prompt: agent.system_prompt || '',
        rag_config_id:
          agent.rag_config_id === '' || agent.rag_config_id === 'none'
            ? null
            : agent.rag_config_id || null,
        llm_config: agent.llm_provider
          ? {
              provider: agent.llm_provider,
              config: (agent.llm_config as Record<string, string>) || {},
            }
          : undefined,
        tts_config: agent.tts_provider
          ? {
              provider: agent.tts_provider,
              config: (agent.tts_config as Record<string, string>) || {},
            }
          : undefined,
        stt_config: agent.stt_provider
          ? {
              provider: agent.stt_provider,
              config: (agent.stt_config as Record<string, string>) || {},
            }
          : undefined,
      };

      const url = agentId
        ? `http://localhost:8001/api/agents/${agentId}/`
        : 'http://localhost:8001/api/agents/';

      const method = agentId ? 'PUT' : 'POST';

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
          `Failed to save agent: ${response.statusText} - ${errorText}`
        );
      }

      if (isModalMode) {
        closeModal();
      } else {
        window.location.href = '/agent/admin';
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: string, value: string | object | null) => {
    setAgent((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleConfigChange = (
    configField: string,
    field: string,
    value: string
  ) => {
    // Validate field name to prevent object injection
    if (typeof field !== 'string' || field.length === 0) {
      console.warn('Invalid field name in handleConfigChange:', field);
      return;
    }

    setAgent((prev) => ({
      ...prev,
      [configField]: {
        ...((prev[configField as keyof Agent] as object) || {}),
        [field]: value,
      },
    }));
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

      <PageCard>
        <div className="space-y-6">
          {/* Basic Info */}
          <div className="space-y-4">
            <h3
              className={`text-lg font-semibold ${THEME.text.accent} flex items-center gap-2`}
            >
              <Bot className="w-5 h-5" />
              Basic Information
            </h3>

            <div>
              <Label htmlFor="name" className={THEME.text.secondary}>
                Agent Name *
              </Label>
              <Input
                id="name"
                value={agent.name || ''}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Enter agent name"
                className={`${THEME.input.base} mt-1`}
              />
            </div>

            <div>
              <Label htmlFor="description" className={THEME.text.secondary}>
                Description
              </Label>
              <Input
                id="description"
                value={agent.description || ''}
                onChange={(e) =>
                  handleInputChange('description', e.target.value)
                }
                placeholder="Enter agent description"
                className={`${THEME.input.base} mt-1`}
              />
            </div>

            <div>
              <Label htmlFor="system_prompt" className={THEME.text.secondary}>
                System Prompt
              </Label>
              <textarea
                id="system_prompt"
                value={agent.system_prompt || ''}
                onChange={(e) =>
                  handleInputChange('system_prompt', e.target.value)
                }
                placeholder="Enter system prompt for the agent (optional)"
                className={`${THEME.input.base} w-full min-h-[120px] p-3 rounded-md mt-1 resize-none`}
              />
            </div>
          </div>

          {/* LLM Configuration */}
          <div className="space-y-4 pt-6 border-t border-white/10">
            <h3 className={`text-lg font-semibold ${THEME.text.accent}`}>
              LLM Provider
            </h3>

            <div>
              <Label htmlFor="llm_provider" className={THEME.text.secondary}>
                Provider
              </Label>
              <Select
                value={agent.llm_provider || ''}
                onValueChange={(value) => handleProviderChange('llm', value)}
              >
                <SelectTrigger
                  id="llm_provider"
                  className={`${THEME.input.select} mt-1`}
                >
                  <SelectValue placeholder="Select LLM Provider" />
                </SelectTrigger>
                <SelectContent className="bg-gray-900 border-white/20">
                  {providers?.llm.providers.map((provider) => (
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

            {agent.llm_provider && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-cyan-500/30">
                {Object.entries(providerFields.llm).map(([field, fieldDef]) => (
                  <div key={field}>
                    <Label
                      htmlFor={`llm_${field}`}
                      className={THEME.text.secondary}
                    >
                      {fieldDef.label}
                    </Label>
                    <Input
                      id={`llm_${field}`}
                      type={fieldDef.type === 'password' ? 'password' : 'text'}
                      value={
                        typeof field === 'string' &&
                        agent.llm_config &&
                        (agent.llm_config as Record<string, string>)[field]
                          ? (agent.llm_config as Record<string, string>)[field]
                          : ''
                      }
                      onChange={(e) =>
                        handleConfigChange('llm_config', field, e.target.value)
                      }
                      placeholder={`Enter ${fieldDef.label}`}
                      className={`${THEME.input.base} mt-1`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* TTS Configuration */}
          <div className="space-y-4 pt-6 border-t border-white/10">
            <h3 className={`text-lg font-semibold ${THEME.text.accent}`}>
              TTS Provider
            </h3>

            <div>
              <Label htmlFor="tts_provider" className={THEME.text.secondary}>
                Provider
              </Label>
              <Select
                value={agent.tts_provider || ''}
                onValueChange={(value) => handleProviderChange('tts', value)}
              >
                <SelectTrigger
                  id="tts_provider"
                  className={`${THEME.input.select} mt-1`}
                >
                  <SelectValue placeholder="Select TTS Provider" />
                </SelectTrigger>
                <SelectContent className="bg-gray-900 border-white/20">
                  {providers?.tts.providers.map((provider) => (
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

            {agent.tts_provider && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-purple-500/30">
                {Object.entries(providerFields.tts).map(([field, fieldDef]) => (
                  <div key={field}>
                    <Label
                      htmlFor={`tts_${field}`}
                      className={THEME.text.secondary}
                    >
                      {fieldDef.label}
                    </Label>
                    <Input
                      id={`tts_${field}`}
                      type={fieldDef.type === 'password' ? 'password' : 'text'}
                      value={
                        typeof field === 'string' &&
                        agent.tts_config &&
                        (agent.tts_config as Record<string, string>)[field]
                          ? (agent.tts_config as Record<string, string>)[field]
                          : ''
                      }
                      onChange={(e) =>
                        handleConfigChange('tts_config', field, e.target.value)
                      }
                      placeholder={`Enter ${fieldDef.label}`}
                      className={`${THEME.input.base} mt-1`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* STT Configuration */}
          <div className="space-y-4 pt-6 border-t border-white/10">
            <h3 className={`text-lg font-semibold ${THEME.text.accent}`}>
              STT Provider
            </h3>

            <div>
              <Label htmlFor="stt_provider" className={THEME.text.secondary}>
                Provider
              </Label>
              <Select
                value={agent.stt_provider || ''}
                onValueChange={(value) => handleProviderChange('stt', value)}
              >
                <SelectTrigger
                  id="stt_provider"
                  className={`${THEME.input.select} mt-1`}
                >
                  <SelectValue placeholder="Select STT Provider" />
                </SelectTrigger>
                <SelectContent className="bg-gray-900 border-white/20">
                  {providers?.stt.providers.map((provider) => (
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

            {agent.stt_provider && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-orange-500/30">
                {Object.entries(providerFields.stt).map(([field, fieldDef]) => (
                  <div key={field}>
                    <Label
                      htmlFor={`stt_${field}`}
                      className={THEME.text.secondary}
                    >
                      {fieldDef.label}
                    </Label>
                    <Input
                      id={`stt_${field}`}
                      type={fieldDef.type === 'password' ? 'password' : 'text'}
                      value={
                        typeof field === 'string' &&
                        agent.stt_config &&
                        (agent.stt_config as Record<string, string>)[field]
                          ? (agent.stt_config as Record<string, string>)[field]
                          : ''
                      }
                      onChange={(e) =>
                        handleConfigChange('stt_config', field, e.target.value)
                      }
                      placeholder={`Enter ${fieldDef.label}`}
                      className={`${THEME.input.base} mt-1`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RAG Configuration */}
          <div className="space-y-4 pt-6 border-t border-white/10">
            <h3
              className={`text-lg font-semibold ${THEME.text.accent} flex items-center gap-2`}
            >
              <Database className="w-5 h-5" />
              RAG Configuration
            </h3>

            <div>
              <Label htmlFor="rag_config_id" className={THEME.text.secondary}>
                RAG Configuration (Optional)
              </Label>
              <Select
                value={
                  agent.rag_config_id === null || agent.rag_config_id === ''
                    ? 'none'
                    : agent.rag_config_id
                }
                onValueChange={(value) =>
                  handleInputChange(
                    'rag_config_id',
                    value === 'none' ? null : value
                  )
                }
              >
                <SelectTrigger
                  id="rag_config_id"
                  className={`${THEME.input.select} mt-1`}
                >
                  <SelectValue placeholder="Select RAG Configuration (optional)" />
                </SelectTrigger>
                <SelectContent className="bg-gray-900 border-white/20">
                  <SelectItem value="none" className="text-white">
                    None
                  </SelectItem>
                  {ragConfigs.map((config) => (
                    <SelectItem
                      key={config.id}
                      value={config.id}
                      className="text-white"
                    >
                      {config.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="mt-2 text-sm">
                <a
                  href="/rag/admin"
                  className={`${THEME.text.accent} hover:underline`}
                >
                  → Manage RAG configurations
                </a>
              </div>
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
              {saving ? 'Saving...' : 'Save Agent'}
            </Button>

            <Button
              variant="outline"
              onClick={() => {
                if (isModalMode) {
                  closeModal();
                } else {
                  window.location.href = '/agent/admin';
                }
              }}
              className={`${THEME.button.ghost} rounded-full px-6 flex items-center gap-2`}
            >
              <ArrowLeft className="w-4 h-4" />
              Cancel
            </Button>
          </div>
        </div>
      </PageCard>
    </>
  );

  if (loading) {
    return (
      <PageLayout
        title={agentId ? 'Edit Agent' : 'Create Agent'}
        icon={<Bot className="w-8 h-8" />}
      >
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
            <p className={THEME.text.secondary}>Loading agent...</p>
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
        title={agentId ? 'Edit Agent' : 'Create Agent'}
      >
        {content}
      </ModalWrapper>
    );
  }

  return (
    <PageLayout
      title={agentId ? 'Edit Agent' : 'Create Agent'}
      icon={<Bot className="w-8 h-8" />}
      breadcrumbs={[
        { label: 'Agents', href: '/agent/admin' },
        { label: agentId ? 'Edit' : 'Create', href: '#' },
      ]}
    >
      {content}
    </PageLayout>
  );
}
