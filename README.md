# c9cu

`onlylike.work` 的个人研究、工程记录与自用工具。生产页面使用 Next.js 16、React 19、Tailwind CSS 与 ECharts。

## 本地开发

需要 Node.js 22+ 与 pnpm：

```bash
pnpm install
pnpm dev
```

开发地址为 `http://localhost:3011`。公司估值等数据库功能需要可用的 `DATABASE_URL`；本地 PostgreSQL 通过现有 SSH 转发提供，不启动本地数据库容器。

```bash
pnpm build
pnpm start
```

## 公开数据服务

- `/ashare-strategy`：A 股策略信号与历史回测。
- `/smallcap-strategy`：小微盘轮动持仓与回测。
- `/etf-premium`：跨境 ETF 实时溢价、同指数载体比较，以及收盘价与单位净值重建的历史溢价。实时行情使用东方财富公开接口，受限时使用已核对字段的腾讯行情；页面标注实际来源与数据日期。
- `/pe`：利润线与估值。
- `/tools`：浏览器本地图片工具与 Chrome 扩展。

## 部署

生产 Compose 包含 `misc`、`ashare-signal` 与 `ashare-smallcap-quant`。GitHub Actions 构建并推送三个镜像，全部成功后通过 webhook 调用服务器部署；服务器执行 `deploy.sh` 拉取镜像并更新服务。

保留的管理员写接口需要在部署环境配置 `ADMIN_API_TOKEN`。未配置时这些接口默认返回 503；短链管理页只在当前页面输入令牌，不在浏览器持久化。

TRHRP、EMA、B&H、Pyramid 与旧 Chat 的研究代码仅作档案保留，公开页面和 API 返回 404，不启动对应 daemon，也不加入部署编排。
