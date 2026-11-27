import { NextResponse } from 'next/server'

// EMA 回测数据 API 已下线：扫描 scripts/_cache_xag_ema_monitor 缓存文件并与
// daemon 实时数据合并的旧执行路径已删除，统一返回 404。历史实现见仓库历史。
export function GET() {
  return NextResponse.json({ message: 'Not Found' }, { status: 404 })
}
