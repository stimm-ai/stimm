import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/agent/:path*',
        destination: 'http://localhost:8001/agent/:path*',
      },
    ];
  },
};

export default nextConfig;
