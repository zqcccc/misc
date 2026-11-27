import { NextResponse } from 'next/server'

// TRHRP 回测数据 API 已下线：读取 deliverables 的旧执行路径已删除，统一返回 404。
// 历史实现见仓库历史。
export function GET() {
  return NextResponse.json({ message: 'Not Found' }, { status: 404 })
}
