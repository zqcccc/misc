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
  // 文章正文在运行时用 fs 读 posts/ (app/api/post/lib.ts), 静态追踪追不到;
  // lib 里已用 turbopackIgnore 阻止动态 fs 访问把整个仓库追进 standalone,
  // 这里按消费路由精确把文章源打进产物。plusPosts 由容器运行时挂载, 不打进镜像。
  outputFileTracingIncludes: {
    '/': ['./posts/**/*'],
    '/post/\\[\\.\\.\\.id\\]': ['./posts/**/*'],
    '/sitemap.xml': ['./posts/**/*'],
  },
  experimental: {
    optimizePackageImports: [
      '@dnd-kit/core',
      '@dnd-kit/sortable',
      'ahooks',
      'echarts',
    ],
  },
}

module.exports = nextConfig
