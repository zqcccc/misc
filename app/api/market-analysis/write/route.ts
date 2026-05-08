import { NextRequest, NextResponse } from 'next/server'
import { writeMarketAnalysisCrossMarket, CrossMarketWriteInput } from '@/lib/market-analysis'

export async function POST(request: NextRequest) {
  try {
    const body: CrossMarketWriteInput = await request.json()

    if (!body.company?.symbol || !body.company?.market || !body.company?.name) {
      return NextResponse.json(
        {
          success: false,
          error: '缺少必需字段: company.symbol, company.market, company.name',
        },
        { status: 400 },
      )
    }

    if (!body.runId) {
      return NextResponse.json(
        {
          success: false,
          error: '缺少必需字段: runId。请提供一个唯一的分析任务 ID，用于幂等写入。',
        },
        { status: 400 },
      )
    }

    const result = await writeMarketAnalysisCrossMarket(body)

    return NextResponse.json({
      success: true,
      message: result.syncedCompanies && result.syncedCompanies.length > 0
        ? `市场分析数据写入成功，已同步到 ${result.syncedCompanies.length} 个关联市场`
        : '市场分析数据写入成功',
      runId: body.runId,
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
        syncedCompanies: result.syncedCompanies || [],
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
    message: '市场分析写入 API（跨市场幂等写入）',
    usage: {
      method: 'POST',
      description: '写入市场分析数据到数据库，支持跨市场同步',
      body: {
        runId: {
          required: true,
          description: '分析任务唯一标识。相同的 runId 重复写入会更新已有记录，不会创建重复数据',
          example: 'analysis-aapl-20260508-001',
        },
        company: {
          required: true,
          fields: {
            symbol: '股票代码 (如: AAPL, 600519)',
            market: '市场 (us, hk, a, cn)',
            name: '公司名称',
            groupId: '跨市场关联标识 (可选，如 "新华保险"。系统会自动根据公司名称识别)',
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
          description: '页面展示配置，用于 PE 页面展示',
          fields: {
            entryType: '入口类型 (manual, ai-generated, analysis, research)',
            note: '备注说明 (可选)',
            sortOrder: '排序顺序 (可选, 默认 0)',
            visible: '是否可见 (可选, 默认 true)',
          },
        },
        exploration: {
          required: false,
          description: '公司探索/研究报告（会自动同步到关联市场）',
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
          description: '估值快照数据（仅写入当前市场，不会同步）',
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
          description: '估值解释说明数组（仅写入当前市场，不会同步）',
          fields: {
            explanationType: '解释类型 (price, profit, valuation, business)',
            title: '说明标题',
            body: '说明内容',
            impactDirection: '影响方向 (positive, neutral, negative)',
            isRecurring: '是否经常性收入 (可选)',
            confidence: '置信度 (可选)',
          },
        },
        syncToMarkets: {
          required: false,
          description: '指定要同步的市场列表。如果不提供，系统会自动同步到所有关联市场',
          example: ['hk', 'a'],
        },
      },
      crossMarketExample: {
        description: '新华保险 A+H 股分析写入示例',
        request: {
          runId: 'analysis-xinhua-20260508-001',
          company: {
            symbol: '601336',
            market: 'a',
            name: '新华保险',
            groupId: '新华保险',
          },
          pageEntry: {
            entryType: 'ai-generated',
          },
          exploration: {
            title: '新华保险投资价值分析',
            summary: '新华保险是中国领先的寿险公司...',
            score: 78,
            tags: ['保险', '金融', 'A+H'],
            visibility: 'published',
          },
          valuation: {
            asOfDate: '2026-05-08',
            price: 45.2,
            ttmPe: 12.5,
          },
        },
        behavior: '系统会自动将 exploration 同步到港股市场 (01336.HK)',
      },
    },
  })
}
