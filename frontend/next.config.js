/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // Required for Docker deployment
  // Next 16 dropped ESLint from `next build`; it no longer reads this key
  // (Next was warning "Unrecognized key(s): 'eslint'" on every dev start).
  // Run `next lint` / your editor's ESLint integration separately instead.
  typescript: {
    ignoreBuildErrors: false,
  },
}

module.exports = nextConfig
