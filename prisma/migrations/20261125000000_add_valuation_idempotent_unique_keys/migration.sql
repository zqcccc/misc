-- 公司估值数据幂等唯一键 + CompanyValuationSummary 外键
--
-- 唯一键设计（幂等语义）：
--   CompanyExploration          (companyId, runId)                     同一 run 内每家公司最多一条研究结论
--   CompanyValuationSnapshot    (companyId, runId)                     同一 run 内每家公司最多一条估值快照
--   CompanyValuationExplanation (companyId, runId, explanationType)    同一 run 内每家公司每种解释类型最多一条
--
-- runId 可为 NULL（历史上无 run 的写入）。PostgreSQL 默认 NULL 互不冲突，
-- 因此约束只对带 runId 的新写入生效，无 runId 的旧数据行为不变。

-- 1. 清理孤儿数据（companyId 指向不存在的公司）。正常情况下前置外键已阻止，
--    此步骤仅防御外键缺失或绕过约束写入的残留。
DELETE FROM "CompanyExploration" ce
WHERE NOT EXISTS (SELECT 1 FROM "Company" c WHERE c."id" = ce."companyId");

DELETE FROM "CompanyValuationSnapshot" vs
WHERE NOT EXISTS (SELECT 1 FROM "Company" c WHERE c."id" = vs."companyId");

DELETE FROM "CompanyValuationExplanation" ex
WHERE NOT EXISTS (SELECT 1 FROM "Company" c WHERE c."id" = ex."companyId");

-- 2. 清理估值快照悬空引用（外键本应 SET NULL，防御性兜底）
UPDATE "CompanyValuationExplanation" ex
SET "valuationSnapshotId" = NULL
WHERE ex."valuationSnapshotId" IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM "CompanyValuationSnapshot" vs WHERE vs."id" = ex."valuationSnapshotId"
  );

-- 3. 按确定性规则清理重复：同一唯一键保留 createdAt 最新（并列时 id 最大）的一行。
--    runId 为 NULL 的行不参与去重（多个 NULL 合法）。
DELETE FROM "CompanyExploration" a
USING "CompanyExploration" b
WHERE a."runId" IS NOT NULL
  AND a."companyId" = b."companyId"
  AND a."runId" = b."runId"
  AND (a."createdAt" < b."createdAt" OR (a."createdAt" = b."createdAt" AND a."id" < b."id"));

DELETE FROM "CompanyValuationSnapshot" a
USING "CompanyValuationSnapshot" b
WHERE a."runId" IS NOT NULL
  AND a."companyId" = b."companyId"
  AND a."runId" = b."runId"
  AND (a."createdAt" < b."createdAt" OR (a."createdAt" = b."createdAt" AND a."id" < b."id"));

DELETE FROM "CompanyValuationExplanation" a
USING "CompanyValuationExplanation" b
WHERE a."runId" IS NOT NULL
  AND a."companyId" = b."companyId"
  AND a."runId" = b."runId"
  AND a."explanationType" = b."explanationType"
  AND (a."createdAt" < b."createdAt" OR (a."createdAt" = b."createdAt" AND a."id" < b."id"));

-- 4. 清理摘要孤儿（摘要表在 appuser schema，尚未有外键，孤儿真实可能存在；
--    摘要为派生数据，可由 rebuild 脚本重建，直接删除）
DELETE FROM appuser."CompanyValuationSummary" s
WHERE NOT EXISTS (SELECT 1 FROM "Company" c WHERE c."id" = s."companyId");

-- 5. 用唯一约束替换原 (companyId, runId) 普通索引（唯一索引同时承担该前缀查询）
DROP INDEX IF EXISTS "CompanyExploration_companyId_runId_idx";
DROP INDEX IF EXISTS "CompanyValuationSnapshot_companyId_runId_idx";
DROP INDEX IF EXISTS "CompanyValuationExplanation_companyId_runId_idx";

ALTER TABLE "CompanyExploration"
  ADD CONSTRAINT "CompanyExploration_companyId_runId_key" UNIQUE ("companyId", "runId");

ALTER TABLE "CompanyValuationSnapshot"
  ADD CONSTRAINT "CompanyValuationSnapshot_companyId_runId_key" UNIQUE ("companyId", "runId");

ALTER TABLE "CompanyValuationExplanation"
  ADD CONSTRAINT "CompanyValuationExplanation_companyId_runId_explanationType_key"
  UNIQUE ("companyId", "runId", "explanationType");

-- 6. CompanyValuationSummary → Company 外键（与 schema 中 onDelete: Cascade 对应）
ALTER TABLE appuser."CompanyValuationSummary"
  ADD CONSTRAINT "CompanyValuationSummary_companyId_fkey"
  FOREIGN KEY ("companyId") REFERENCES "public"."Company"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
