-- Add cross-market grouping field to Company
ALTER TABLE "Company" ADD COLUMN IF NOT EXISTS "groupId" TEXT;

CREATE INDEX IF NOT EXISTS "Company_groupId_idx" ON "Company"("groupId");
