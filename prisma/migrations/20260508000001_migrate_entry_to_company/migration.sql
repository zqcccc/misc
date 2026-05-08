-- Migration: 将 CompanyPageEntry 字段迁移到 Company 表
-- 目的：让 PE 页面直接展示 Company 数据，而不是依赖 CompanyPageEntry

-- 1. 添加新字段到 Company 表
ALTER TABLE "Company" ADD COLUMN IF NOT EXISTS "entryType" TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE "Company" ADD COLUMN IF NOT EXISTS "entryNote" TEXT;
ALTER TABLE "Company" ADD COLUMN IF NOT EXISTS "sortOrder" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "Company" ADD COLUMN IF NOT EXISTS "visible" BOOLEAN NOT NULL DEFAULT true;

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS "Company_visible_sortOrder_idx" ON "Company"("visible", "sortOrder");
CREATE INDEX IF NOT EXISTS "Company_entryType_idx" ON "Company"("entryType");

-- 3. 迁移历史数据：将 CompanyPageEntry 的数据合并到 Company 表
-- 对于每个有 entry 的公司，将 entry 数据更新到 Company 表
UPDATE "Company" c
SET
  "entryType" = e."entryType",
  "entryNote" = e."note",
  "sortOrder" = e."sortOrder",
  "visible" = e."visible"
FROM "CompanyPageEntry" e
WHERE c.id = e."companyId";

-- 4. 处理多个 entry 的情况：如果一个公司有多个 entry，保留 sortOrder 最大的那个
-- 先找到每个公司 sortOrder 最大的 entry
WITH max_entries AS (
  SELECT DISTINCT ON ("companyId")
    "companyId",
    "entryType",
    "note",
    "sortOrder",
    "visible"
  FROM "CompanyPageEntry"
  ORDER BY "companyId", "sortOrder" DESC
)
UPDATE "Company" c
SET
  "entryType" = m."entryType",
  "entryNote" = m."note",
  "sortOrder" = m."sortOrder",
  "visible" = m."visible"
FROM max_entries m
WHERE c.id = m."companyId";
