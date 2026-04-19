/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  compress: true,
  images: {
    formats: ['image/avif', 'image/webp'],
  },
  experimental: {
    optimizePackageImports: [
      '@dnd-kit/core',
      '@dnd-kit/sortable',
      '@dnd-kit/modifiers',
      'ahooks',
      'echarts',
      'dayjs',
    ],
  },
}

module.exports = nextConfig
