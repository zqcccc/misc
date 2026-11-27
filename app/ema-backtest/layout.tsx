import { notFound } from 'next/navigation'

// EMA 回测公开页（含 btc-15m、btc-15m-min、diag、pit 等全部子页面）已下线：
// 父 layout 统一返回 404，子页面与共享研究实现保留作档案，不再对外渲染。
export default function EmaBacktestLayout() {
  return notFound()
}
