# Company Valuation Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the profit-line page into a company valuation page that can show AI-discovered company entries, valuation snapshots, and explanations for current price/profit quality.

**Architecture:** Keep Redis for live profit-line API caching. Store durable company discovery, valuation snapshots, and narrative explanations in Prisma/SQLite tables. Add a small summary helper and API that shape database rows into frontend-ready sidebar cards.

**Tech Stack:** Next.js App Router, Prisma SQLite, TypeScript, existing ts-node test style.

---

### Task 1: Valuation Summary Contract

**Files:**
- Create: `tests/company-valuation-summary.test.ts`
- Create: `app/api/company-valuation/summary.ts`

- [ ] Write a failing test for picking the primary explanation and formatting a company card.
- [ ] Implement `parseJsonArray`, `pickPrimaryExplanation`, and `buildCompanyValuationCard`.
- [ ] Run `yarn ts-node --project tsconfig-debug.json tests/company-valuation-summary.test.ts`.

### Task 2: Prisma Models

**Files:**
- Modify: `prisma/schema.prisma`

- [ ] Add `Company`, `CompanyExplorationRun`, `CompanyExploration`, `CompanyValuationSnapshot`, `CompanyValuationExplanation`, and `CompanyPageEntry`.
- [ ] Keep JSON-like arrays as nullable strings for SQLite compatibility.
- [ ] Run `yarn prisma:generate`.

### Task 3: API

**Files:**
- Create: `app/api/company-valuation/route.ts`

- [ ] Query visible page entries with company, latest exploration, latest valuation snapshot, and explanations.
- [ ] Support optional `symbol` filtering for the current `/pe` company.
- [ ] Return frontend-ready cards using the summary helper.

### Task 4: Page Extension

**Files:**
- Modify: `app/pe/page.tsx`

- [ ] Fetch `/api/company-valuation?symbol=...` alongside profit-line data.
- [ ] Add left-side company shortcut entries.
- [ ] Add valuation explanation panels for price and profit quality.
- [ ] Keep existing chart behavior intact.

### Task 5: Verification

- [ ] Run focused tests.
- [ ] Run `yarn tsc --noEmit`.
- [ ] Run `yarn lint`.
- [ ] Run `yarn build`.
