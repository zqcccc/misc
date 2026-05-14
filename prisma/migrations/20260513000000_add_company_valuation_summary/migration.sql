CREATE SCHEMA IF NOT EXISTS appuser AUTHORIZATION appuser;

CREATE TABLE appuser."CompanyValuationSummary" (
    "id" TEXT NOT NULL,
    "companyId" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "market" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "currency" TEXT,
    "entryType" TEXT NOT NULL DEFAULT 'manual',
    "entryNote" TEXT,
    "metrics" JSONB NOT NULL,
    "exploration" JSONB NOT NULL,
    "tags" JSONB NOT NULL,
    "profitQuality" TEXT NOT NULL,
    "profitQualityRank" INTEGER NOT NULL,
    "primaryExplanation" JSONB,
    "explanations" JSONB NOT NULL,
    "explorationScore" INTEGER NOT NULL DEFAULT 0,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "companyUpdatedAt" TIMESTAMP(3) NOT NULL,
    "searchText" TEXT NOT NULL,
    "visible" BOOLEAN NOT NULL DEFAULT true,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CompanyValuationSummary_pkey" PRIMARY KEY ("id")
);

CREATE OR REPLACE FUNCTION _company_valuation_safe_jsonb_array(value TEXT)
RETURNS JSONB AS $$
BEGIN
    IF value IS NULL OR btrim(value) = '' THEN
        RETURN '[]'::jsonb;
    END IF;

    RETURN value::jsonb;
EXCEPTION WHEN others THEN
    RETURN '[]'::jsonb;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

INSERT INTO appuser."CompanyValuationSummary" (
    "id",
    "companyId",
    "symbol",
    "market",
    "title",
    "currency",
    "entryType",
    "entryNote",
    "metrics",
    "exploration",
    "tags",
    "profitQuality",
    "profitQualityRank",
    "primaryExplanation",
    "explanations",
    "explorationScore",
    "sortOrder",
    "companyUpdatedAt",
    "searchText",
    "visible"
)
SELECT
    'cvs_' || c."id" AS "id",
    c."id" AS "companyId",
    c."symbol",
    c."market",
    c."name" AS "title",
    c."currency",
    c."entryType",
    c."entryNote",
    jsonb_build_object(
        'asOfDate', CASE WHEN v."asOfDate" IS NULL THEN NULL ELSE to_char(v."asOfDate", 'YYYY-MM-DD') END,
        'price', v."price",
        'ttmEps', v."ttmEps",
        'ttmPe', v."ttmPe",
        'profitLinePrice', v."profitLinePrice",
        'referenceLinePrice', v."referenceLinePrice",
        'upsideToProfitLine', v."upsideToProfitLine",
        'upsideToReferenceLine', v."upsideToReferenceLine"
    ) AS "metrics",
    jsonb_build_object(
        'summary', e."summary",
        'thesis', e."thesis",
        'score', e."score"
    ) AS "exploration",
    _company_valuation_safe_jsonb_array(e."tags") AS "tags",
    CASE
        WHEN COALESCE(exps."hasNonRecurringProfit", false) THEN '需调整'
        WHEN COALESCE(exps."hasProfitExplanation", false) THEN '正常'
        ELSE '待确认'
    END AS "profitQuality",
    CASE
        WHEN COALESCE(exps."hasNonRecurringProfit", false) THEN 2
        WHEN COALESCE(exps."hasProfitExplanation", false) THEN 0
        ELSE 1
    END AS "profitQualityRank",
    primary_exp."primaryExplanation",
    COALESCE(exps."explanations", '[]'::jsonb) AS "explanations",
    COALESCE(e."score", 0) AS "explorationScore",
    c."sortOrder",
    c."updatedAt" AS "companyUpdatedAt",
    lower(concat_ws(' ', c."name", c."symbol", all_tags."tags")) AS "searchText",
    c."visible"
FROM "Company" c
LEFT JOIN LATERAL (
    SELECT *
    FROM "CompanyValuationSnapshot" v
    WHERE v."companyId" = c."id"
    ORDER BY v."asOfDate" DESC, v."createdAt" DESC
    LIMIT 1
) v ON true
LEFT JOIN LATERAL (
    SELECT *
    FROM "CompanyExploration" e
    WHERE e."companyId" = c."id" AND e."visibility" = 'published'
    ORDER BY e."pinned" DESC, e."createdAt" DESC
    LIMIT 1
) e ON true
LEFT JOIN LATERAL (
    SELECT
        jsonb_agg(
            jsonb_build_object(
                'explanationType', current_exp."explanationType",
                'title', current_exp."title",
                'body', current_exp."body",
                'impactDirection', current_exp."impactDirection",
                'isRecurring', current_exp."isRecurring",
                'confidence', current_exp."confidence"
            )
            ORDER BY current_exp."asOfDate" DESC, current_exp."createdAt" DESC
        ) AS "explanations",
        bool_or(current_exp."explanationType" = 'profit') AS "hasProfitExplanation",
        bool_or(current_exp."explanationType" = 'profit' AND current_exp."isRecurring" = false) AS "hasNonRecurringProfit"
    FROM (
        SELECT *
        FROM "CompanyValuationExplanation" exp
        WHERE exp."companyId" = c."id" AND exp."isCurrent" = true
        ORDER BY exp."asOfDate" DESC, exp."createdAt" DESC
        LIMIT 8
    ) current_exp
) exps ON true
LEFT JOIN LATERAL (
    SELECT jsonb_build_object(
        'explanationType', ranked_exp."explanationType",
        'title', ranked_exp."title",
        'body', ranked_exp."body",
        'impactDirection', ranked_exp."impactDirection",
        'isRecurring', ranked_exp."isRecurring",
        'confidence', ranked_exp."confidence"
    ) AS "primaryExplanation"
    FROM "CompanyValuationExplanation" ranked_exp
    WHERE ranked_exp."companyId" = c."id" AND ranked_exp."isCurrent" = true
    ORDER BY
        CASE
            WHEN ranked_exp."explanationType" = 'profit' AND ranked_exp."isRecurring" = false THEN 0
            WHEN ranked_exp."explanationType" = 'profit' THEN 1
            WHEN ranked_exp."explanationType" = 'price' THEN 2
            ELSE 3
        END,
        ranked_exp."asOfDate" DESC,
        ranked_exp."createdAt" DESC
    LIMIT 1
) primary_exp ON true
LEFT JOIN LATERAL (
    SELECT string_agg(tag.value, ' ') AS "tags"
    FROM "CompanyExploration" tag_exp
    CROSS JOIN LATERAL jsonb_array_elements_text(_company_valuation_safe_jsonb_array(tag_exp."tags")) tag(value)
    WHERE tag_exp."companyId" = c."id" AND tag_exp."visibility" = 'published'
) all_tags ON true;

DROP FUNCTION _company_valuation_safe_jsonb_array(TEXT);

CREATE UNIQUE INDEX "CompanyValuationSummary_companyId_key" ON appuser."CompanyValuationSummary"("companyId");
CREATE INDEX "CompanyValuationSummary_visible_quality_rank_score_updated_idx" ON appuser."CompanyValuationSummary"("visible", "profitQualityRank", "explorationScore" DESC, "updatedAt" DESC);
CREATE INDEX "CompanyValuationSummary_visible_profitQuality_idx" ON appuser."CompanyValuationSummary"("visible", "profitQuality");
CREATE INDEX "CompanyValuationSummary_visible_sort_companyUpdated_idx" ON appuser."CompanyValuationSummary"("visible", "sortOrder" DESC, "companyUpdatedAt" DESC);
CREATE INDEX "CompanyValuationSummary_visible_market_symbol_idx" ON appuser."CompanyValuationSummary"("visible", "market", "symbol");
