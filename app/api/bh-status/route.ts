import { NextResponse } from 'next/server'

// B&H 看盘数据 API 已下线：读取 deliverables 并按 refresh=1 spawn Python 重算的
// 旧执行路径已删除，统一返回 404。历史实现见仓库历史。
export function GET() {
  return NextResponse.json({ message: 'Not Found' }, { status: 404 })
}
