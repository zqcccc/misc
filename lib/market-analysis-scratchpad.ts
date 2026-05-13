import { appendFile, mkdir } from 'fs/promises'
import { join } from 'path'

export type MarketAnalysisScratchpadEventType =
  | 'init'
  | 'validation'
  | 'tool_result'
  | 'write_result'
  | 'error'

const SCRATCHPAD_DIR = join(process.cwd(), 'tmp', 'analysis-runs')
const SAFE_RUN_ID_PATTERN = /[^a-zA-Z0-9_.-]/g
const MAX_FILE_NAME_LENGTH = 160
const EMPTY_RUN_ID_FILE_NAME = 'unknown-run'

function scratchpadPath(runId: string) {
  const safeRunId = runId
    .trim()
    .replace(SAFE_RUN_ID_PATTERN, '_')
    .slice(0, MAX_FILE_NAME_LENGTH) || EMPTY_RUN_ID_FILE_NAME

  return join(SCRATCHPAD_DIR, `${safeRunId}.jsonl`)
}

export async function recordMarketAnalysisScratchpad(
  runId: string | null | undefined,
  type: MarketAnalysisScratchpadEventType,
  data: Record<string, unknown> = {},
) {
  if (!runId) return

  try {
    await mkdir(SCRATCHPAD_DIR, { recursive: true })
    await appendFile(
      scratchpadPath(runId),
      `${JSON.stringify({
        type,
        timestamp: new Date().toISOString(),
        runId,
        ...data,
      })}\n`,
      'utf8',
    )
  } catch (error) {
    console.warn('[market-analysis] scratchpad write failed:', error)
  }
}
