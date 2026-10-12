# 已下架文章存档

2026-10 因 Google AdSense 审核（低价值内容 / 规避类政策）从公开站点下架的三篇文章原文，原文件保留在服务器 `plusPosts` 磁盘上，这里是 GitHub 侧的备份。

- `cursor-ycursor.md`：更换机器码重置试用＋批量注册，协助绕过付费限制
- `cloudflare-warp.md`：分流访问受限服务，规避地域限制
- `v-machine-hyper-v-openwrt.md`：旁路由透明代理，规避访问控制

注意：本目录不在文章加载路径内（`app/api/post/lib.ts` 只读 `posts/` 与 `plusPosts/`），不会进入站点地图与公开列表。不要移回 `posts/` 或 `plusPosts/`。
