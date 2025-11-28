/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // Make environment info available to the frontend
    NEXT_PUBLIC_ENVIRONMENT_TYPE: process.env.NODE_ENV === 'development' ? 'local' : 'docker',
    NEXT_PUBLIC_VOICEBOT_API_URL: 'http://localhost:8001',
    NEXT_PUBLIC_LIVEKIT_WS_URL: 'ws://localhost:7880',
  },
  experimental: {
    serverComponentsExternalPackages: []
  },
  // Configure for dual-mode development
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  }
};

export default nextConfig;