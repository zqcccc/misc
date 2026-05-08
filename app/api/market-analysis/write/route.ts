import { NextRequest, NextResponse } from 'next/server'
import { writeMarketAnalysis, MarketAnalysisWriteInput } from '@/lib/market-analysis'

export async function POST(request: NextRequest) {
  try {
    const body: MarketAnalysisWriteInput = await request.json()

    if (!body.company?.symbol || !body.company?.market || !body.company?.name) {
      return NextResponse.json(
        {
          success: false,
          error: '缺少必需字段: company.symbol, company.market, company.name',
        },
        { status: 400 },
      )
    }

    const result = await writeMarketAnalysis(body)

    return NextResponse.json({
      success: true,
      message: '市场分析数据写入成功',
      data: {
        company: {
          id: result.company.id,
          symbol: result.company.symbol,
          market: result.company.market,
          name: result.company.name,
        },
        pageEntry: result.pageEntry
          ? {
              id: result.pageEntry.id,
              entryType: result.pageEntry.entryType,
            }
          : null,
        exploration: result.exploration
          ? {
              id: result.exploration.id,
              title: result.exploration.title,
            }
          : null,
        valuation: result.valuation
          ? {
              id: result.valuation.id,
              asOfDate: result.valuation.asOfDate,
            }
          : null,
        explanationsCount: result.explanations.length,
      },
    })
  } catch (error) {
    console.error('[market-analysis/write] error:', error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : '写入失败',
      },
      { status: 500 },
    )
  }
}

export async function GET() {
  return NextResponse.json({
    success: true,
    message: '市场分析写入 API',
    usage: {
      method: 'POST',
      description: '写入市场分析数据到数据库',
      body: {
        company: {
          required: true,
          fields: {
            symbol: '股票代码 (如: AAPL, 600519)',
            market: '市场 (us, hk, a, cn)',
            name: '公司名称',
            exchange: '交易所 (可选)',
            currency: '货币代码 (可选, 如: USD, CNY)',
            sector: '行业板块 (可选)',
            industry: '细分行业 (可选)',
            country: '国家 (可选)',
            website: '官网 (可选)',
          },
        },
        pageEntry: {
          required: false,
          description: '页面入口配置，用于 PE 页面展示',
          fields: {
            entryType: '入口类型 (manual, ai-generated, analysis, research)',
            title: '显示标题 (可选)',
            note: '备注说明 (可选)',
            sortOrder: '排序顺序 (可选, 默认 0)',
            visible: '是否可见 (可选, 默认 true)',
          },
        },
        exploration: {
          required: false,
          description: '公司探索/研究报告',
          fields: {
            title: '报告标题',
            summary: '摘要总结',
            thesis: '投资论点 (可选)',
            catalysts: '催化剂 (可选)',
            risks: '风险因素 (可选)',
            tags: '标签数组 (可选)',
            score: '评分 1-100 (可选)',
            confidence: '置信度 1-100 (可选)',
            sourceUrls: '来源链接数组 (可选)',
            visibility: '可见性 (可选, draft/published/archived)',
          },
        },
        valuation: {
          required: false,
          description: '估值快照数据',
          fields: {
            asOfDate: '数据日期 (ISO 格式或 YYYY-MM-DD)',
            price: '当前价格 (可选)',
            marketCap: '市值 (可选)',
            ttmEps: 'TTM 每股收益 (可选)',
            ttmPe: 'TTM 市盈率 (可选)',
            profitLinePrice: '利润线价格 (可选)',
            referenceLinePrice: '参考线价格 (可选)',
            upsideToProfitLine: '到利润线空间 (可选)',
            upsideToReferenceLine: '到参考线空间 (可选)',
            profitQualityScore: '利润质量评分 (可选)',
            profitQualitySummary: '利润质量说明 (可选)',
          },
        },
        explanations: {
          required: false,
          description: '估值解释说明数组',
          fields: {
            explanationType: '解释类型 (price, profit, valuation, business)',
            title: '说明标题',
            body: '说明内容',
            impactDirection: '影响方向 (positive, neutral, negative)',
            isRecurring: '是否经常性收入 (可选)',
            confidence: '置信度 (可选)',
          },
        },
      },
      example: {
        company: {
          symbol: 'AAPL',
          market: 'us',
          name: 'Apple Inc.',
          sector: 'Technology',
        },
        pageEntry: {
          entryType: 'ai-generated',
          title: 'Apple 分析',
        },
        exploration: {
          title: 'Apple 投资分析报告',
          summary: '苹果是一家值得长期持有的优质公司...',
          score: 85,
          tags: ['科技', '消费电子', '长期投资'],
        },
        valuation: {
          asOfDate: '2026-05-08',
          price: 185.5,
          ttmPe: 28.5,
          profitLinePrice: 200,
        },
        explanations: [
          {
            explanationType: 'profit',
            title: '服务收入增长强劲',
            body: '服务收入同比增长 15%，成为新的增长引擎',
            impactDirection: 'positive',
            isRecurring: true,
          },
        ],
      },
    },
  })
}
