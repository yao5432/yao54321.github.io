# 丫丫资讯 · iOS 风格自动更新网站

一个**纯静态、零成本、每日自动更新**的资讯聚合站（丫丫资讯）。整体采用 iOS 设计语言（毛玻璃导航、分段控制器、圆角卡片、明暗双主题），数据由 GitHub Actions 每天定时抓取并重新生成，托管在 GitHub Pages 上即可长期自动运行。

> 网站分为三大板块：**AI 科技** / **竞技体育** / **军事政治**，风格统一、可一键切换。

## ✨ 特性

- **每日自动更新**：GitHub Actions 定时运行 `generate.py`，抓取最新内容并提交，GitHub Pages 自动生效。
- **三大板块 · 多源聚合**（均无需 API Key）：
  - **AI 科技**：Hacker News（热门 AI 讨论，按热度排序）、arXiv（cs.AI / cs.CL / cs.LG 最新论文）、科技媒体 RSS（The Verge / Ars Technica / Wired）
  - **竞技体育**：ESPN 各项目 RSS（足球 / NBA / NFL / MLB / 网球）、BBC Sport 综合资讯、Reddit 体育社区（补充）
  - **军事政治**：BBC 国际 / 政治、Al Jazeera、Google News（military / defense / geopolitics / election）等 RSS
- **中英双语**：保留英文原文，下方自动附中文翻译（生成时调用免费翻译接口，中文内容原样保留）。
- **iOS 视觉**：毛玻璃导航栏、渐变标题、一级板块切换（AI 科技 / 竞技体育 / 军事政治）+ 二级分段筛选、卡片悬浮动效、明暗自适应。
- **零依赖核心**：仅用 Python 标准库即可生成；`feedparser` 为必需依赖（用于全部 RSS 抓取）。
- **安全渲染**：页面用 `textContent` 构建 DOM，并对数据做转义，避免 XSS。

## 🚀 部署到 GitHub Pages（5 分钟）

1. 把本目录初始化为 Git 仓库并推送到 GitHub：
   ```bash
   cd ai-news-site
   git init
   git add .
   git commit -m "init: 丫丫资讯"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```
2. 在仓库 **Settings → Pages** 中，Source 选择 **Deploy from a branch**，分支选 **main**，目录选 **/ (root)**，保存。
3. 几分钟后访问 `https://<你的用户名>.github.io/<仓库名>/` 即可看到网站。
4. 首次部署后，Actions 会按 `daily.yml` 的 cron（每天北京时间 01:00）自动更新；也可在 **Actions** 页手动 `Run workflow` 立即刷新。

> 提示：GitHub Actions 对公开仓库免费，私有仓库每月也有免费额度。免费版默认仅在仓库有提交时运行计划任务；如需"纯定时"持续运行，请保持仓库为 public 或确保每月有一次活动。

## 🛠 本地预览 / 二次开发

```bash
# 生成 index.html（无网络时会使用内置示例数据，便于本地预览）
python generate.py

# 用任意静态服务器预览
python -m http.server 8000
# 浏览器打开 http://localhost:8000
```

### 自定义

- **AI 抓取关键词**：修改 `generate.py` 顶部的 `HN_KEYWORDS`。
- **各源条数**：调整 `HN_TOTAL` / `ARXIV_MAX` / `RSS_MAX_PER`。
- **AI 媒体源**：编辑 `RSS_FEEDS` 列表（加 `feedparser` 支持任意 RSS）。
- **体育源**：编辑 `SPORTS_RSS_FEEDS` 列表（ESPN 各项目 RSS 或任意体育 RSS）。
- **军事政治源**：编辑 `MIL_RSS_FEEDS` 列表（BBC / Al Jazeera / Google News 等 RSS）。
- **更新时间**：编辑 `.github/workflows/daily.yml` 中的 cron 表达式（UTC 时间）。
- **配色**：修改 `generate.py` 中 `HTML_TEMPLATE` 顶部的 CSS 变量（`--accent` 等）。

## 📁 目录结构

```
ai-news-site/
├─ generate.py              # 数据抓取 + 页面生成（核心脚本）
├─ index.html               # 生成的静态站点（每日自动覆盖）
├─ requirements.txt         # 可选依赖 feedparser
├─ .nojekyll                # 禁用 Jekyll，确保静态资源原样托管
├─ README.md                # 本文件
└─ .github/workflows/
   └─ daily.yml             # 每日定时更新工作流
```
