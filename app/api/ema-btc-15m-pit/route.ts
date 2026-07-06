import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'

export const dynamic = 'force-dynamic'
export const revalidate = 0

const DATA_FILE = path.join(process.cwd(), 'data', 'ema-btc-15m-pit.json')

export async function GET() {
  try {
    const raw = await fs.readFile(DATA_FILE, 'utf-8')
    return new NextResponse(raw, {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store, max-age=0',
      },
    })
  } catch {
    return NextResponse.json(
      {
        message:
          'step8 PIT 数据未生成。请运行: /Users/gongzhao/.workbuddy/binaries/python/envs/default/bin/python btc_ema_15m/export_step8_frontend_json.py',
      },
      { status: 503 },
    )
  }
}
