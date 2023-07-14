/*
  Warnings:

  - The primary key for the `LowCodeConfig` table will be changed. If it partially fails, the table could be left without primary key constraint.
  - You are about to alter the column `id` on the `LowCodeConfig` table. The data in that column could be lost. The data in that column will be cast from `String` to `Int`.

*/
-- RedefineTables
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_LowCodeConfig" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "json" TEXT NOT NULL
);
INSERT INTO "new_LowCodeConfig" ("id", "json") SELECT "id", "json" FROM "LowCodeConfig";
DROP TABLE "LowCodeConfig";
ALTER TABLE "new_LowCodeConfig" RENAME TO "LowCodeConfig";
PRAGMA foreign_key_check;
PRAGMA foreign_keys=ON;
