import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'

const DELIVERABLES_DIR = path.join(process.cwd(), 'deliverables')
const BACKTEST_FILE = path.join(DELIVERABLES_DIR, 'ashare_strategy_backtest.json')

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET() {
  try {
    const raw = await fs.readFile(BACKTEST_FILE, 'utf-8')
    const data = JSON.parse(raw)
    return NextResponse.json({ success: true, data })
  } catch (err: any) {
    return NextResponse.json(
      { success: false, error: err.message || 'Failed to read backtest data' },
      { status: 500 }
    )
  }
}
