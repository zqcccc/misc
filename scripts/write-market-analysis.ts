import { readFile } from 'fs/promises'
import { PrismaClient } from '@prisma/client'
import {
  writeMarketAnalysisCrossMarket,
  type CrossMarketWriteInput,
} from '../lib/market-analysis'

const FLAG_DRY_RUN = '--dry-run'
const FLAG_HELP = '--help'
const FLAG_NO_VERIFY = '--no-verify'
const STDIN_FILE_PATH = '-'
const SUCCESS_EXIT_CODE = 0
const FAILURE_EXIT_CODE = 1
const VALID_MARKETS = new Set(['us', 'hk', 'a', 'cn'])
const VALID_ENTRY_TYPES = new Set(['manual', 'ai-generated', 'ai-deep-analysis', 'analysis', 'research'])
const VALID_VISIBILITIES = new Set(['draft', 'published', 'archived'])
const VALID_EXPLANATION_TYPES = new Set(['price', 'profit', 'valuation', 'business'])
const VALID_IMPACT_DIRECTIONS = new Set(['positive', 'neutral', 'negative'])

const prisma = new PrismaClient()

type CliOptions = {
  filePath: string
  dryRun: boolean
  verify: boolean
}

type VerifyResult = {
  success: boolean
  pePageVisible: boolean
  company: {
    id: string
    symbol: string
    market: string
    name: string
  }
  dataStatus: {
    isVisible: boolean
    hasPublishedExploration: boolean
    hasValuation: boolean
    hasExplanations: boolean
    explorationsCount: number
    valuationsCount: number
    explanationsCount: number
  }
  checkList: {
    canShowInSidebar: boolean
    canShowValuationCard: boolean
    canShowExploration: boolean
    canShowExplanations: boolean
    fullyComplete: boolean
  }
  runData?: {
    runId: string
    hasExploration: boolean
    hasValuation: boolean
    explanationsCount: number
    explorationId: string | null
    valuationId: string | null
  }
}

function printUsage() {
  console.log(`Usage: npm run market-analysis:write -- <payload.json> [--dry-run] [--no-verify]

Examples:
  npm run market-analysis:write -- tmp/aapl-analysis.json
  npm run market-analysis:write -- tmp/aapl-analysis.json --dry-run

The payload must match CrossMarketWriteInput and include runId, company.symbol, company.market, and company.name.`)
}

function parseArgs(args: string[]): CliOptions | null {
  if (args.includes(FLAG_HELP)) {
    printUsage()
    return null
  }

  const filePaths = args.filter((arg) => !arg.startsWith('--'))
  const unknownFlags = args.filter(
    (arg) =>
      arg.startsWith('--') &&
      arg !== FLAG_DRY_RUN &&
      arg !== FLAG_HELP &&
      arg !== FLAG_NO_VERIFY,
  )

  if (unknownFlags.length > 0) {
    throw new Error(`未知参数: ${unknownFlags.join(', ')}`)
  }

  if (filePaths.length !== 1) {
    throw new Error('请提供且只提供一个 payload JSON 文件路径')
  }

  return {
    filePath: filePaths[0],
    dryRun: args.includes(FLAG_DRY_RUN),
    verify: !args.includes(FLAG_NO_VERIFY),
  }
}

async function readStdin() {
  return new Promise<string>((resolve, reject) => {
    let data = ''
    process.stdin.setEncoding('utf8')
    process.stdin.on('data', (chunk) => {
      data += chunk
    })
    process.stdin.on('end', () => resolve(data))
    process.stdin.on('error', reject)
  })
}

async function readPayload(filePath: string) {
  const raw = filePath === STDIN_FILE_PATH
    ? await readStdin()
    : await readFile(filePath, 'utf8')

  try {
    return JSON.parse(raw) as CrossMarketWriteInput
  } catch (error) {
    throw new Error(`payload 不是合法 JSON: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function assertPlainObject(value: unknown, fieldName: string): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${fieldName} 必须是对象`)
  }
}

function assertNonEmptyString(value: unknown, fieldName: string) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${fieldName} 必须是非空字符串`)
  }
}

function assertOptionalNumberInRange(value: unknown, fieldName: string, min: number, max: number) {
  if (value === undefined || value === null) return
  if (typeof value !== 'number' || Number.isNaN(value) || value < min || value > max) {
    throw new Error(`${fieldName} 必须是 ${min}-${max} 之间的数字`)
  }
}

function assertOptionalEnum(value: unknown, fieldName: string, validValues: Set<string>) {
  if (value === undefined || value === null) return
  if (typeof value !== 'string' || !validValues.has(value)) {
    throw new Error(`${fieldName} 必须是以下值之一: ${Array.from(validValues).join(', ')}`)
  }
}

function assertOptionalDate(value: unknown, fieldName: string) {
  if (value === undefined || value === null) return
  if (typeof value !== 'string' && !(value instanceof Date)) {
    throw new Error(`${fieldName} 必须是日期字符串`)
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    throw new Error(`${fieldName} 不是有效日期`)
  }
}

function validatePayload(payload: CrossMarketWriteInput) {
  assertPlainObject(payload, 'payload')
  assertNonEmptyString(payload.runId, 'runId')

  assertPlainObject(payload.company, 'company')
  assertNonEmptyString(payload.company.symbol, 'company.symbol')
  assertNonEmptyString(payload.company.market, 'company.market')
  assertNonEmptyString(payload.company.name, 'company.name')

  if (!VALID_MARKETS.has(payload.company.market)) {
    throw new Error(`company.market 必须是以下值之一: ${Array.from(VALID_MARKETS).join(', ')}`)
  }

  if (payload.pageEntry) {
    assertPlainObject(payload.pageEntry, 'pageEntry')
    assertNonEmptyString(payload.pageEntry.entryType, 'pageEntry.entryType')
    assertOptionalEnum(payload.pageEntry.entryType, 'pageEntry.entryType', VALID_ENTRY_TYPES)
  }

  if (payload.exploration) {
    assertPlainObject(payload.exploration, 'exploration')
    assertNonEmptyString(payload.exploration.title, 'exploration.title')
    assertNonEmptyString(payload.exploration.summary, 'exploration.summary')
    assertOptionalNumberInRange(payload.exploration.score, 'exploration.score', 0, 100)
    assertOptionalNumberInRange(payload.exploration.confidence, 'exploration.confidence', 0, 100)
    assertOptionalEnum(payload.exploration.visibility, 'exploration.visibility', VALID_VISIBILITIES)
  }

  if (payload.valuation) {
    assertPlainObject(payload.valuation, 'valuation')
    assertNonEmptyString(payload.valuation.asOfDate, 'valuation.asOfDate')
    assertOptionalDate(payload.valuation.asOfDate, 'valuation.asOfDate')
    assertOptionalNumberInRange(payload.valuation.profitQualityScore, 'valuation.profitQualityScore', 0, 100)
  }

  if (payload.explanations) {
    if (!Array.isArray(payload.explanations)) {
      throw new Error('explanations 必须是数组')
    }

    const explanationTypes = new Set<string>()
    for (let index = 0; index < payload.explanations.length; index += 1) {
      const explanation = payload.explanations[index]
      assertPlainObject(explanation, `explanations[${index}]`)
      assertNonEmptyString(explanation.explanationType, `explanations[${index}].explanationType`)
      assertNonEmptyString(explanation.title, `explanations[${index}].title`)
      assertNonEmptyString(explanation.body, `explanations[${index}].body`)
      assertOptionalEnum(explanation.explanationType, `explanations[${index}].explanationType`, VALID_EXPLANATION_TYPES)
      assertOptionalEnum(explanation.impactDirection, `explanations[${index}].impactDirection`, VALID_IMPACT_DIRECTIONS)
      assertOptionalNumberInRange(explanation.confidence, `explanations[${index}].confidence`, 0, 100)

      if (explanationTypes.has(explanation.explanationType)) {
        throw new Error(`同一个 runId 下 explanationType 不能重复: ${explanation.explanationType}`)
      }
      explanationTypes.add(explanation.explanationType)
    }
  }
}

async function verifyWrite(input: CrossMarketWriteInput): Promise<VerifyResult> {
  const company = await prisma.company.findUnique({
    where: {
      market_symbol: {
        market: input.company.market,
        symbol: input.company.symbol,
      },
    },
    include: {
      explorations: {
        where: { visibility: 'published' },
        orderBy: [{ pinned: 'desc' }, { createdAt: 'desc' }],
      },
      valuations: {
        orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
      },
      explanations: {
        where: { isCurrent: true },
        orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
      },
    },
  })

  if (!company) {
    throw new Error(`验证失败：未找到公司 ${input.company.market}:${input.company.symbol}`)
  }

  const hasPublishedExploration = company.explorations.length > 0
  const hasValuation = company.valuations.length > 0
  const hasExplanations = company.explanations.length > 0

  const result: VerifyResult = {
    success: true,
    pePageVisible: company.visible,
    company: {
      id: company.id,
      symbol: company.symbol,
      market: company.market,
      name: company.name,
    },
    dataStatus: {
      isVisible: company.visible,
      hasPublishedExploration,
      hasValuation,
      hasExplanations,
      explorationsCount: company.explorations.length,
      valuationsCount: company.valuations.length,
      explanationsCount: company.explanations.length,
    },
    checkList: {
      canShowInSidebar: company.visible,
      canShowValuationCard: company.visible && hasValuation,
      canShowExploration: company.visible && hasPublishedExploration,
      canShowExplanations: company.visible && hasExplanations,
      fullyComplete: company.visible && hasPublishedExploration && hasValuation && hasExplanations,
    },
  }

  const runExploration = await prisma.companyExploration.findFirst({
    where: { companyId: company.id, runId: input.runId },
  })
  const runValuation = await prisma.companyValuationSnapshot.findFirst({
    where: { companyId: company.id, runId: input.runId },
  })
  const runExplanations = await prisma.companyValuationExplanation.findMany({
    where: { companyId: company.id, runId: input.runId },
  })

  result.runData = {
    runId: input.runId,
    hasExploration: Boolean(runExploration),
    hasValuation: Boolean(runValuation),
    explanationsCount: runExplanations.length,
    explorationId: runExploration?.id || null,
    valuationId: runValuation?.id || null,
  }

  return result
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (!options) return

  const payload = await readPayload(options.filePath)
  validatePayload(payload)

  if (options.dryRun) {
    console.log(JSON.stringify({
      success: true,
      mode: 'dry-run',
      message: 'payload 校验通过，未写入数据库',
      runId: payload.runId,
      company: payload.company,
    }, null, 2))
    return
  }

  const writeResult = await writeMarketAnalysisCrossMarket(payload)
  const verifyResult = options.verify ? await verifyWrite(payload) : null

  console.log(JSON.stringify({
    success: true,
    mode: 'write',
    message: '市场分析数据写入成功',
    runId: payload.runId,
    data: {
      company: {
        id: writeResult.company.id,
        symbol: writeResult.company.symbol,
        market: writeResult.company.market,
        name: writeResult.company.name,
      },
      pageEntry: writeResult.pageEntry
        ? {
            id: writeResult.pageEntry.id,
            entryType: writeResult.pageEntry.entryType,
          }
        : null,
      exploration: writeResult.exploration
        ? {
            id: writeResult.exploration.id,
            title: writeResult.exploration.title,
          }
        : null,
      valuation: writeResult.valuation
        ? {
            id: writeResult.valuation.id,
            asOfDate: writeResult.valuation.asOfDate,
          }
        : null,
      explanationsCount: writeResult.explanations.length,
      syncedCompanies: writeResult.syncedCompanies || [],
    },
    verify: verifyResult,
  }, null, 2))
}

main()
  .then(async () => {
    await prisma.$disconnect()
    process.exit(SUCCESS_EXIT_CODE)
  })
  .catch(async (error) => {
    console.error(JSON.stringify({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }, null, 2))
    await prisma.$disconnect()
    process.exit(FAILURE_EXIT_CODE)
  })
