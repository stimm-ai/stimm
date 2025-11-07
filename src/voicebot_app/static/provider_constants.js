/**
 * Provider Constants - Immutable provider-level constants for JavaScript
 *
 * This file loads provider constants from the shared JSON file via API.
 * These are NOT fallback defaults - they are fixed values that define provider behavior.
 */

// Global provider constants (will be loaded on demand)
window.ProviderConstants = {
    TTS: {},
    STT: {},
    LLM: {}
};

/**
 * Load provider constants from the server
 * @returns {Promise<Object>} Provider constants
 */
async function loadProviderConstants() {
    try {
        const response = await fetch('/api/provider-constants');
        if (!response.ok) {
            throw new Error(`Failed to load provider constants: ${response.status}`);
        }
        const constants = await response.json();
        
        // Update global constants
        window.ProviderConstants.TTS = constants.tts || {};
        window.ProviderConstants.STT = constants.stt || {};
        window.ProviderConstants.LLM = constants.llm || {};
        
        console.log('✅ Provider constants loaded successfully');
        return constants;
    } catch (error) {
        console.error('❌ Failed to load provider constants:', error);
        // Return empty constants to avoid breaking the application
        return { tts: {}, stt: {}, llm: {} };
    }
}

/**
 * Get provider constants for a specific provider
 * @param {string} providerType - 'tts', 'stt', or 'llm'
 * @param {string} providerName - Provider name (e.g., 'kokoro.local')
 * @returns {Object|null} Provider constants or null if not found
 */
function getProviderConstants(providerType, providerName) {
    const constants = window.ProviderConstants[providerType.toUpperCase()];
    return constants ? constants[providerName] : null;
}

// Export for usage
window.loadProviderConstants = loadProviderConstants;
window.getProviderConstants = getProviderConstants;

// Load constants when the script is loaded
document.addEventListener('DOMContentLoaded', () => {
    loadProviderConstants().catch(error => {
        console.error('Failed to load provider constants on page load:', error);
    });
});