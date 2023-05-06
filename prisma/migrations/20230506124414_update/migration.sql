/*
  Warnings:

  - Added the required column `updatedAt` to the `Share` table without a default value. This is not possible if the table is not empty.

*/
-- CreateTable
CREATE TABLE "ShareInfo" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "stock_abbr" TEXT NOT NULL,
    "stock_number" TEXT NOT NULL,
    "stock_pinyin" TEXT NOT NULL
);

-- RedefineTables
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Share" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT,
    "date" TEXT NOT NULL,
    "price" TEXT NOT NULL,
    "pe" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_Share" ("date", "id", "name", "pe", "price") SELECT "date", "id", "name", "pe", "price" FROM "Share";
DROP TABLE "Share";
ALTER TABLE "new_Share" RENAME TO "Share";
PRAGMA foreign_key_check;
PRAGMA foreign_keys=ON;
