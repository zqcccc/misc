import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()
const sqlitePath = process.env.SQLITE_DATABASE_PATH || 'prisma/dev.db'

type AnyRow = Record<string, unknown>

function readSqliteRows<T extends AnyRow>(table: string): T[] {
  if (!existsSync(sqlitePath)) {
    throw new Error(`SQLite database not found: ${sqlitePath}`)
  }

  const output = execFileSync(
    'sqlite3',
    ['-json', sqlitePath, `SELECT * FROM "${table}";`],
    {
      encoding: 'utf8',
      maxBuffer: 256 * 1024 * 1024,
    },
  )

  return output.trim() ? (JSON.parse(output) as T[]) : []
}

function dateValue(value: unknown) {
  if (value instanceof Date) return value
  if (typeof value === 'number') return new Date(value)
  if (typeof value === 'string' && value.trim()) {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? new Date(numeric) : new Date(value)
  }
  return new Date()
}

function nullableString(value: unknown) {
  return typeof value === 'string' ? value : null
}

function requiredString(value: unknown) {
  return typeof value === 'string' ? value : String(value ?? '')
}

function nullableNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function nullableBoolean(value: unknown) {
  if (value === null || value === undefined) return null
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  if (typeof value === 'string') return value === 'true' || value === '1'
  return null
}

async function migrateShare() {
  const rows = readSqliteRows<AnyRow>('Share')
  if (rows.length === 0) return 0

  await prisma.share.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      name: nullableString(row.name),
      date: requiredString(row.date),
      price: requiredString(row.price),
      pe: requiredString(row.pe),
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateShareInfo() {
  const rows = readSqliteRows<AnyRow>('ShareInfo')
  if (rows.length === 0) return 0

  await prisma.shareInfo.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      name: requiredString(row.name),
      stock_abbr: requiredString(row.stock_abbr),
      stock_number: requiredString(row.stock_number),
      stock_pinyin: requiredString(row.stock_pinyin),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateLowCodeConfig() {
  const rows = readSqliteRows<AnyRow>('LowCodeConfig')
  if (rows.length === 0) return 0

  await prisma.lowCodeConfig.createMany({
    data: rows.map((row) => ({
      id: Number(row.id),
      name: requiredString(row.name || 'website'),
      json: requiredString(row.json),
    })),
    skipDuplicates: true,
  })
  await prisma.$executeRawUnsafe(
    'SELECT setval(pg_get_serial_sequence(\'"LowCodeConfig"\', \'id\'), COALESCE((SELECT MAX(id) FROM "LowCodeConfig"), 1), true);',
  )

  return rows.length
}

async function migrateCompanies() {
  const rows = readSqliteRows<AnyRow>('Company')
  if (rows.length === 0) return 0

  await prisma.company.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      symbol: requiredString(row.symbol),
      market: requiredString(row.market),
      exchange: nullableString(row.exchange),
      name: requiredString(row.name),
      currency: nullableString(row.currency),
      sector: nullableString(row.sector),
      industry: nullableString(row.industry),
      country: nullableString(row.country),
      website: nullableString(row.website),
      status: requiredString(row.status || 'active'),
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateExplorationRuns() {
  const rows = readSqliteRows<AnyRow>('CompanyExplorationRun')
  if (rows.length === 0) return 0

  await prisma.companyExplorationRun.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      name: nullableString(row.name),
      marketScope: nullableString(row.marketScope),
      prompt: requiredString(row.prompt),
      model: nullableString(row.model),
      status: requiredString(row.status),
      startedAt: dateValue(row.startedAt),
      finishedAt: row.finishedAt ? dateValue(row.finishedAt) : null,
      error: nullableString(row.error),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateValuationSnapshots() {
  const rows = readSqliteRows<AnyRow>('CompanyValuationSnapshot')
  if (rows.length === 0) return 0

  await prisma.companyValuationSnapshot.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      companyId: requiredString(row.companyId),
      asOfDate: dateValue(row.asOfDate),
      price: nullableNumber(row.price),
      marketCap: nullableNumber(row.marketCap),
      ttmEps: nullableNumber(row.ttmEps),
      normalizedTtmEps: nullableNumber(row.normalizedTtmEps),
      ttmPe: nullableNumber(row.ttmPe),
      normalizedTtmPe: nullableNumber(row.normalizedTtmPe),
      revenueTtm: nullableNumber(row.revenueTtm),
      profitTtm: nullableNumber(row.profitTtm),
      normalizedProfitTtm: nullableNumber(row.normalizedProfitTtm),
      profitMultiple: nullableNumber(row.profitMultiple),
      referenceMultiple: nullableNumber(row.referenceMultiple),
      profitLinePrice: nullableNumber(row.profitLinePrice),
      referenceLinePrice: nullableNumber(row.referenceLinePrice),
      upsideToProfitLine: nullableNumber(row.upsideToProfitLine),
      upsideToReferenceLine: nullableNumber(row.upsideToReferenceLine),
      nonRecurringProfit: nullableNumber(row.nonRecurringProfit),
      profitQualityScore: nullableNumber(row.profitQualityScore),
      profitQualitySummary: nullableString(row.profitQualitySummary),
      source: nullableString(row.source),
      rawJson: nullableString(row.rawJson),
      createdAt: dateValue(row.createdAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateExplorations() {
  const rows = readSqliteRows<AnyRow>('CompanyExploration')
  if (rows.length === 0) return 0

  await prisma.companyExploration.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      companyId: requiredString(row.companyId),
      runId: nullableString(row.runId),
      title: requiredString(row.title),
      summary: requiredString(row.summary),
      thesis: nullableString(row.thesis),
      catalysts: nullableString(row.catalysts),
      risks: nullableString(row.risks),
      tags: nullableString(row.tags),
      score: nullableNumber(row.score),
      confidence: nullableNumber(row.confidence),
      sourceUrls: nullableString(row.sourceUrls),
      rawJson: nullableString(row.rawJson),
      visibility: requiredString(row.visibility || 'draft'),
      pinned: nullableBoolean(row.pinned) || false,
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migrateValuationExplanations() {
  const rows = readSqliteRows<AnyRow>('CompanyValuationExplanation')
  if (rows.length === 0) return 0

  await prisma.companyValuationExplanation.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      companyId: requiredString(row.companyId),
      valuationSnapshotId: nullableString(row.valuationSnapshotId),
      explanationType: requiredString(row.explanationType),
      title: requiredString(row.title),
      body: requiredString(row.body),
      impactDirection: nullableString(row.impactDirection),
      impactAmount: nullableNumber(row.impactAmount),
      isRecurring: nullableBoolean(row.isRecurring),
      sourceUrls: nullableString(row.sourceUrls),
      confidence: nullableNumber(row.confidence),
      authorType: requiredString(row.authorType || 'ai'),
      asOfDate: dateValue(row.asOfDate),
      isCurrent: nullableBoolean(row.isCurrent) ?? true,
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function migratePageEntries() {
  const rows = readSqliteRows<AnyRow>('CompanyPageEntry')
  if (rows.length === 0) return 0

  await prisma.companyPageEntry.createMany({
    data: rows.map((row) => ({
      id: requiredString(row.id),
      companyId: requiredString(row.companyId),
      entryType: requiredString(row.entryType),
      title: nullableString(row.title),
      note: nullableString(row.note),
      sortOrder: nullableNumber(row.sortOrder) || 0,
      visible: nullableBoolean(row.visible) ?? true,
      createdAt: dateValue(row.createdAt),
      updatedAt: dateValue(row.updatedAt),
    })),
    skipDuplicates: true,
  })

  return rows.length
}

async function main() {
  const results = {
    Share: await migrateShare(),
    ShareInfo: await migrateShareInfo(),
    LowCodeConfig: await migrateLowCodeConfig(),
    Company: await migrateCompanies(),
    CompanyExplorationRun: await migrateExplorationRuns(),
    CompanyValuationSnapshot: await migrateValuationSnapshots(),
    CompanyExploration: await migrateExplorations(),
    CompanyValuationExplanation: await migrateValuationExplanations(),
    CompanyPageEntry: await migratePageEntries(),
  }

  console.table(results)
}

main()
  .finally(async () => {
    await prisma.$disconnect()
  })
  .catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
