// 港股分析写入：统一走 lib/market-analysis 的幂等写入管道
// （唯一键 upsert + 事务写入 + 摘要刷新 + 缓存失效 + run 状态），失败非零退出。
const fs = require('fs');
const path = require('path');

require('ts-node').register({
  project: path.join(__dirname, '..', 'tsconfig-debug.json'),
});

const {
  writeMarketAnalysisIdempotent,
  disconnectMarketAnalysisClient,
} = require('../lib/market-analysis');

const CONFIDENCE_BY_LABEL = { low: 30, medium: 60, high: 85 };

function normalizeConfidence(value) {
  if (typeof value === 'string') {
    return CONFIDENCE_BY_LABEL[value.toLowerCase()] || 60;
  }
  return value;
}

function stringifyIfNeeded(value) {
  if (value === undefined || value === null) return null;
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function normalizeTags(value) {
  if (value === undefined || value === null) return undefined;
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [String(value)];
}

function normalizeVisibility(value) {
  if (typeof value === 'number') return 'published';
  return value || 'published';
}

function buildPayload(raw) {
  if (!raw.company?.market || !raw.company?.symbol || !raw.company?.name) {
    throw new Error('payload.company.market/symbol/name 必填');
  }
  if (!raw.runId || typeof raw.runId !== 'string' || !raw.runId.trim()) {
    throw new Error('payload.runId 必填：幂等写入需要唯一的 run 标识');
  }

  const payload = {
    runId: raw.runId.trim(),
    company: raw.company,
  };

  if (raw.pageEntry) {
    payload.pageEntry = {
      entryType: raw.pageEntry.entryType || 'ai-generated',
      note: raw.pageEntry.note,
      visible: true,
    };
  }

  if (raw.exploration) {
    payload.exploration = {
      title: raw.exploration.title,
      summary: raw.exploration.summary,
      thesis: raw.exploration.thesis,
      catalysts: stringifyIfNeeded(raw.exploration.catalysts),
      risks: stringifyIfNeeded(raw.exploration.risks),
      tags: normalizeTags(raw.exploration.tags),
      score: raw.exploration.score,
      confidence: normalizeConfidence(raw.exploration.confidence),
      visibility: normalizeVisibility(raw.exploration.visibility),
    };
  }

  if (raw.valuation) {
    payload.valuation = {
      asOfDate: raw.valuation.asOfDate,
      price: raw.valuation.price,
      marketCap: raw.valuation.marketCap,
      ttmEps: raw.valuation.EPS ?? raw.valuation.ttmEps,
      normalizedTtmEps: raw.valuation.normalizedTtmEps,
      ttmPe: raw.valuation.PE ?? raw.valuation.ttmPe,
      normalizedTtmPe: raw.valuation.normalizedTtmPe,
      revenueTtm: raw.valuation.revenueTtm,
      profitTtm: raw.valuation.profitTtm,
      normalizedProfitTtm: raw.valuation.normalizedProfitTtm,
      profitMultiple: raw.valuation.profitMultiple ? Math.round(raw.valuation.profitMultiple) : undefined,
      referenceMultiple: raw.valuation.referenceMultiple ? Math.round(raw.valuation.referenceMultiple) : undefined,
      profitLinePrice: raw.valuation.profitLinePrice,
      referenceLinePrice: raw.valuation.referenceLinePrice,
      upsideToProfitLine: raw.valuation.upside ?? raw.valuation.upsideToProfitLine,
      upsideToReferenceLine: raw.valuation.upsideToReferenceLine,
      profitQualityScore: raw.valuation.profitQualityScore,
      profitQualitySummary: raw.valuation.profitQualitySummary,
    };

    if (raw.explanations) {
      payload.explanations = raw.explanations.map((exp) => ({
        explanationType: exp.explanationType || 'valuation_factor',
        title: exp.title,
        body: exp.body || exp.content,
        impactDirection: exp.impactDirection,
        isRecurring: exp.isRecurring,
        confidence: normalizeConfidence(exp.confidence),
      }));
    }
  }

  return payload;
}

async function writeAnalysis(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  console.log('Processing:', raw.company.name);

  const payload = buildPayload(raw);
  const result = await writeMarketAnalysisIdempotent(payload);

  console.log('Company:', result.company.id);
  if (result.exploration) console.log('Exploration:', result.exploration.id);
  if (result.valuation) console.log('Valuation:', result.valuation.id);
  console.log('Explanations:', result.explanations.length);
  console.log('SUCCESS:', payload.company.name);
}

const file = process.argv[2];
if (!file) {
  console.error('用法: node scripts/write-hk-analysis.js <payload.json>');
  process.exit(1);
}

writeAnalysis(file)
  .then(async () => {
    await disconnectMarketAnalysisClient();
  })
  .catch(async (e) => {
    console.error('ERROR:', e.message);
    await disconnectMarketAnalysisClient();
    process.exit(1);
  });
