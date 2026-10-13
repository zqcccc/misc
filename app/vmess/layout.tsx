import { notFound } from 'next/navigation'

// AdSense 重审前下架：代理节点订阅管理工具，直接访问返回 404。
// 自用恢复时删除 notFound() 这一行即可，页面代码原样保留。
export const metadata = {
  title: '内部工具',
  robots: { index: false, follow: false },
}

export default function EnLayout({ children }: { children: React.ReactNode }) {
  notFound()
  return children
}
