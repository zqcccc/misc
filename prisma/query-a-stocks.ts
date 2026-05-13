import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  const companies = await prisma.company.findMany({
    where: { market: 'a' },
    select: {
      symbol: true,
      name: true,
      sector: true,
      industry: true,
      visible: true,
      entryType: true,
      explorations: {
        where: { visibility: 'published' },
        select: { id: true, score: true },
        take: 1,
      },
      valuations: {
        orderBy: { asOfDate: 'desc' },
        select: { ttmPe: true, price: true, marketCap: true },
        take: 1,
      },
    },
    orderBy: { symbol: 'asc' },
  })

  console.log(`\n=== A股已入库公司总数: ${companies.length} ===\n`)
  
  for (const c of companies) {
    const hasExploration = c.explorations.length > 0
    const hasValuation = c.valuations.length > 0
    const pe = c.valuations[0]?.ttmPe || 'N/A'
    const price = c.valuations[0]?.price || 'N/A'
    const score = c.explorations[0]?.score || 'N/A'
    console.log(`${c.symbol} | ${c.name} | ${c.sector || '-'} | PE:${pe} | 价:${price} | 分:${score} | 探索:${hasExploration ? '✓' : '✗'} | 估值:${hasValuation ? '✓' : '✗'} | 可见:${c.visible}`)
  }

  await prisma.$disconnect()
}

main()
