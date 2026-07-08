// 第三方广告接入组件（用户指定脚本：globalimmaturelunatic.com）。
//
// ⚠️ 安全说明：该域名未经验证、存在风险。因此这里把用户提供的完整 snippet
// 放进 sandbox iframe 内运行，使其无法访问主站 DOM / Cookie / localStorage，
// 也无法劫持顶层页面导航（allow-top-navigation 未开启）。
// 仅允许脚本执行与点击弹窗（allow-scripts / allow-popups）。
//
// 上线前请务必核实该广告联盟的合法性，并优先选择 Google AdSense 等可信渠道
// （见 components/AdBanner300x250.tsx，走项目既有管线）。

type SandboxedAdProps = {
  width?: number
  height?: number
  className?: string
}

const AD_SNIPPET = `
  <script>
    atOptions = {
      'key' : 'eb331ea66fa90da37a32077a95932036',
      'format' : 'iframe',
      'height' : 90,
      'width' : 728,
      'params' : {}
    };
  </script>
  <script src="https://globalimmaturelunatic.com/eb331ea66fa90da37a32077a95932036/invoke.js"></script>
`

export default function SandboxedAd({
  width = 728,
  height = 90,
  className,
}: SandboxedAdProps) {
  return (
    <aside
      className={`sandboxed-ad w-full ${className ?? ''}`}
      role="region"
      aria-label="Advertisement"
      style={{ maxWidth: width }}
    >
      <span className="sandboxed-ad__label" aria-hidden="true">
        Advertisement
      </span>
      <iframe
        title="Advertisement"
        width="100%"
        height={height}
        // 隔离第三方脚本：仅允许脚本执行与点击弹窗；禁止访问父页面/同域/Cookie/顶层导航
        sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
        srcDoc={AD_SNIPPET}
        loading="lazy"
        referrerPolicy="no-referrer"
        style={{ border: 'none', display: 'block' }}
      />
    </aside>
  )
}
