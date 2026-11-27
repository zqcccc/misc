import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import FinancialNotice from '@/components/site/FinancialNotice'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '跨境 ETF 溢价监控',
  description:
    '按 IOPV 实时估值监控跨境 ETF（QDII 与港股通）的场内溢价：统一公式计算溢价率、按跟踪指数分组对比、标注同组低溢价载体，并区分净值披露口径与盘中口径。',
  alternates: { canonical: '/etf-premium' },
  openGraph: {
    title: '跨境 ETF 溢价监控',
    description:
      '按 IOPV 监控 QDII 与港股通 ETF 的场内溢价，分组对比，口径与局限写在页面里。',
    url: `${SITE_URL}/etf-premium`,
  },
}

/**
 * 页面级样式：只作用于 .etf-premium-page，全部取自 globals.css 的 --site-* 主题变量，
 * 深浅主题由 .dark 类自动切换。globals.css 归公共层所有，这里不改动它。
 */
const PAGE_CSS = `
.etf-premium-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 48px 20px 64px;
  color: var(--site-ink);
}
.etf-premium-page ::selection { background: var(--site-link); color: #fff; }
.etf-premium-page :focus-visible { outline: 3px solid var(--site-link); outline-offset: 2px; }
.etf-premium-page a { color: var(--site-link); }
.etf-premium-page a:hover { color: var(--site-link-strong); text-decoration: underline; }

.etf-premium-head { margin-bottom: 34px; }
.etf-premium-head h1 {
  font-family: var(--site-display);
  font-weight: 700;
  font-size: clamp(2rem, 4.4vw, 3.2rem);
  line-height: 1.06;
  letter-spacing: -0.03em;
  margin: 0 0 14px;
}
.etf-premium-head p { color: var(--site-muted); line-height: 1.8; max-width: 68ch; margin: 0; }

.etf-premium-section { margin-top: 48px; }
.etf-premium-section > h2 {
  font-size: 19px;
  font-weight: 700;
  margin: 0 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--site-ink);
}
.etf-premium-section > p,
.etf-premium-section li { color: var(--site-ink); line-height: 1.8; font-size: 15px; }
.etf-premium-section > p { margin: 0 0 12px; max-width: 76ch; }
.etf-premium-section ul { margin: 0; padding: 0; list-style: none; }
.etf-premium-section li { padding: 9px 0; border-top: 1px solid var(--site-line); }
.etf-premium-section li:first-child { border-top: none; }
.etf-premium-section code {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--site-paper);
  padding: 1px 6px;
}
.etf-premium-section strong { font-weight: 650; }

.etf-premium-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
.etf-premium-toolbar input,
.etf-premium-toolbar select {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--site-line);
  border-radius: 9px;
  background: var(--site-panel);
  color: var(--site-ink);
  font-size: 14px;
}
.etf-premium-toolbar input { width: 200px; }
.etf-premium-toolbar button {
  height: 38px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1px solid var(--site-line);
  background: transparent;
  color: var(--site-ink);
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}
.etf-premium-toolbar button.etf-btn-primary {
  background: var(--site-link);
  border-color: var(--site-link);
  color: #fff;
}
.etf-premium-toolbar button:hover { border-color: var(--site-link-strong); color: var(--site-link-strong); }
.etf-premium-toolbar button.etf-btn-primary:hover { background: var(--site-link-strong); border-color: var(--site-link-strong); color: #fff; }
.etf-premium-toolbar button:disabled { opacity: 0.55; cursor: default; }

.etf-premium-meta { color: var(--site-muted); font-size: 13px; line-height: 1.7; margin: 0 0 14px; font-variant-numeric: tabular-nums; }

.etf-premium-state {
  border: 1px solid var(--site-line);
  background: var(--site-panel);
  padding: 26px 22px;
  color: var(--site-muted);
  line-height: 1.8;
}
.etf-premium-state strong { color: var(--site-ink); display: block; margin-bottom: 6px; }
.etf-premium-state.is-error { border-color: var(--neg); }
.etf-premium-state.is-error strong { color: var(--neg); }

.etf-premium-tablewrap {
  border: 1px solid var(--site-line);
  background: var(--site-panel);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-color: var(--site-line) transparent;
}
.etf-premium-tablewrap::-webkit-scrollbar { height: 10px; }
.etf-premium-tablewrap::-webkit-scrollbar-thumb { background: var(--site-line); border-radius: 5px; }
.etf-premium-table { width: 100%; min-width: 920px; border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }
.etf-premium-table th {
  text-align: left;
  font-size: 12px;
  font-weight: 750;
  color: var(--site-muted);
  padding: 10px 12px;
  border-bottom: 1px solid var(--site-line);
  white-space: nowrap;
}
.etf-premium-table td { padding: 9px 12px; border-bottom: 1px solid var(--site-line); white-space: nowrap; }
.etf-premium-table tbody tr:last-child td { border-bottom: none; }
.etf-premium-table tbody tr:hover { background: var(--site-paper); }
.etf-premium-table .num { text-align: right; }
.etf-premium-name-btn {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: var(--site-ink);
  font-weight: 650;
  cursor: pointer;
  text-align: left;
}
.etf-premium-name-btn:hover { color: var(--site-link-strong); text-decoration: underline; }
.etf-premium-code { color: var(--site-muted); font-size: 12px; margin-left: 6px; }
.etf-premium-premium.pos { color: var(--pos); font-weight: 650; }
.etf-premium-premium.neg { color: var(--neg); font-weight: 650; }
.etf-premium-low {
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  font-weight: 750;
  color: var(--site-signal);
  border: 1px solid var(--site-signal);
  border-radius: 999px;
  padding: 1px 7px;
}
.etf-premium-stale { color: var(--site-signal); font-size: 12px; }
.etf-premium-table .missing { color: var(--site-muted); }
.etf-premium-legend { color: var(--site-muted); font-size: 13px; margin: 10px 0 0; line-height: 1.7; }

.etf-premium-detail {
  margin-top: 26px;
  border: 1px solid var(--site-line);
  background: var(--site-panel);
  padding: 20px 22px;
}
.etf-premium-detail-head { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: baseline; margin-bottom: 6px; }
.etf-premium-detail-head h3 { font-size: 18px; font-weight: 700; margin: 0; }
.etf-premium-detail-head .etf-premium-chip {
  font-size: 12px;
  font-weight: 750;
  color: var(--site-muted);
  border: 1px solid var(--site-line);
  border-radius: 999px;
  padding: 2px 9px;
}
.etf-premium-detail-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--site-link);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 2px;
}
.etf-premium-detail-facts { color: var(--site-muted); font-size: 13px; line-height: 1.8; margin: 0 0 14px; font-variant-numeric: tabular-nums; }
.etf-premium-detail-range { display: flex; gap: 6px; margin-bottom: 12px; }
.etf-premium-detail-range button {
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
  border-radius: 9px;
  border: 1px solid var(--site-line);
  background: transparent;
  color: var(--site-ink);
  cursor: pointer;
  font-variant-numeric: tabular-nums;
}
.etf-premium-detail-range button[aria-pressed='true'] { background: var(--site-link); border-color: var(--site-link); color: #fff; }
.etf-premium-chart { width: 100%; height: 340px; }
.etf-premium-detail-notes { margin: 16px 0 0; padding: 0; list-style: none; }
.etf-premium-detail-notes li {
  font-size: 13px;
  color: var(--site-muted);
  line-height: 1.8;
  padding: 8px 0;
  border-top: 1px solid var(--site-line);
}

.etf-premium-page .financial-notice {
  margin-top: 48px;
  border: 1px solid var(--site-line);
  border-top: 2px solid var(--site-signal);
  padding: 14px 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  align-items: baseline;
}
.etf-premium-page .financial-notice strong { font-size: 14px; font-weight: 750; }
.etf-premium-page .financial-notice p { margin: 4px 0 0; color: var(--site-muted); font-size: 13px; line-height: 1.8; max-width: 72ch; }
.etf-premium-page .financial-notice a { font-size: 13px; white-space: nowrap; }

@media (max-width: 640px) {
  .etf-premium-page { padding: 34px 14px 48px; }
  .etf-premium-toolbar input { width: 100%; flex-basis: 100%; }
  .etf-premium-detail { padding: 16px 14px; }
  .etf-premium-chart { height: 280px; }
}
@media (prefers-reduced-motion: reduce) {
  .etf-premium-page * { transition: none !important; animation: none !important; }
}
`

export default function EtfPremiumLayout({ children }: { children: ReactNode }) {
  return (
    <div className='etf-premium-page'>
      <style>{PAGE_CSS}</style>
      {children}
      <FinancialNotice title='跨境 ETF 溢价监控的数据边界' />
    </div>
  )
}
