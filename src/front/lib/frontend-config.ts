/**
 * Frontend Environment Configuration
 * Handles SSR vs Client-Side environment differences using Next.js public environment variables.
 */

// These variables are exposed to the browser and must be prefixed with NEXT_PUBLIC_
// They should be defined in `.env.local` for local development
// and in docker-compose.yml for containerized environments.
const backendHostname = process.env.NEXT_PUBLIC_BACKEND_HOSTNAME || 'localhost';
const liveKitHostname = process.env.NEXT_PUBLIC_LIVEKIT_HOSTNAME || 'localhost';

const isServerSide = typeof window === 'undefined';

// Log the configuration once for debugging purposes
console.log(`Frontend Config Initialized (isServerSide: ${isServerSide})`);
console.log(`- Backend Host: ${backendHostname}`);
console.log(`- LiveKit Host: ${liveKitHostname}`);


// Main configuration object
export const config = {
  /**
   * URLs for server-side code (e.g., API routes, getStaticProps).
   * Uses service names when running in Docker, localhost otherwise.
   */
  backend: {
    apiUrl: `http://${backendHostname}:8001`,
  },

  /**
   * URLs for the browser.
   * Always connects to localhost, assuming Docker ports are exposed.
   */
  browser: {
    stimmApiUrl: 'http://localhost:8001',
    liveKitWsUrl: `ws://localhost:7880`,
  },
};

// API Client using the configuration
export class FrontendApiClient {
  /**
   * Make API calls with environment-aware URL handling.
   */
  async apiCall(endpoint: string, options: RequestInit = {}): Promise<Response> {
    // In a universal component, we check if we're on the client or server.
    const baseUrl = isServerSide ? config.backend.apiUrl : config.browser.stimmApiUrl;
    const url = `${baseUrl}${endpoint}`;
    
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    
    return fetch(url, {
      ...options,
      headers,
    });
  }
  
  /**
   * Get LiveKit WebSocket URL.
   */
  getLiveKitUrl(): string {
    // The browser will always connect to localhost. Server-side connections to LiveKit
    // would need a different URL, but this client is primarily for the browser.
    return config.browser.liveKitWsUrl;
  }
}

// Export a singleton instance of the API client
export const apiClient = new FrontendApiClient();