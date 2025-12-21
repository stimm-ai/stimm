/**
 * Frontend Environment Configuration for Dual-Mode Operation
 * Handles SSR vs Client-Side environment differences
 */

interface FrontendEnvironmentConfig {
  // Backend API configuration
  backend: {
    apiBaseUrl: string; // For SSR: environment-aware, Client: always localhost
    webSocketUrl: string; // For WebSocket connections
    liveKitUrl: string; // For LiveKit connections
  };

  // Service configuration
  services: {
    stimmApiUrl: string; // SSR + Client: localhost:8001
    liveKitWsUrl: string; // SSR + Client: localhost:7880
  };

  // Environment metadata
  metadata: {
    isServerSide: boolean;
    isDockerEnvironment: boolean;
    environmentType: 'local' | 'docker';
  };
}

/**
 * Detect server-side environment (for SSR)
 */
function detectServerEnvironment(): { isDocker: boolean; hostname: string } {
  // Check if we're running on server-side (SSR)
  const isServerSide = typeof window === 'undefined';

  if (!isServerSide) {
    return {
      isDocker: false,
      hostname: 'localhost',
    };
  }

  // Server-side environment detection (Node.js)
  try {
    // Check for .dockerenv file
    const fs = require('fs');

    if (fs.existsSync('/.dockerenv')) {
      return {
        isDocker: true,
        hostname: 'stimm',
      };
    }

    // Check for Docker environment variables
    const dockerEnvVars = [
      'DOCKER_CONTAINER',
      'COMPOSE_SERVICE_NAME',
      'DOCKER_SERVICE_NAME',
    ];

    for (const envVar of dockerEnvVars) {
      // Validate envVar to prevent object injection vulnerabilities
      if (
        typeof envVar === 'string' &&
        envVar.length > 0 &&
        dockerEnvVars.includes(envVar) &&
        process.env[envVar]
      ) {
        return {
          isDocker: true,
          hostname: 'stimm',
        };
      }
    }

    // Check cgroup for container indicators
    if (fs.existsSync('/proc/1/cgroup')) {
      const cgroupContent = fs.readFileSync('/proc/1/cgroup', 'utf8');
      const dockerPatterns = ['docker', 'lxc', 'kubepods', 'containerd'];

      for (const pattern of dockerPatterns) {
        if (cgroupContent.includes(pattern)) {
          return {
            isDocker: true,
            hostname: 'stimm',
          };
        }
      }
    }
  } catch (error) {
    console.warn('Could not detect server environment:', error);
  }

  // Default to local environment
  return {
    isDocker: false,
    hostname: 'localhost',
  };
}

/**
 * Create frontend environment configuration
 */
export function createFrontendEnvironmentConfig(): FrontendEnvironmentConfig {
  const isServerSide = typeof window === 'undefined';
  const serverEnv = detectServerEnvironment();

  // SSR Environment (Server-Side Rendering)
  // - Uses container names in Docker dev
  // - Uses localhost in local dev
  const ssrBackendHost = serverEnv.hostname;

  // Client-side Environment (Browser)
  // - Always uses localhost for API calls
  const clientBackendHost = 'localhost';

  // Backend API configuration
  const backendApiBaseUrl = isServerSide
    ? `http://${ssrBackendHost}:8001` // SSR: environment-aware
    : `http://${clientBackendHost}:8001`; // Client: always localhost

  const backendWebSocketUrl = isServerSide
    ? `ws://${ssrBackendHost}:8001` // SSR: environment-aware
    : `ws://${clientBackendHost}:8001`; // Client: always localhost

  const backendLiveKitUrl = isServerSide
    ? `ws://${ssrBackendHost}:7880` // SSR: environment-aware
    : `ws://${clientBackendHost}:7880`; // Client: always localhost

  return {
    backend: {
      apiBaseUrl: backendApiBaseUrl,
      webSocketUrl: backendWebSocketUrl,
      liveKitUrl: backendLiveKitUrl,
    },
    services: {
      stimmApiUrl: `http://localhost:8001`, // Always localhost
      liveKitWsUrl: `ws://localhost:7880`, // Always localhost
    },
    metadata: {
      isServerSide,
      isDockerEnvironment: serverEnv.isDocker,
      environmentType: serverEnv.isDocker ? 'docker' : 'local',
    },
  };
}

// Singleton instance
let frontendConfig: FrontendEnvironmentConfig | null = null;

/**
 * Get the current frontend environment configuration
 */
export function getFrontendEnvironmentConfig(): FrontendEnvironmentConfig {
  if (!frontendConfig) {
    frontendConfig = createFrontendEnvironmentConfig();
  }
  return frontendConfig;
}

/**
 * Environment-aware API client for frontend
 */
export class FrontendApiClient {
  private config: FrontendEnvironmentConfig;

  constructor() {
    this.config = getFrontendEnvironmentConfig();
  }

  /**
   * Make API calls with environment-aware URL handling
   */
  async apiCall(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const isServerSide = typeof window === 'undefined';

    // For client-side calls, always use localhost
    // For SSR calls, use environment-aware URLs
    const baseUrl = isServerSide
      ? this.config.backend.apiBaseUrl
      : this.config.services.stimmApiUrl;

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
   * Get LiveKit WebSocket URL (always localhost for both SSR and client)
   */
  getLiveKitUrl(): string {
    return this.config.services.liveKitWsUrl;
  }

  /**
   * Get environment information
   */
  getEnvironmentInfo() {
    return this.config.metadata;
  }
}

// Export singleton instance
export const frontendApiClient = new FrontendApiClient();

/**
 * Environment detection hook for React components
 */
export function useEnvironmentDetection() {
  const config = getFrontendEnvironmentConfig();

  return {
    isServerSide: config.metadata.isServerSide,
    isDockerEnvironment: config.metadata.isDockerEnvironment,
    environmentType: config.metadata.environmentType,
    backendUrl: config.backend.apiBaseUrl,
    liveKitUrl: config.services.liveKitWsUrl,
  };
}

export type { FrontendEnvironmentConfig };
