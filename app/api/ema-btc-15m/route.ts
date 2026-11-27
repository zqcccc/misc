import { NextResponse } from 'next/server'

// BTC 15m 研究数据 API 已下线：读取 data/ema-btc-15m.json 的旧执行路径已删除，
// 统一返回 404。历史实现见仓库历史。
export function GET() {
  return NextResponse.json({ message: 'Not Found' }, { status: 404 })
}
