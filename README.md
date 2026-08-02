# 大模型 API 政策工作台（独立运行 · 零 token 版）

一个**完全脱离对话、自己定时更新、自己托管**的免费大模型 API 政策看板。
**每月 1 号自动更新，全程不消耗任何 LLM token**——无 API key、无 LLM 调用、无现金成本。

## 它是怎么做到零 token 的
- **理解一次性写死**：对各平台免费政策的"理解"在 `generate.py` 的 `PLATFORMS` 静态配置里（人工构建时写入一次），运行时不再需要 LLM。
- **运行时只做机械比对**：脚本用标准库 `urllib` 抓取两个**公开、无需鉴权**的数据源，统计各 provider 当前免费模型数，与上月快照 diff，自动标记「放宽 / 收紧」并生成特别提醒。
  - `ClawLabsAI/free-ai-models` 的 `data/models.json`（社区每日 GitHub Actions 更新）
  - OpenRouter 公开接口 `/api/v1/models`（筛选 `:free` 模型）
- 任一数据源抓取失败，自动降级为纯静态（不崩溃、不花 token）。

## 目录结构
```
llm-api-dashboard/
├── dashboard.html          # 前端展示（纯静态，fetch data.json）
├── generate.py             # 生成数据：零 token，仅 urllib 抓公开源 + 静态配置 diff
├── data.json               # 展示数据（每月自动覆盖）
├── live_snapshot.json      # 上月免费模型数快照（内部 diff 用，不展示）
├── .github/workflows/monthly.yml   # 每月 1 号定时任务（无 secrets）
└── README.md
```

## 部署步骤（一次配置，之后全自动，零密钥）
1. 把本目录推到你自己的 GitHub 仓库（或 fork 后改名）。
2. 仓库 **Settings → Pages → Build and deployment → Source 选 "GitHub Actions"**。
3. 完成。**无需配置任何 API key / LLM**，每月 1 号 Actions 自动跑 `generate.py`，更新 `data.json` 并重新托管。
4. 想立刻看效果：Actions 页面 → 左上角 **Run workflow** 手动触发一次。

## 本地预览
```bash
cd llm-api-dashboard
python -m http.server 8000
# 浏览器打开 http://localhost:8000/dashboard.html
```

## 成本说明
- **展示（dashboard.html）**：纯静态，零成本。
- **每月生成（generate.py）**：GitHub Actions 免费额度内运行；只用标准库抓取公开数据，**零 LLM token、零密钥、零现金成本**。
- 局限：静态配置覆盖 18 家平台的免费档描述（构建时写入）；live diff 仅对覆盖在公开免费清单里的 provider（OpenRouter / Google / NVIDIA / Mistral 等）生效，国内平台（智谱、硅基流动等）若政策变动需人工更新 `PLATFORMS`。这正是"零 token"换来的取舍——把"理解"前置到构建时。

## 与 WorkBuddy 自动化版本的区别
- WorkBuddy 自动化：每月 1 号由对话后台调用 LLM 生成月报（消耗你自有免费额度），数据写在 WorkBuddy + 同步 ima。
- 本仓库：零 token、零密钥、完全独立托管，任何设备开网页即看，不依赖任何对话工具或 LLM 额度。
