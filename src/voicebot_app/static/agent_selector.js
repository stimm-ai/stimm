/**
 * Shared Agent Selector Component
 * 
 * This module provides a consistent agent selection interface across all
 * voicebot interfaces (RAG chat, TTS, STT, Voicebot).
 * 
 * Usage:
 * 1. Include this script in your HTML: <script src="/static/agent_selector.js"></script>
 * 2. Add an agent selection dropdown: <select id="agentSelect"></select>
 * 3. Initialize: new AgentSelector('agentSelect', onAgentChangeCallback)
 */

class AgentSelector {
    constructor(selectElementId, onAgentChange = null) {
        this.selectElement = document.getElementById(selectElementId);
        this.onAgentChange = onAgentChange;
        this.availableAgents = [];
        this.currentAgentId = null;
        
        if (!this.selectElement) {
            console.error(`AgentSelector: Element with id '${selectElementId}' not found`);
            return;
        }
        
        this.initialize();
    }
    
    async initialize() {
        // Set initial loading state
        this.selectElement.innerHTML = '<option value="">Loading agents...</option>';
        this.selectElement.disabled = true;
        
        // Set up event listener first
        this.selectElement.addEventListener('change', (e) => this.handleAgentChange(e));
        
        // Load agents
        await this.loadAgents();
        
        // Automatically select the default agent after loading and rendering
        this.selectDefaultAgent();
        
        this.selectElement.disabled = false;
    }

    /**
     * Automatically select the default agent
     */
    selectDefaultAgent() {
        console.log('🔍 Searching for default agent...');
        console.log('📋 Available agents:', this.availableAgents);
        
        const defaultAgent = this.availableAgents.find(agent => agent.is_default);
        if (defaultAgent) {
            this.currentAgentId = defaultAgent.id;
            this.selectElement.value = defaultAgent.id;
            
            console.log(`✅ Default agent found and selected: ${defaultAgent.name} (ID: ${defaultAgent.id})`);
            console.log(`🔧 TTS Provider: ${defaultAgent.tts_provider}`);
            console.log(`🔧 LLM Provider: ${defaultAgent.llm_provider}`);
            console.log(`🔧 STT Provider: ${defaultAgent.stt_provider}`);
            
            // Trigger change event to notify other components
            const event = new Event('change');
            this.selectElement.dispatchEvent(event);
            
            console.log(`🎯 Change event dispatched for agent: ${defaultAgent.name}`);
        } else {
            console.warn('⚠️ No default agent found in available agents');
            console.log('📋 Available agents:', this.availableAgents);
        }
    }
    
    async loadAgents() {
        try {
            const response = await fetch('/api/agents/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            this.availableAgents = await response.json();
            this.renderAgentOptions();
            
        } catch (error) {
            console.error('Error loading agents:', error);
            this.selectElement.innerHTML = '<option value="">Error loading agents</option>';
        }
    }
    
    renderAgentOptions() {
        this.selectElement.innerHTML = '';
        
        // Add all agents - no "Default Agent" option, just the actual agents
        this.availableAgents.forEach(agent => {
            const option = document.createElement('option');
            option.value = agent.id;
            option.textContent = agent.name;
            option.dataset.llmProvider = agent.llm_provider;
            option.dataset.ttsProvider = agent.tts_provider;
            option.dataset.sttProvider = agent.stt_provider;
            
            if (agent.is_default) {
                option.textContent += ' (Default)';
                this.currentAgentId = agent.id;
            }
            
            this.selectElement.appendChild(option);
        });
    }
    
    handleAgentChange(event) {
        this.currentAgentId = event.target.value;
        const selectedAgent = this.availableAgents.find(agent => agent.id === this.currentAgentId);
        
        console.log(`🔄 Agent change event: selectedAgentId=${this.currentAgentId}`);
        console.log(`🔍 Selected agent:`, selectedAgent);
        
        if (this.onAgentChange) {
            console.log(`🎯 Calling onAgentChange callback with agent:`, selectedAgent);
            this.onAgentChange(selectedAgent, this.currentAgentId);
        } else {
            console.warn('⚠️ No onAgentChange callback registered');
        }
        
        // Dispatch custom event for other components to listen to
        const agentChangeEvent = new CustomEvent('agentChanged', {
            detail: {
                agent: selectedAgent,
                agentId: this.currentAgentId
            }
        });
        document.dispatchEvent(agentChangeEvent);
        console.log(`📢 Dispatched agentChanged event for agent:`, selectedAgent);
    }
    
    getCurrentAgent() {
        return this.availableAgents.find(agent => agent.id === this.currentAgentId);
    }
    
    getCurrentAgentId() {
        return this.currentAgentId;
    }
    
    setAgent(agentId) {
        if (this.selectElement) {
            this.selectElement.value = agentId;
            this.currentAgentId = agentId;
            
            // Trigger change event
            const event = new Event('change');
            this.selectElement.dispatchEvent(event);
        }
    }
    
    refresh() {
        return this.loadAgents();
    }
}

// Global agent manager for cross-interface coordination
window.AgentManager = {
    currentAgentId: null,
    availableAgents: [],
    
    async initialize() {
        try {
            const response = await fetch('/api/agents/');
            if (response.ok) {
                this.availableAgents = await response.json();
                const defaultAgent = this.availableAgents.find(agent => agent.is_default);
                if (defaultAgent) {
                    this.currentAgentId = defaultAgent.id;
                }
            }
        } catch (error) {
            console.error('AgentManager: Failed to initialize', error);
        }
    },
    
    setCurrentAgent(agentId) {
        this.currentAgentId = agentId;
        
        // Update all agent selectors on the page
        document.querySelectorAll('#agentSelect').forEach(select => {
            if (select.value !== agentId) {
                select.value = agentId;
                const event = new Event('change');
                select.dispatchEvent(event);
            }
        });
        
        // Dispatch global agent change event
        const agentChangeEvent = new CustomEvent('globalAgentChanged', {
            detail: {
                agentId: agentId,
                agent: this.availableAgents.find(agent => agent.id === agentId)
            }
        });
        document.dispatchEvent(agentChangeEvent);
    },
    
    getCurrentAgent() {
        return this.availableAgents.find(agent => agent.id === this.currentAgentId);
    }
};

// Initialize global agent manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.AgentManager.initialize();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AgentSelector, AgentManager };
}