import { PrismaClient } from '@prisma/client'
import { NextResponse } from 'next/server'
import { buildCompanyValuationCard } from './summary'

const prisma = new PrismaClient()

const companyInclude = {
  valuations: {
    orderBy: [{ asOfDate: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 1,
  },
  explorations: {
    where: { visibility: 'published' },
    orderBy: [{ pinned: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 1,
  },
  explanations: {
    where: { isCurrent: true },
    orderBy: [{ asOfDate: 'desc' as const }, { createdAt: 'desc' as const }],
    take: 8,
  },
}

export async function GET() {
  try {
    const entries = await prisma.companyPageEntry.findMany({
      where: { visible: true },
      orderBy: [{ sortOrder: 'asc' }, { createdAt: 'desc' }],
      take: 500,
      include: {
        company: {
          include: companyInclude,
        },
      },
    })

    const cards = entries.map((entry) =>
      buildCompanyValuationCard({
        company: entry.company,
        entry,
        latestValuation: entry.company.valuations[0] || null,
        latestExploration: entry.company.explorations[0] || null,
        explanations: entry.company.explanations,
      }),
    )

    return NextResponse.json({ entries: cards })
  } catch (error) {
    console.error('[company-valuation] load failed:', error)
    return NextResponse.json(
      { message: '公司估值数据获取失败' },
      { status: 500 },
    )
  }
}
