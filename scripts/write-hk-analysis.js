const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const fs = require('fs');

async function writeAnalysis(filePath) {
  const payload = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  console.log('Processing:', payload.company.name);
  
  let company = await prisma.company.findUnique({
    where: { market_symbol: { market: payload.company.market, symbol: payload.company.symbol } }
  });
  
  if (!company) {
    company = await prisma.company.create({
      data: {
        symbol: payload.company.symbol, market: payload.company.market, exchange: payload.company.exchange,
        name: payload.company.name, currency: payload.company.currency, sector: payload.company.sector,
        industry: payload.company.industry, country: payload.company.country, website: payload.company.website,
        status: 'active', entryType: payload.pageEntry?.entryType || 'ai-generated',
        entryNote: payload.pageEntry?.note, visible: true,
      }
    });
    console.log('Created company:', company.id);
  } else {
    company = await prisma.company.update({
      where: { id: company.id },
      data: { name: payload.company.name, sector: payload.company.sector, industry: payload.company.industry, country: payload.company.country, website: payload.company.website }
    });
    console.log('Updated company:', company.id);
  }
  
  const run = await prisma.companyExplorationRun.create({
    data: {
      name: payload.runId,
      marketScope: payload.company.market,
      prompt: '港股高分红小公司系列分析 - ' + payload.company.name,
      model: 'ai-analysis',
      status: 'completed',
      startedAt: new Date(),
      finishedAt: new Date(),
    }
  });
  console.log('Created run:', run.id);
  
  if (payload.exploration) {
    const exploration = await prisma.companyExploration.create({
      data: {
        companyId: company.id, runId: run.id, title: payload.exploration.title,
        summary: payload.exploration.summary, thesis: payload.exploration.thesis,
        catalysts: payload.exploration.catalysts ? (typeof payload.exploration.catalysts === 'string' ? payload.exploration.catalysts : JSON.stringify(payload.exploration.catalysts)) : null,
        risks: payload.exploration.risks ? (typeof payload.exploration.risks === 'string' ? payload.exploration.risks : JSON.stringify(payload.exploration.risks)) : null,
        tags: payload.exploration.tags ? (typeof payload.exploration.tags === 'string' ? payload.exploration.tags : JSON.stringify(payload.exploration.tags)) : null,
        score: payload.exploration.score, confidence: typeof payload.exploration.confidence === 'string' ? { low: 30, medium: 60, high: 85 }[payload.exploration.confidence] || 60 : payload.exploration.confidence,
        visibility: typeof payload.exploration.visibility === 'number' ? 'published' : (payload.exploration.visibility || 'published'),
      }
    });
    console.log('Created exploration:', exploration.id);
  }
  
  if (payload.valuation) {
    const valuation = await prisma.companyValuationSnapshot.create({
      data: {
        companyId: company.id, runId: run.id, asOfDate: new Date(payload.valuation.asOfDate),
        price: payload.valuation.price, marketCap: payload.valuation.marketCap,
        ttmEps: payload.valuation.EPS || payload.valuation.ttmEps,
        normalizedTtmEps: payload.valuation.normalizedTtmEps,
        ttmPe: payload.valuation.PE || payload.valuation.ttmPe,
        normalizedTtmPe: payload.valuation.normalizedTtmPe,
        revenueTtm: payload.valuation.revenueTtm, profitTtm: payload.valuation.profitTtm,
        normalizedProfitTtm: payload.valuation.normalizedProfitTtm,
        profitMultiple: payload.valuation.profitMultiple ? Math.round(payload.valuation.profitMultiple) : null,
        referenceMultiple: payload.valuation.referenceMultiple ? Math.round(payload.valuation.referenceMultiple) : null,
        profitLinePrice: payload.valuation.profitLinePrice, referenceLinePrice: payload.valuation.referenceLinePrice,
        upsideToProfitLine: payload.valuation.upside || payload.valuation.upsideToProfitLine,
        upsideToReferenceLine: payload.valuation.upsideToReferenceLine,
        profitQualityScore: payload.valuation.profitQualityScore, profitQualitySummary: payload.valuation.profitQualitySummary,
      }
    });
    console.log('Created valuation:', valuation.id);
    
    if (payload.explanations) {
      for (const exp of payload.explanations) {
        await prisma.companyValuationExplanation.create({
          data: {
            companyId: company.id, runId: run.id, valuationSnapshotId: valuation.id,
            explanationType: exp.explanationType || 'valuation_factor',
            title: exp.title, body: exp.body || exp.content,
            impactDirection: exp.impactDirection, isRecurring: exp.isRecurring, confidence: typeof exp.confidence === 'string' ? { low: 30, medium: 60, high: 85 }[exp.confidence] || 60 : exp.confidence,
            authorType: 'ai',
          }
        });
      }
      console.log('Created', payload.explanations.length, 'explanations');
    }
  }
  
  console.log('SUCCESS:', payload.company.name);
}

const file = process.argv[2];
writeAnalysis(file)
  .then(() => prisma.$disconnect())
  .catch(e => { console.error('ERROR:', e.message); prisma.$disconnect(); process.exit(1); });
