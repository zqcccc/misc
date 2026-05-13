#!/usr/bin/env node
/**
 * batch-import-analyses.ts
 * 批量将 tmp/*.json 分析文件导入数据库（高性能版本）
 * 用法: node scripts/batch-import-analyses.ts [--dry-run] [--continue]
 */

import { readdir, readFile } from 'fs/promises'
import { join } from 'path'
import { PrismaClient } from '@prisma/client'
import { writeMarketAnalysisCrossMarket, type CrossMarketWriteInput } from '../lib/market-analysis'
import { recordMarketAnalysisScratchpad } from '../lib/market-analysis-scratchpad'

const prisma = new PrismaClient()
const TMP_DIR = join(process.cwd(), 'tmp')
const DRY_RUN = process.argv.includes('--dry-run')
const CONTINUE = process.argv.includes('--continue')
const BATCH_SIZE = 20

function getNumberArg(name: string) {
  const prefix = `--${name}=`
  const arg = process.argv.find(value => value.startsWith(prefix))
  if (!arg) return null

  const value = Number.parseInt(arg.slice(prefix.length), 10)
  return Number.isFinite(value) ? value : null
}

const FROM_INDEX = getNumberArg('from') ?? 0
const LIMIT_COUNT = getNumberArg('limit')

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function main() {
  console.log(`批量导入分析数据`)
  console.log(`模式: ${DRY_RUN ? 'DRY-RUN（不实际写入）' : '正式导入'}`)
  if (CONTINUE) console.log('断点续传模式: 跳过已存在的公司')
  console.log('---')

  // 获取当前数据库中已导入的公司
  let existingCompanies = new Map<string, string>()
  if (CONTINUE) {
    const companies = await prisma.company.findMany({
      select: { id: true, market: true, symbol: true }
    })
    companies.forEach(c => {
      existingCompanies.set(`${c.market}:${c.symbol}`, c.id)
    })
    console.log(`已有 ${existingCompanies.size} 家公司，将跳过`)
  }

  // 获取所有 analysis.json 文件
  const files = await readdir(TMP_DIR)
  let analysisFiles = files
    .filter(f => f.endsWith('-analysis.json') || f.endsWith('-deep-analysis.json'))
    .sort()
    .map(f => join(TMP_DIR, f))

  if (FROM_INDEX > 0 || LIMIT_COUNT !== null) {
    const toIndex = LIMIT_COUNT === null ? undefined : FROM_INDEX + LIMIT_COUNT
    analysisFiles = analysisFiles.slice(FROM_INDEX, toIndex)
    console.log(`文件区间: from=${FROM_INDEX}, limit=${LIMIT_COUNT ?? 'all'}`)
  }

  // 断点续传模式：跳过已存在的公司
  if (CONTINUE) {
    const originalCount = analysisFiles.length
    analysisFiles = analysisFiles.filter(filePath => {
      const fileName = filePath.split('/').pop() || ''
      let market = '', symbol = ''
      if (fileName.includes('-hk-')) {
        market = 'hk'
        symbol = fileName.replace('-hk-analysis.json', '').replace('-hk-deep-analysis.json', '').toUpperCase() + '.HK'
      } else if (/^\d{6}/.test(fileName)) {
        market = 'a'
        symbol = fileName.replace('-analysis.json', '').replace('-deep-analysis.json', '')
      } else {
        market = 'us'
        symbol = fileName.replace('-analysis.json', '').replace('-deep-analysis.json', '').toUpperCase()
      }
      return !existingCompanies.has(`${market}:${symbol}`)
    })
    console.log(`过滤后剩余 ${analysisFiles.length}/${originalCount} 个文件待导入`)
  }

  console.log(`找到 ${analysisFiles.length} 个待导入文件`)
  console.log('')

  if (analysisFiles.length === 0) {
    console.log('没有需要导入的文件')
    return
  }

  let success = 0
  let failed = 0
  let skipped = 0
  const errors: Array<{ file: string; error: string }> = []

  // 预加载所有公司到内存
  const allCompanies = await prisma.company.findMany({
    select: { id: true, market: true, symbol: true }
  })
  const companyMap = new Map(allCompanies.map(c => [`${c.market}:${c.symbol}`, c.id]))

  for (let i = 0; i < analysisFiles.length; i++) {
    const filePath = analysisFiles[i]
    const fileName = filePath.split('/').pop()
    const progress = `[${i + 1}/${analysisFiles.length}]`

    try {
      const content = await readFile(filePath, 'utf8')
      const payload = JSON.parse(content) as CrossMarketWriteInput

      if (!payload.company?.symbol || !payload.company?.market) {
        console.log(`${progress} ${fileName}... ✗ 缺少必要字段`)
        failed++
        continue
      }

      await recordMarketAnalysisScratchpad(payload.runId, 'validation', {
        success: true,
        mode: DRY_RUN ? 'batch-dry-run' : 'batch-write',
        filePath,
      })

      const key = `${payload.company.market}:${payload.company.symbol}`
      let companyId = companyMap.get(key)

      // 公司不存在则创建
      if (!companyId) {
        if (DRY_RUN) {
          console.log(`${progress} ${fileName}... [DRY-RUN] 创建公司: ${key}`)
          success++
        } else {
          const newCompany = await prisma.company.create({
            data: {
              symbol: payload.company.symbol,
              market: payload.company.market,
              name: payload.company.name || payload.company.symbol,
              exchange: payload.company.exchange || null,
              currency: payload.company.currency || null,
              sector: payload.company.sector || null,
              industry: payload.company.industry || null,
              country: payload.company.country || null,
              status: 'active',
            },
          })
          companyId = newCompany.id
          companyMap.set(key, companyId)
          console.log(`${progress} ${fileName}... ✓ 创建公司: ${key}`)
        }
      } else {
        if (DRY_RUN) {
          console.log(`${progress} ${fileName}... [DRY-RUN] 跳过（已存在）`)
          skipped++
          continue
        }
      }

      if (!DRY_RUN && companyId) {
        await writeMarketAnalysisCrossMarket(payload)
        console.log(`${progress} ${fileName}... ✓`)
      }

      success++

      // 批量暂停，防止数据库过载
      if (!DRY_RUN && i > 0 && i % BATCH_SIZE === 0) {
        await sleep(100)
      }

    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      console.log(`${progress} ${fileName}... ✗ ${msg}`)
      failed++
      errors.push({ file: fileName || filePath, error: msg })
    }

    // 每100个输出进度
    if (!DRY_RUN && i % 100 === 0 && i > 0) {
      console.log(`\n进度: ${success + failed}/${analysisFiles.length}`)
      await sleep(200)
    }
  }

  console.log('')
  console.log('=== 导入结果 ===')
  console.log(`成功: ${success}`)
  console.log(`跳过: ${skipped}`)
  console.log(`失败: ${failed}`)

  if (errors.length > 0) {
    console.log('')
    console.log('失败详情:')
    errors.slice(0, 20).forEach(e => {
      console.log(`  ${e.file}: ${e.error}`)
    })
    if (errors.length > 20) {
      console.log(`  ... 还有 ${errors.length - 20} 个错误`)
    }
  }
}

main()
  .finally(async () => {
    await prisma.$disconnect()
  })
  .catch(error => {
    console.error('脚本执行失败:', error)
    process.exit(1)
  })
