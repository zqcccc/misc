-- Add runId columns and indexes for idempotent writes

-- CompanyValuationSnapshot: add runId column and index
ALTER TABLE "CompanyValuationSnapshot" ADD COLUMN IF NOT EXISTS "runId" TEXT;
CREATE INDEX IF NOT EXISTS "CompanyValuationSnapshot_companyId_runId_idx" ON "CompanyValuationSnapshot"("companyId", "runId");

-- CompanyValuationExplanation: add runId column and index
ALTER TABLE "CompanyValuationExplanation" ADD COLUMN IF NOT EXISTS "runId" TEXT;
CREATE INDEX IF NOT EXISTS "CompanyValuationExplanation_companyId_runId_idx" ON "CompanyValuationExplanation"("companyId", "runId");

-- CompanyExploration: add index for companyId + runId (runId already exists)
CREATE INDEX IF NOT EXISTS "CompanyExploration_companyId_runId_idx" ON "CompanyExploration"("companyId", "runId");
