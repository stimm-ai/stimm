# Agent Management System Documentation

## Overview

The Agent Management System replaces the environment variable-based provider configuration in voicebot-app with a dynamic, database-driven approach. This allows for runtime creation, configuration, and switching of agents without requiring service restarts.

## Key Features

- **Multi-Agent Support**: Create and manage multiple agents with different provider configurations
- **Runtime Configuration**: Change agent settings without restarting the application
- **Default Agent Management**: Set a default agent for automatic selection
- **Provider Flexibility**: Configure different LLM, TTS, and STT providers per agent
- **Web Administration Interface**: User-friendly web UI for agent management
- **Backward Compatibility**: Fallback to environment variables when no agents are configured
- **Database Persistence**: PostgreSQL database for storing agent configurations

## Architecture

### Database Schema

The system uses PostgreSQL with the following main tables:

- **agents**: Stores agent metadata (name, description, default status)
- **llm_providers**: LLM provider configurations per agent
- **tts_providers**: TTS provider configurations per agent  
- **stt_providers**: STT provider configurations per agent

### Core Components

1. **AgentService**: CRUD operations for agents and provider configurations
2. **AgentManager**: Runtime agent resolution and configuration caching
3. **Agent Routes**: REST API endpoints for agent management
4. **Agent Web Routes**: Web interface for agent administration
5. **Dev Agent Creator**: Automatic creation of default agent from environment variables

## API Endpoints

### Agent Management

- `GET /api/agents/` - List all agents
- `GET /api/agents/{agent_id}` - Get specific agent
- `POST /api/agents/` - Create new agent
- `PUT /api/agents/{agent_id}` - Update agent
- `DELETE /api/agents/{agent_id}` - Delete agent
- `GET /api/agents/default/current` - Get current default agent
- `PUT /api/agents/{agent_id}/set-default` - Set agent as default

### Web Interface

- `GET /agent/admin` - Agent administration dashboard
- `GET /agent/create` - Create new agent form
- `GET /agent/edit/{agent_id}` - Edit agent form

## Integration with Services

### LLM Service Integration

The LLM service now supports agent-based configuration:

```python
# Get agent configuration
agent_config = await agent_manager.get_agent_config(agent_id)

# Initialize provider with agent config
provider = LLMProviderFactory.create_provider(agent_config.llm_provider, agent_config.llm_config)
```

### TTS Service Integration

TTS service supports agent-based voice selection:

```python
# Get agent TTS configuration
tts_config = await agent_manager.get_tts_config(agent_id)

# Initialize TTS provider
tts_provider = TTSProviderFactory.create_provider(tts_config.provider_type, tts_config)
```

### STT Service Integration

STT service supports agent-based model selection:

```python
# Get agent STT configuration
stt_config = await agent_manager.get_stt_config(agent_id)

# Initialize STT provider
stt_provider = STTProviderFactory.create_provider(stt_config.provider_type, stt_config)
```

## Supported Providers

### LLM Providers
- OpenAI (GPT models)
- Groq
- Mistral
- OpenRouter
- Llama.cpp (local)
- OpenAI-compatible APIs

### TTS Providers
- ElevenLabs
- Deepgram
- Async AI
- Kokoro Local

### STT Providers
- Deepgram
- Whisper Local

## Configuration

### Environment Variables

The system maintains backward compatibility with these environment variables:

- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`
- `TTS_PROVIDER`, `TTS_VOICE`, `TTS_API_KEY`, `TTS_BASE_URL`  
- `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY`, `STT_BASE_URL`

### Database Configuration

- `DATABASE_URL`: PostgreSQL connection string
- Database tables are automatically created via Alembic migrations

## Usage Examples

### Creating an Agent via API

```bash
curl -X POST http://localhost:8001/api/agents/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Agent",
    "description": "Production agent with OpenAI and ElevenLabs",
    "llm_provider_type": "openai",
    "llm_model_name": "gpt-4",
    "llm_api_key": "sk-...",
    "tts_provider_type": "elevenlabs", 
    "tts_voice_name": "Rachel",
    "tts_api_key": "xi-...",
    "stt_provider_type": "deepgram",
    "stt_model_name": "nova-2",
    "stt_api_key": "dg-...",
    "is_default": true
  }'
```

### Switching Agents at Runtime

```python
# In service code
async def process_request(text: str, agent_id: Optional[str] = None):
    agent_config = await agent_manager.get_agent_config(agent_id)
    # Use agent_config for provider initialization
```

## Web Interface

### Agent Administration Dashboard

Accessible at `http://localhost:8001/agent/admin`

Features:
- View all agents with provider configurations
- Set default agent
- Edit existing agents
- Delete agents
- Create new agents

### Agent Creation/Edit Form

Accessible at `http://localhost:8001/agent/create` and `/agent/edit/{id}`

Features:
- Configure agent name and description
- Select LLM/TTS/STT providers
- Configure provider-specific settings
- Set as default agent

## Migration from Environment Variables

1. **Automatic Migration**: On first startup, the system creates a default agent from environment variables
2. **Backward Compatibility**: Services fall back to environment variables if no agents exist
3. **Gradual Transition**: You can continue using environment variables while testing the agent system

## Development Workflow

### Adding New Providers

1. **Update Database Schema**: Add new provider type to appropriate provider table
2. **Update Models**: Add new provider type to Pydantic models
3. **Update Forms**: Add new provider to web interface forms
4. **Update Service Integration**: Ensure service can handle new provider type

### Testing

```bash
# Test API endpoints
curl http://localhost:8001/api/agents/

# Test web interface
curl http://localhost:8001/agent/admin

# Test service integration
curl http://localhost:8001/rag/chat/stream
```

## Troubleshooting

### Common Issues

1. **Database Connection**: Ensure PostgreSQL is running and DATABASE_URL is correct
2. **Template Errors**: Check template paths in web routes
3. **Provider Initialization**: Verify provider configurations in database
4. **Agent Resolution**: Check default agent settings

### Logs

Check application logs for:
- Agent initialization errors
- Database connection issues
- Provider configuration problems

## Performance Considerations

- **Caching**: Agent configurations are cached with TTL for performance
- **Connection Pooling**: Database connections are pooled for efficiency
- **Lazy Loading**: Providers are initialized on first use

## Security

- **API Key Storage**: API keys are stored encrypted in the database
- **Input Validation**: All inputs are validated using Pydantic models
- **SQL Injection Protection**: Uses SQLAlchemy ORM with parameterized queries

## Future Enhancements

- **User Management**: Multi-user support with IAM integration
- **Agent Templates**: Pre-configured agent templates
- **Performance Metrics**: Agent usage and performance tracking
- **Backup/Restore**: Agent configuration backup functionality