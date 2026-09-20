import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  allowedDevOrigins: ["localhost", "127.0.0.1", "platform.localhost"],
  skipTrailingSlashRedirect: true,
  turbopack: { root: process.cwd() },
  reactStrictMode: true,
};

export default nextConfig;
