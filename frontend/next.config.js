/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // Required for Docker deployment
  eslint: {
    ignoreDuringBuilds: true, // Optional: skip ESLint during builds
  },
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig
