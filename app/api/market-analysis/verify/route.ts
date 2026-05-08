import { NextRequest, NextResponse } from 'next/server'
import { PrismaClient } from '@prisma/client'
import { buildCompanyValuationCard } from '@/app/api/company-valuation/summary'

const prisma = new PrismaClient()

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const symbol = searchParams.get('symbol')
  const market = searchParams.get('market')
  const runId = searchParams.get('runId')
  const includeRelated = searchParams.get('includeRelated') === 'true'

  if (!symbol || !market) {
    return NextResponse.json(
      {
        success: false,
        error: '缺少必需参数: symbol, market',
      },
      { status: 400 },
    )
  }

  try {
    const company = await prisma.company.findUnique({
      where: {
        market_symbol: {
          market,
          symbol,
        },
      },
      include: {
        valuations: {
          orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
          take: 1,
        },
        explorations: {
          where: { visibility: 'published' },
          orderBy: [{ pinned: 'desc' }, { createdAt: 'desc' }],
          take: 1,
        },
        explanations: {
          where: { isCurrent: true },
          orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
          take: 8,
        },
      },
    })

    if (!company) {
      return NextResponse.json(
        {
          success: false,
          error: `未找到公司 ${market}:${symbol}，请先写入数据`,
          pePageVisible: false,
        },
        { status: 404 },
      )
    }

    const isVisible = company.visible
    const hasPublishedExploration = company.explorations.length > 0
    const hasValuation = company.valuations.length > 0
    const hasExplanations = company.explanations.length > 0

    const card = buildCompanyValuationCard({
      company,
      latestValuation: company.valuations[0] || null,
      latestExploration: company.explorations[0] || null,
      explanations: company.explanations,
    })

    const result: any = {
      success: true,
      pePageVisible: isVisible,
      company: {
        id: company.id,
        symbol: company.symbol,
        market: company.market,
        name: company.name,
        groupId: company.groupId,
      },
      dataStatus: {
        isVisible,
        hasPublishedExploration,
        hasValuation,
        hasExplanations,
        explorationsCount: company.explorations.length,
        valuationsCount: company.valuations.length,
        explanationsCount: company.explanations.length,
      },
      pePagePreview: {
        title: card.title,
        entryType: card.entryType,
        metrics: card.metrics,
        exploration: card.exploration,
        tags: card.tags,
        profitQuality: card.profitQuality,
        primaryExplanation: card.primaryExplanation,
      },
      checkList: {
        canShowInSidebar: isVisible,
        canShowValuationCard: isVisible && hasValuation,
        canShowExploration: isVisible && hasPublishedExploration,
        canShowExplanations: isVisible && hasExplanations,
        fullyComplete:
          isVisible &&
          hasPublishedExploration &&
          hasValuation &&
          hasExplanations,
      },
    }

    if (runId) {
      const runExploration = await prisma.companyExploration.findFirst({
        where: { companyId: company.id, runId },
      })
      const runValuation = await prisma.companyValuationSnapshot.findFirst({
        where: { companyId: company.id, runId },
      })
      const runExplanations = await prisma.companyValuationExplanation.findMany({
        where: { companyId: company.id, runId },
      })

      result.runData = {
        runId,
        hasExploration: !!runExploration,
        hasValuation: !!runValuation,
        explanationsCount: runExplanations.length,
        explorationId: runExploration?.id || null,
        valuationId: runValuation?.id || null,
      }
    }

    // 查询关联公司（跨市场）
    if (includeRelated && company.groupId) {
      const relatedCompanies = await prisma.company.findMany({
        where: {
          groupId: company.groupId,
          id: { not: company.id },
        },
        include: {
          valuations: {
            orderBy: [{ asOfDate: 'desc' }, { createdAt: 'desc' }],
            take: 1,
          },
          explorations: {
            where: { visibility: 'published' },
            orderBy: [{ pinned: 'desc' }, { createdAt: 'desc' }],
            take: 1,
          },
        },
      })

      result.relatedCompanies = relatedCompanies.map(related => {
        const relatedCard = buildCompanyValuationCard({
          company: related,
          latestValuation: related.valuations[0] || null,
          latestExploration: related.explorations[0] || null,
          explanations: [],
        })

        return {
          symbol: related.symbol,
          market: related.market,
          name: related.name,
          pePageVisible: related.visible,
          hasExploration: related.explorations.length > 0,
          hasValuation: related.valuations.length > 0,
          pePagePreview: {
            title: relatedCard.title,
            entryType: relatedCard.entryType,
            metrics: relatedCard.metrics,
            exploration: relatedCard.exploration,
          },
        }
      })

      result.crossMarketStatus = {
        groupId: company.groupId,
        totalMarkets: relatedCompanies.length + 1,
        visibleMarkets: [
          ...(isVisible ? [{ market: company.market, symbol: company.symbol }] : []),
          ...relatedCompanies
            .filter(c => c.visible)
            .map(c => ({ market: c.market, symbol: c.symbol })),
        ],
      }
    }

    return NextResponse.json(result)
  } catch (error) {
    console.error('[market-analysis/verify] error:', error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : '查询失败',
      },
      { status: 500 },
    )
  }
}
