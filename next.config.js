/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  compress: true,
  cacheMaxMemorySize: 0,
  // 允许 127.0.0.1 / 局域网 IP / 端口差异访问 dev 资源 (含 _next/webpack-hmr),
  // 浏览器扩展 (沉浸式翻译 / Userscript 注入) 才不会把 HMR socket 拦成跨域.
  allowedDevOrigins: ['127.0.0.1', 'localhost', '0.0.0.0'],
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
