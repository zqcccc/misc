import path from 'node:path'
import { deliverableJsonResponse } from '@/lib/deliverable-json'

const DELIVERABLES_DIR = path.join(process.cwd(), 'deliverables')
const BACKTEST_FILE = path.join(DELIVERABLES_DIR, 'smallcap_strategy.json')

export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(request: Request) {
  return deliverableJsonResponse(request, BACKTEST_FILE)
}
