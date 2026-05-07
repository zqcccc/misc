-- CreateTable
CREATE TABLE "Share" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "date" TEXT NOT NULL,
    "price" TEXT NOT NULL,
    "pe" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Share_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ShareInfo" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "stock_abbr" TEXT NOT NULL,
    "stock_number" TEXT NOT NULL,
    "stock_pinyin" TEXT NOT NULL,

    CONSTRAINT "ShareInfo_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LowCodeConfig" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL DEFAULT 'website',
    "json" TEXT NOT NULL,

    CONSTRAINT "LowCodeConfig_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Company" (
    "id" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "market" TEXT NOT NULL,
    "exchange" TEXT,
    "name" TEXT NOT NULL,
    "currency" TEXT,
    "sector" TEXT,
    "industry" TEXT,
    "country" TEXT,
    "website" TEXT,
    "status" TEXT NOT NULL DEFAULT 'active',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Company_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CompanyExplorationRun" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "marketScope" TEXT,
    "prompt" TEXT NOT NULL,
    "model" TEXT,
    "status" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "error" TEXT,

    CONSTRAINT "CompanyExplorationRun_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CompanyExploration" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "runId" TEXT,
    "title" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "thesis" TEXT,
    "catalysts" TEXT,
    "risks" TEXT,
    "tags" TEXT,
    "score" INTEGER,
    "confidence" INTEGER,
    "sourceUrls" TEXT,
    "rawJson" TEXT,
    "visibility" TEXT NOT NULL DEFAULT 'draft',
    "pinned" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CompanyExploration_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CompanyValuationSnapshot" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "asOfDate" TIMESTAMP(3) NOT NULL,
    "price" DOUBLE PRECISION,
    "marketCap" DOUBLE PRECISION,
    "ttmEps" DOUBLE PRECISION,
    "normalizedTtmEps" DOUBLE PRECISION,
    "ttmPe" DOUBLE PRECISION,
    "normalizedTtmPe" DOUBLE PRECISION,
    "revenueTtm" DOUBLE PRECISION,
    "profitTtm" DOUBLE PRECISION,
    "normalizedProfitTtm" DOUBLE PRECISION,
    "profitMultiple" INTEGER,
    "referenceMultiple" INTEGER,
    "profitLinePrice" DOUBLE PRECISION,
    "referenceLinePrice" DOUBLE PRECISION,
    "upsideToProfitLine" DOUBLE PRECISION,
    "upsideToReferenceLine" DOUBLE PRECISION,
    "nonRecurringProfit" DOUBLE PRECISION,
    "profitQualityScore" INTEGER,
    "profitQualitySummary" TEXT,
    "source" TEXT,
    "rawJson" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CompanyValuationSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CompanyValuationExplanation" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "valuationSnapshotId" TEXT,
    "explanationType" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "body" TEXT NOT NULL,
    "impactDirection" TEXT,
    "impactAmount" DOUBLE PRECISION,
    "isRecurring" BOOLEAN,
    "sourceUrls" TEXT,
    "confidence" INTEGER,
    "authorType" TEXT NOT NULL DEFAULT 'ai',
    "asOfDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "isCurrent" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CompanyValuationExplanation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CompanyPageEntry" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "entryType" TEXT NOT NULL,
    "title" TEXT,
    "note" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "visible" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CompanyPageEntry_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Company_market_idx" ON "Company"("market");

-- CreateIndex
CREATE INDEX "Company_sector_idx" ON "Company"("sector");

-- CreateIndex
CREATE UNIQUE INDEX "Company_market_symbol_key" ON "Company"("market", "symbol");

-- CreateIndex
CREATE INDEX "CompanyExplorationRun_status_startedAt_idx" ON "CompanyExplorationRun"("status", "startedAt");

-- CreateIndex
CREATE INDEX "CompanyExploration_companyId_createdAt_idx" ON "CompanyExploration"("companyId", "createdAt");

-- CreateIndex
CREATE INDEX "CompanyExploration_visibility_pinned_createdAt_idx" ON "CompanyExploration"("visibility", "pinned", "createdAt");

-- CreateIndex
CREATE INDEX "CompanyExploration_score_idx" ON "CompanyExploration"("score");

-- CreateIndex
CREATE INDEX "CompanyValuationSnapshot_companyId_asOfDate_idx" ON "CompanyValuationSnapshot"("companyId", "asOfDate");

-- CreateIndex
CREATE INDEX "CompanyValuationSnapshot_ttmPe_idx" ON "CompanyValuationSnapshot"("ttmPe");

-- CreateIndex
CREATE INDEX "CompanyValuationSnapshot_profitQualityScore_idx" ON "CompanyValuationSnapshot"("profitQualityScore");

-- CreateIndex
CREATE INDEX "CompanyValuationExplanation_companyId_explanationType_isCur_idx" ON "CompanyValuationExplanation"("companyId", "explanationType", "isCurrent");

-- CreateIndex
CREATE INDEX "CompanyValuationExplanation_valuationSnapshotId_idx" ON "CompanyValuationExplanation"("valuationSnapshotId");

-- CreateIndex
CREATE INDEX "CompanyPageEntry_visible_sortOrder_idx" ON "CompanyPageEntry"("visible", "sortOrder");

-- CreateIndex
CREATE INDEX "CompanyPageEntry_entryType_idx" ON "CompanyPageEntry"("entryType");

-- AddForeignKey
ALTER TABLE "CompanyExploration" ADD CONSTRAINT "CompanyExploration_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CompanyExploration" ADD CONSTRAINT "CompanyExploration_runId_fkey" FOREIGN KEY ("runId") REFERENCES "CompanyExplorationRun"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CompanyValuationSnapshot" ADD CONSTRAINT "CompanyValuationSnapshot_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CompanyValuationExplanation" ADD CONSTRAINT "CompanyValuationExplanation_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CompanyValuationExplanation" ADD CONSTRAINT "CompanyValuationExplanation_valuationSnapshotId_fkey" FOREIGN KEY ("valuationSnapshotId") REFERENCES "CompanyValuationSnapshot"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CompanyPageEntry" ADD CONSTRAINT "CompanyPageEntry_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "Company"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
