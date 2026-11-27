import { notFound } from 'next/navigation'

// TRHRP 回测公开页已下线：本 layout 对所有请求统一返回 404，
// page.tsx 等研究实现保留作档案，不再对外渲染。
export default function TrhrpLayout() {
  return notFound()
}
