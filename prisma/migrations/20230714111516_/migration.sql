-- CreateTable
CREATE TABLE "Share" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT,
    "date" TEXT NOT NULL,
    "price" TEXT NOT NULL,
    "pe" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ShareInfo" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "stock_abbr" TEXT NOT NULL,
    "stock_number" TEXT NOT NULL,
    "stock_pinyin" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "LowCodeConfig" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "json" TEXT NOT NULL
);
