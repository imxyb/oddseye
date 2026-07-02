---
title: "预测市场雷达与纸面交易系统 V1 工程化落地文档（轻量用量管理版）"
author: "ChatGPT"
date: "2026-07-01"
lang: zh-CN
---

# 预测市场雷达与纸面交易系统 V1 工程化落地文档（轻量用量管理版）

**项目代号**：Prediction Radar  
**版本**：V1.2 轻量用量管理工程启动版  
**日期**：2026-07-01  
**目标用户**：自用  
**第一阶段交易模式**：纸面交易，不接真实下单  
**第一阶段 App**：iOS App，使用 Expo Go 开发与调试  
**第一阶段市场分类**：Crypto + Macro/Economics

---

## 0. 一句话目标

构建一个自用的预测市场雷达系统，从 Codex 获取 Polymarket、Kalshi 等预测市场数据，先覆盖 Crypto 与 Macro/Economics 两类市场，系统自动筛选高质量市场、计算市场质量分、生成模型信号，并通过纸面交易模块模拟下单、持仓、退出和复盘；iOS App 作为移动端操作界面，用配置文件账号密码做简单登录。

第一版不追求“自动赚钱机器人”，而是先搭出一个可以长期迭代的交易研究平台：

```text
数据获取 → 标准化 → 市场筛选 → 市场质量评分 → 模型概率 → 信号 → 纸面交易 → 复盘
```

**Codex 使用策略更新**：Codex 账号不是预测市场雷达独享。另一个项目预计每天消耗 10,000+ requests，但本系统 V1 不在代码层做硬性预算拦截。V1 采用“低频默认采集 + watchlist/持仓优先 + 用量日志观察”的轻量策略：日常建议跑在 1,000-2,000 requests/day，行情剧烈或调试时可临时提高到约 3,000-5,000 requests/day；后续你可以根据 Codex 实际额度和另一个项目的真实用量，直接调整采集频率与 watchlist 规模。

---

## 1. V1 边界与非目标

### 1.1 V1 必须实现

| 模块 | V1 目标 |
|---|---|
| 数据源 | 后端通过 Codex GraphQL 获取预测市场数据 |
| 市场分类 | Crypto + Macro/Economics |
| 市场雷达 | 支持按分类、平台、成交量、流动性、价差、关闭时间筛选 |
| 市场详情 | 显示市场基本信息、YES/NO bid/ask、隐含概率、流动性、成交量、历史图表 |
| 质量评分 | 对市场做 `market_quality_score`，过滤垃圾市场 |
| 信号模块 | 生成可解释信号：观察、买 YES、买 NO、退出、忽略 |
| 纸面交易 | 模拟限价下单、成交、持仓、PnL、胜率、回撤 |
| iOS App | Expo Go + Expo Router + React Native 页面 |
| 登录 | 后端配置文件账号密码，移动端只保存 token |
| 扩展性 | 预留真实交易执行接口、更多数据源、更多市场分类 |

### 1.2 V1 明确不做

| 不做项 | 原因 |
|---|---|
| 真实自动下单 | 先验证模型和纸面交易结果，降低风险 |
| 高频交易 | 预测市场流动性、API 成本和结算不适合一开始高频 |
| 做市策略 | 需要更复杂的库存管理、盘口模型和风控 |
| 政治/体育自动交易 | 监管与噪音更复杂，不适合作为新手第一版 |
| 多用户系统 | 自用系统，避免过早复杂化 |
| 原生 iOS 定制功能 | V1 使用 Expo Go，避免引入 development build 复杂度 |

---

## 2. 关键工程判断

### 2.1 Codex API Key 只放后端

Codex API Key、后续交易所 API Key、数据库密码等敏感配置绝对不能放在 Expo App 里。Expo 的 `EXPO_PUBLIC_` 环境变量会被打包进客户端 JavaScript bundle，不能放任何 secret。移动端只保存后端颁发的短期 token。

**正确链路**：

```text
iOS App → 自己的后端 API → Codex GraphQL
```

**错误链路**：

```text
iOS App → Codex GraphQL
```

### 2.2 自用登录也走后端校验

用户说“登录直接用配置文件的账号密码”，V1 推荐实现为：

```text
backend/config/app.yaml 里配置 username + password_hash
App 调 POST /auth/login
后端校验成功后返回 JWT
App 用 SecureStore 保存 JWT
后续请求带 Authorization: Bearer <token>
```

不要把账号密码写进 App 源码，也不要把密码放进 `EXPO_PUBLIC_` 环境变量。

### 2.3 V1 使用 Expo Go，但架构预留迁移

Expo Go 可以满足第一版：登录、列表、详情、图表、纸面交易、设置、SecureStore 都可以做。不要引入 Expo Go 不支持的自定义原生模块。未来如果需要推送通知、后台长连接、原生安全能力或发布到 TestFlight，再迁移到 development build。

### 2.4 纸面交易必须比“理想成交”更保守

纸面交易不能用 last price 作为成交价。买入 YES 要按 YES ask 模拟，退出或卖出要按 YES bid 模拟。否则回测结果会虚高。

V1 纸面成交规则：

```text
BUY_YES: 以 outcome0.bestAskCT 或 YES ask 成交
SELL_YES / EXIT_YES: 以 outcome0.bestBidCT 或 YES bid 成交
BUY_NO: 以 outcome1.bestAskCT 或 NO ask 成交
SELL_NO / EXIT_NO: 以 outcome1.bestBidCT 或 NO bid 成交
```

---

## 3. 技术栈选择

### 3.1 总体技术栈

| 层 | 技术 | 选择理由 |
|---|---|---|
| 移动端 | Expo Go + React Native + Expo Router | 快速开发 iOS App，迭代成本低 |
| App 状态 | TanStack Query + Zustand | 服务端状态与本地 UI 状态分离 |
| App 安全存储 | expo-secure-store | 存 JWT 等小型敏感值 |
| 后端 API | Python FastAPI | 快速、类型友好、适合量化和数据逻辑 |
| ORM/迁移 | SQLAlchemy 2.x + Alembic | 成熟稳定，便于复杂查询 |
| 数据库 | PostgreSQL 16 + TimescaleDB 可选 | 结构化数据 + 时间序列快照 |
| 后台任务 | APScheduler 独立 worker 进程 | V1 简单可靠；后续可替换 Celery |
| 缓存 | Redis 可选 | 缓存热点市场、token、任务锁 |
| 图表 | react-native-svg 或 lightweight chart WebView | V1 可先用 SVG/简化线图 |
| 部署 | Docker Compose | 自用 VPS 或本地 NAS 快速部署 |
| 监控 | structlog + Prometheus 可选 | 先日志化，后续补指标 |

### 3.2 为什么后端用 Python 而不是 Node

这个系统后续会有概率模型、回测、统计、数据清洗、时间序列处理。Python 在量化、数据科学、回测方面生态更直接。移动端是 TypeScript，后端是 Python，边界通过 OpenAPI/REST 清晰隔离。

---

## 4. 系统架构

### 4.1 V1 架构图

```text
┌─────────────────────────────┐
│          iOS App             │
│  Expo Go / React Native      │
│  - Radar                     │
│  - Market Detail             │
│  - Signals                   │
│  - Paper Portfolio           │
└──────────────┬──────────────┘
               │ HTTPS + JWT
               ▼
┌─────────────────────────────┐
│        FastAPI Backend       │
│  - Auth                      │
│  - Radar API                 │
│  - Market API                │
│  - Signal API                │
│  - Paper Trading API         │
└──────────────┬──────────────┘
               │ internal service calls
               ▼
┌─────────────────────────────┐
│       Worker Processes       │
│  - Codex Ingestion Worker    │
│  - Signal Worker             │
│  - Paper Mark-to-Market      │
│  - Resolution Poller         │
└───────┬─────────────┬───────┘
        │             │
        ▼             ▼
┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │ Redis Cache   │
│ Timeseries   │  │ optional      │
└──────────────┘  └──────────────┘
        ▲
        │ GraphQL HTTPS
        ▼
┌─────────────────────────────┐
│          Codex API           │
│ Prediction Markets / Tokens  │
└─────────────────────────────┘
```

### 4.2 模块边界

```text
Codex Client
  只负责 Codex GraphQL 请求和响应解析

Market Normalizer
  把 Codex 的 event / market / outcome 标准化成内部统一 schema

Ingestion Worker
  定时拉取市场、快照、图表、结算状态

Quality Engine
  计算市场质量分，过滤不值得交易的市场

Strategy Engine
  根据市场和外部数据计算模型概率 p_model

Signal Engine
  根据 p_model、市场价格、质量分、风控规则生成信号

Paper Trading Engine
  根据当前快照模拟订单成交、持仓、PnL

Mobile API
  给 App 提供稳定、少量、聚合后的数据，不把 Codex 原始结构暴露给移动端
```

---

## 5. Monorepo 目录结构

```text
prediction-radar/
  README.md
  docker-compose.yml
  .env.example

  backend/
    pyproject.toml
    alembic.ini
    app/
      main.py
      core/
        config.py
        security.py
        logging.py
        time.py
      api/
        deps.py
        routes/
          auth.py
          health.py
          radar.py
          markets.py
          signals.py
          paper.py
          settings.py
      db/
        session.py
        models.py
        repositories/
      codex/
        client.py
        queries.py
        schemas.py
      normalizer/
        prediction_market.py
      scoring/
        market_quality.py
        risk.py
      strategies/
        base.py
        crypto_threshold.py
        macro_calendar.py
      paper/
        engine.py
        accounting.py
        fills.py
      workers/
        ingest.py
        signal.py
        paper_mark.py
        resolution.py
      tools/
        hash_password.py
        seed_watchlist.py
    tests/
      unit/
      integration/

  mobile/
    app.json
    package.json
    .env.example
    app/
      _layout.tsx
      login.tsx
      (tabs)/
        _layout.tsx
        radar.tsx
        signals.tsx
        portfolio.tsx
        settings.tsx
      market/
        [id].tsx
      paper/
        new-order.tsx
    src/
      api/
        client.ts
        auth.ts
        radar.ts
        markets.ts
        signals.ts
        paper.ts
      components/
        MarketCard.tsx
        SignalBadge.tsx
        ProbabilityChart.tsx
        PaperOrderSheet.tsx
      stores/
        authStore.ts
        filterStore.ts
      utils/
        format.ts
        probability.ts

  infra/
    postgres/
      init.sql
    nginx/
      nginx.conf

  config/
    app.example.yaml
    categories.example.yaml
    strategy.example.yaml
    watchlist.example.yaml
```

---

## 6. 配置设计

### 6.1 后端环境变量 `.env`

```bash
APP_ENV=dev
APP_CONFIG_PATH=./config/app.yaml
DATABASE_URL=postgresql+psycopg://radar:radar@localhost:5432/radar
REDIS_URL=redis://localhost:6379/0
CODEX_API_KEY=replace_me
JWT_SECRET=replace_with_long_random_string
JWT_EXPIRES_DAYS=7
LOG_LEVEL=INFO
```

### 6.2 后端配置文件 `config/app.yaml`

```yaml
app:
  name: prediction-radar
  timezone: Asia/Singapore
  base_currency: USDC

auth:
  users:
    - username: biaoge
      # 使用 python -m app.tools.hash_password 生成
      password_hash: "$2b$12$replace_with_bcrypt_hash"
      role: admin
  token_expires_days: 7

codex:
  endpoint: "https://graph.codex.io/graphql"
  timeout_seconds: 20
  max_retries: 3
  # 请求量只做运行参考，不做代码层硬拦截。
  usage_tracking_enabled: true
  usage_policy: advisory_only
  # 整个 Codex 账号的参考月额度，不是本项目独享额度。
  global_monthly_reference_budget: 1000000
  # 另一个项目的保守估算。后续用账单或控制台真实 usage 覆盖。
  external_daily_usage_estimate: 12000
  # 雷达的默认运行目标。只是建议值，用于观察和报表，不用于拒绝请求。
  radar_daily_target_requests: 2000
  radar_daily_review_threshold: 5000
  radar_monthly_review_threshold: 150000
  fetch_profile: light      # light / normal / aggressive，后续按额度调整

radar:
  enabled_categories:
    - crypto
    - economics
    - finance
  protocols:
    - POLYMARKET
    - KALSHI
  min_liquidity_usd: 1000
  min_volume_usd_24h: 500
  max_spread_ct: 0.08
  max_markets_per_ingest: 300

paper:
  starting_cash: 10000
  currency: USDC
  fee_bps: 0
  slippage_bps: 25
  max_position_pct: 0.03
  max_daily_loss_pct: 0.03
  max_category_exposure_pct: 0.15
  allow_short: false

jobs:
  categories_refresh_cron: "0 3 * * *"
  # 低消耗默认值：后续可根据 Codex 额度和信号质量调高。
  market_discovery_seconds: 1800
  hot_market_snapshot_seconds: 300
  warm_market_snapshot_seconds: 1800
  cold_market_snapshot_seconds: 21600
  signal_seconds: 300
  paper_mark_seconds: 300
  resolution_poll_seconds: 7200

ingestion_tiers:
  hot_watchlist_max_markets: 30
  warm_pool_max_markets: 120
  cold_pool_max_markets: 500
  bars_fetch_mode: on_demand
  manual_refresh_enabled: true
  # 不在代码层限制每日请求数；通过日志观察实际消耗。
```

### 6.3 移动端 `.env`

```bash
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.10:8000
EXPO_PUBLIC_APP_ENV=dev
```

移动端只允许放公开配置。不要放 Codex API Key，不要放登录密码，不要放 JWT secret。

---

## 7. Codex 数据接入方案

### 7.1 GraphQL 基础

后端通过 HTTPS POST 调用 Codex GraphQL endpoint：

```text
https://graph.codex.io/graphql
```

请求头：

```http
Authorization: <CODEX_API_KEY>
Content-Type: application/json
```

### 7.2 分类树同步

启动时或每天同步一次分类树，用于 App 的筛选器。

```graphql
query PredictionCategories {
  predictionCategories {
    name
    slug
    subcategories {
      name
      slug
      subcategories {
        name
        slug
      }
    }
  }
}
```

保存到表：`prediction_categories`。

### 7.3 市场发现

V1 推荐先按 event 拉取，再按 event 拉市场价格。Codex 官方推荐发现页可以先用 `filterPredictionEvents` 获取事件和 market IDs，再用 `filterPredictionMarkets(eventIds: [...])` 获取具体市场价格。

#### 7.3.1 拉取 Crypto / Macro 开放事件

```graphql
query DiscoverEvents($categories: [String!], $limit: Int!, $offset: Int!) {
  filterPredictionEvents(
    filters: {
      protocol: [POLYMARKET, KALSHI]
      status: [OPEN]
      categories: $categories
    }
    rankings: [{ attribute: relevanceScore24h, direction: DESC }]
    limit: $limit
    offset: $offset
  ) {
    count
    page
    results {
      id
      status
      categories
      marketCount
      trendingScore24h
      relevanceScore24h
      liquidityUsd
      openInterestUsd
      volumeUsd24h
      trades24h
      uniqueTraders24h
      event {
        id
        protocol
        status
        slug
        question
        description
        imageThumbUrl
        venueUrl
        closesAt
        resolvesAt
      }
      markets {
        id
        label
      }
    }
  }
}
```

#### 7.3.2 拉取具体市场和 outcome 价格

```graphql
query EventMarkets($eventIds: [String!], $limit: Int!) {
  filterPredictionMarkets(
    eventIds: $eventIds
    rankings: [{ attribute: openInterestUsd, direction: DESC }]
    limit: $limit
  ) {
    count
    results {
      id
      eventLabel
      status
      market {
        id
        eventId
        protocol
        label
        question
        imageThumbUrl
        status
        closesAt
        resolvesAt
      }
      outcome0 {
        label
        bestAskCT
        bestBidCT
        spreadCT
        lastPriceCT
        liquidityCT
        volumeUsd24h
        priceChange24h
      }
      outcome1 {
        label
        bestAskCT
        bestBidCT
        spreadCT
        lastPriceCT
        liquidityCT
        volumeUsd24h
        priceChange24h
      }
      competitiveScore24h
      trendingScore24h
      liquidityUsd
      openInterestUsd
      volumeUsd24h
      trades24h
      priceCompetitiveness
    }
  }
}
```

### 7.4 市场详情图表

V1 市场详情页调用后端，后端再调用 Codex 的 `predictionMarketBars`。图表数据不需要对所有市场高频拉取，只在用户打开详情页或市场进入 watchlist 后拉取。

```graphql
query PredictionMarketBars($marketId: String!, $from: Int!, $to: Int!, $resolution: String!) {
  predictionMarketBars(
    input: {
      marketId: $marketId
      from: $from
      to: $to
      resolution: $resolution
      removeEmptyBars: true
    }
  ) {
    marketId
    predictionMarket {
      id
      label
      question
      outcomeLabels
      eventLabel
    }
    bars {
      t
      volumeUsd
      trades
      uniqueTraders
      openInterestUsd { o h l c }
      outcome0 {
        volumeUsd
        priceCollateralToken { o h l c }
        bidCollateralToken { o h l c }
        askCollateralToken { o h l c }
      }
      outcome1 {
        volumeUsd
        priceCollateralToken { o h l c }
        bidCollateralToken { o h l c }
        askCollateralToken { o h l c }
      }
    }
  }
}
```

### 7.5 API 请求用量：作为运行建议，不做代码硬卡

Codex 账号不是本系统独享。另一个项目预计每天消耗 10,000+ requests，按 30 天估算就是 300,000+ requests/month。雷达第一版不需要在代码层做复杂的预算拦截；更适合用低频默认采集、分层刷新和 usage 日志，把请求量控制在一个大致合理的范围内。

V1 建议目标如下：

| 项目 | requests/day 参考值 | requests/month，按 30 天 | 说明 |
|---|---:|---:|---|
| 其他项目估算 | 10,000-12,000+ | 300,000-360,000+ | 已有业务，优先级高于雷达 |
| 雷达日常模式 | 1,000-2,000 | 30,000-60,000 | 默认推荐模式，适合长期运行 |
| 雷达调试/行情活跃模式 | 3,000-5,000 | 90,000-150,000 | 需要更多 watchlist 或更快刷新时使用 |
| 全账号月度参考 | 约 1,000,000，可略超 | 以 Codex 套餐和后台为准 | 不在代码层强制停止，由你根据实际额度调整 |

这套策略的重点不是“超过多少就让代码拒绝请求”，而是：默认参数足够保守，真实消耗可见，后续调额度或扩大市场范围时只需要改配置。

### 7.6 分层采集策略

V1 不做全市场高频轮询，而是把市场分为 hot、warm、cold 三层。这样不需要请求量硬卡，也能自然降低 Codex 请求量。

| 层级 | 市场来源 | 最大数量 | 默认刷新频率 | 说明 |
|---|---|---:|---:|---|
| Hot | watchlist、已有纸面持仓、未过期强信号、即将触发的市场 | 30 | 5 分钟 | 最高优先级，保证 App 和纸面持仓可用 |
| Warm | 质量分高、流动性好、成交活跃、模型可解析 | 120 | 30 分钟 | 用于发现新机会 |
| Cold | 刚发现但质量一般、低流动性、长期市场 | 500 | 6 小时 | 低频跟踪，避免漏掉后续升温 |
| Archived | 已关闭、已结算、长期无流动性 | 不限制 | 停止或每天 1 次 | 只用于复盘和历史查询 |

Codex 请求策略：

| 数据 | 默认频率 | 请求控制思路 | 说明 |
|---|---:|---|---|
| 分类树 | 1 次/天 | 缓存 24 小时 | 分类很少变化，不需要频繁拉 |
| 事件发现 | 30 分钟/次 | 限制分类、分页和 page size | 只发现 Crypto/Macro OPEN events |
| Hot 市场快照 | 5 分钟/次 | 尽量批量按 IDs 查询 | 包括持仓、watchlist、强信号 |
| Warm 市场快照 | 30 分钟/次 | 分页批量查询 | 只保留质量分靠前市场 |
| Cold 市场刷新 | 6 小时/次 | 严格分页上限 | 更新是否升温，不拉图表 |
| 图表 bars | 按需 | 用户打开详情页、加入 watchlist 或持仓时才拉 | 避免给所有市场拉历史线 |
| 结算状态 | 2 小时/次 | 临近结算市场优先 | 纸面交易需要结算 PnL |
| 手动刷新 | 按需 | 只触发当前页面或当前市场刷新 | 自用系统可以开放，不做复杂限额 |
| WebSocket | V1 暂不启用 | 暂不引入持续推送 | 后续 watchlist 扩大后再考虑 |

在一次 GraphQL 请求可以批量返回多个 event/market 的前提下，正常日消耗目标应控制在 1,000-2,000 requests/day；3,000-5,000 requests/day 是给调试、手动刷新和加密行情剧烈波动预留的运行空间。真实消耗以后端 `api_usage_ledger` 为准，后续根据 Codex 控制台和账单调整。

### 7.7 轻量用量统计：记录即可，不做请求拦截

V1 不实现任何会阻断请求的用量治理模块。所有 Codex 请求统一走 `CodexClient` 封装，目的只是：

```text
1. 统一 timeout、retry、error handling。
2. 统一记录每次 Codex 请求的 kind、耗时、成功/失败。
3. 可以在 App 设置页或后台日志看到今天/本月大概用了多少 requests。
4. 后续如果真的需要更精细的套餐策略，再基于同一张 usage 表扩展。
```

建议的轻量记录伪代码：

```python
async def call_codex(kind: str, query: str, variables: dict) -> dict:
    started = utcnow()
    status = "success"
    try:
        return await graphql_post(query=query, variables=variables)
    except Exception:
        status = "failed"
        raise
    finally:
        await usage_service.record(
            provider="codex",
            kind=kind,
            request_count=1,
            status=status,
            duration_ms=(utcnow() - started).total_seconds() * 1000,
        )
```

### 7.8 App 侧刷新策略

App 的“下拉刷新”默认调用后端缓存接口，保证体验快、请求少。需要更实时的数据时，可以提供“刷新当前市场”或“刷新当前 watchlist”按钮，由后端触发一次 Codex 拉取并更新缓存。

App 返回数据要带 freshness，方便你知道价格是不是已经过期：

```json
{
  "data": [],
  "freshness": {
    "last_snapshot_at": "2026-07-01T10:00:00+08:00",
    "age_seconds": 420,
    "is_stale": false,
    "codex_usage_hint": {
      "today_requests": 1280,
      "month_requests": 38400,
      "fetch_profile": "light"
    }
  }
}
```

当 `is_stale=true` 时，App 详情页必须明显提示：当前价格来自本地缓存，纸面开仓前最好手动刷新当前市场。

---

## 8. 数据库设计

### 8.1 表设计原则

1. Codex 原始 JSON 必须保留，方便字段变化时回放和 debug。
2. 内部核心字段要标准化，避免前端依赖 Codex 原始结构。
3. 快照表只存查询和回测需要的字段，不要无限制存所有原始响应。
4. 所有金额字段使用 `numeric`，所有时间使用 `timestamptz`。
5. event、market、outcome 使用内部 UUID；外部 ID 另存。

### 8.2 核心 DDL

```sql
create table venues (
  id uuid primary key,
  code text not null unique,
  name text not null,
  supports_execution boolean not null default false,
  status text not null default 'active',
  created_at timestamptz not null default now()
);

create table prediction_categories (
  id uuid primary key,
  slug text not null unique,
  name text not null,
  parent_slug text,
  raw_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table prediction_events (
  id uuid primary key,
  venue_id uuid not null references venues(id),
  external_event_id text not null,
  protocol text not null,
  slug text,
  question text not null,
  description text,
  categories text[] not null default '{}',
  status text not null,
  venue_url text,
  image_thumb_url text,
  closes_at timestamptz,
  resolves_at timestamptz,
  market_count int not null default 0,
  raw_json jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (venue_id, external_event_id)
);

create table prediction_markets (
  id uuid primary key,
  event_id uuid not null references prediction_events(id),
  venue_id uuid not null references venues(id),
  external_market_id text not null,
  protocol text not null,
  label text,
  question text not null,
  status text not null,
  outcome_type text not null default 'binary',
  image_thumb_url text,
  closes_at timestamptz,
  resolves_at timestamptz,
  resolution_source text,
  raw_json jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (venue_id, external_market_id)
);

create table market_outcomes (
  id uuid primary key,
  market_id uuid not null references prediction_markets(id),
  outcome_index int not null,
  label text not null,
  side text not null,
  external_token_id text,
  raw_json jsonb not null default '{}'::jsonb,
  unique (market_id, outcome_index)
);

create table market_snapshots (
  id bigserial primary key,
  market_id uuid not null references prediction_markets(id),
  ts timestamptz not null,
  outcome0_label text,
  outcome0_best_ask numeric,
  outcome0_best_bid numeric,
  outcome0_spread numeric,
  outcome0_last_price numeric,
  outcome0_liquidity numeric,
  outcome0_volume_usd_24h numeric,
  outcome1_label text,
  outcome1_best_ask numeric,
  outcome1_best_bid numeric,
  outcome1_spread numeric,
  outcome1_last_price numeric,
  outcome1_liquidity numeric,
  outcome1_volume_usd_24h numeric,
  liquidity_usd numeric,
  open_interest_usd numeric,
  volume_usd_24h numeric,
  trades_24h numeric,
  competitive_score_24h numeric,
  trending_score_24h numeric,
  market_quality_score numeric,
  raw_json jsonb not null default '{}'::jsonb
);

create index idx_market_snapshots_market_ts on market_snapshots (market_id, ts desc);
create index idx_market_snapshots_ts on market_snapshots (ts desc);

create table model_signals (
  id uuid primary key,
  market_id uuid not null references prediction_markets(id),
  ts timestamptz not null,
  strategy_code text not null,
  action text not null,
  side text,
  model_probability numeric,
  executable_price numeric,
  edge numeric,
  confidence numeric,
  suggested_notional numeric,
  market_quality_score numeric,
  reason_codes text[] not null default '{}',
  risk_flags text[] not null default '{}',
  expires_at timestamptz,
  raw_json jsonb not null default '{}'::jsonb
);

create index idx_model_signals_ts on model_signals (ts desc);
create index idx_model_signals_market_ts on model_signals (market_id, ts desc);

create table paper_accounts (
  id uuid primary key,
  name text not null,
  starting_cash numeric not null,
  cash numeric not null,
  currency text not null default 'USDC',
  created_at timestamptz not null default now()
);

create table paper_orders (
  id uuid primary key,
  account_id uuid not null references paper_accounts(id),
  market_id uuid not null references prediction_markets(id),
  signal_id uuid references model_signals(id),
  side text not null,
  outcome_index int not null,
  order_type text not null default 'limit',
  limit_price numeric not null,
  quantity numeric not null,
  status text not null,
  reason text,
  created_at timestamptz not null default now(),
  filled_at timestamptz,
  cancelled_at timestamptz
);

create table paper_fills (
  id uuid primary key,
  order_id uuid not null references paper_orders(id),
  account_id uuid not null references paper_accounts(id),
  market_id uuid not null references prediction_markets(id),
  outcome_index int not null,
  side text not null,
  price numeric not null,
  quantity numeric not null,
  notional numeric not null,
  fee numeric not null default 0,
  snapshot_id bigint references market_snapshots(id),
  created_at timestamptz not null default now()
);

create table paper_positions (
  id uuid primary key,
  account_id uuid not null references paper_accounts(id),
  market_id uuid not null references prediction_markets(id),
  outcome_index int not null,
  quantity numeric not null,
  avg_price numeric not null,
  mark_price numeric,
  realized_pnl numeric not null default 0,
  unrealized_pnl numeric not null default 0,
  status text not null default 'open',
  updated_at timestamptz not null default now(),
  unique (account_id, market_id, outcome_index)
);

create table market_resolutions (
  id uuid primary key,
  market_id uuid not null references prediction_markets(id),
  resolved_outcome_index int,
  resolved_label text,
  status text not null,
  resolved_at timestamptz,
  source_url text,
  raw_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

---

## 9. 市场质量评分

### 9.1 评分目标

`market_quality_score` 用来回答：这个市场是否值得进入模型和纸面交易？

它不是交易信号本身。高质量市场不等于一定买入，只代表市场流动性、价差、规则清晰度和可建模性较好。

### 9.2 V1 评分公式

```text
market_quality_score =
  0.25 * liquidity_score
+ 0.20 * spread_score
+ 0.20 * resolution_clarity_score
+ 0.15 * modelability_score
+ 0.10 * time_score
+ 0.10 * activity_score
- risk_penalty
```

### 9.3 子分数定义

```python
def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def liquidity_score(liquidity_usd: float) -> float:
    # 1000 以下很差，10000 以上较好，50000 以上满分
    if liquidity_usd is None:
        return 0
    return clamp((liquidity_usd - 1000) / (50000 - 1000) * 100)


def spread_score(spread_ct: float) -> float:
    # spread 0.02 很好，0.10 以上很差
    if spread_ct is None:
        return 0
    return clamp((0.10 - spread_ct) / (0.10 - 0.02) * 100)


def activity_score(volume_usd_24h: float, trades_24h: float) -> float:
    volume_part = clamp((volume_usd_24h or 0) / 20000 * 100)
    trades_part = clamp((trades_24h or 0) / 200 * 100)
    return 0.7 * volume_part + 0.3 * trades_part
```

### 9.4 resolution_clarity_score

V1 先用规则打分：

| 条件 | 分数 |
|---|---:|
| 有明确 resolves_at、closes_at、venue_url | +30 |
| question 不含模糊词，如 “substantially”、“significant”、“major” | +20 |
| description 非空且长度 > 100 | +20 |
| 分类属于 crypto/economics/finance | +10 |
| 平台状态 OPEN 且 resolves_at 在合理范围 | +20 |

### 9.5 modelability_score

V1 先用解析器判断是否可模型化：

| 市场类型 | 分数 |
|---|---:|
| BTC/ETH/SOL 价格阈值，能解析资产、方向、阈值、时间 | 90 |
| CPI/FOMC/利率/失业率，能解析指标和日期 | 70 |
| Crypto 新闻事件，能解析实体但缺少定量数据 | 40 |
| 政治、体育、娱乐、描述模糊 | 10-30 |

### 9.6 进入纸面交易的硬门槛

```text
market_quality_score >= 65
liquidity_usd >= 1000
volume_usd_24h >= 500
spread_ct <= 0.08
status = OPEN
closes_at > now + 30 minutes
modelability_score >= 60
resolution_clarity_score >= 60
```

不满足硬门槛的市场只进入 radar，不生成自动纸面订单。

---

## 10. 策略与信号设计

### 10.1 信号数据结构

```json
{
  "market_id": "uuid",
  "strategy_code": "crypto_threshold_v1",
  "action": "BUY",
  "side": "YES",
  "model_probability": 0.67,
  "executable_price": 0.58,
  "edge": 0.09,
  "confidence": 0.72,
  "suggested_notional": 120.0,
  "market_quality_score": 78,
  "reason_codes": ["SPREAD_OK", "LIQUIDITY_OK", "MODEL_EDGE_POSITIVE"],
  "risk_flags": [],
  "expires_at": "2026-07-01T12:00:00Z"
}
```

### 10.2 action 枚举

```text
OBSERVE      只观察
BUY          买入某 outcome
EXIT         平仓/退出
HOLD         保持已有仓位
IGNORE       忽略，不展示为机会
```

### 10.3 side 枚举

```text
YES
NO
```

内部用 outcome_index 表示具体结果。对于二元市场：

```text
outcome0 通常显示为 YES 或第一个 outcome
outcome1 通常显示为 NO 或第二个 outcome
```

不要假设所有平台 outcome0 一定是 YES；必须保存 label 并做 normalize。

### 10.4 Crypto Threshold V1

#### 10.4.1 适用市场

```text
Will BTC be above $X on DATE?
Will ETH hit $X before DATE?
Will SOL close above $X this week?
```

#### 10.4.2 解析结果

```json
{
  "asset": "BTC",
  "condition_type": "close_above",
  "threshold": 80000,
  "deadline": "2026-07-31T23:59:59Z",
  "confidence": 0.86
}
```

#### 10.4.3 V1 模型

第一版用简单、可解释的概率模型，不追求复杂：

```text
输入：
- 当前价格 S0
- 阈值 K
- 到期时间 T，按年化
- 历史波动率 sigma
- 漂移 mu，V1 可设为 0 或用近 30 天动量估计

close_above 概率：
P(S_T > K) = 1 - NormalCDF((ln(K/S0) - (mu - 0.5*sigma^2)T) / (sigma*sqrt(T)))
```

V1 不确定时宁可不交易：

```text
解析置信度 < 0.75 → 不生成 BUY 信号
模型概率与市场价差 < 0.07 → 不生成 BUY 信号
市场质量分 < 65 → 不生成 BUY 信号
```

#### 10.4.4 BUY YES 规则

```text
p_model - yes_ask >= min_edge
confidence >= 0.65
market_quality_score >= 65
no critical risk flags
```

#### 10.4.5 BUY NO 规则

```text
(1 - p_model) - no_ask >= min_edge
confidence >= 0.65
market_quality_score >= 65
no critical risk flags
```

### 10.5 Macro Calendar V1

#### 10.5.1 适用市场

```text
Will the Fed cut rates at the next FOMC meeting?
Will CPI YoY be above X%?
Will unemployment rate be above X%?
```

#### 10.5.2 V1 处理方式

Macro 第一版建议先作为 radar + watchlist + 手工纸面交易，不建议一开始完全自动生成模型概率。原因是宏观数据需要可靠外部共识源、发布日期、修订规则和结算口径。

V1 可以实现：

```text
- 发现宏观市场
- 市场质量评分
- 价格变化提醒
- 手动创建纸面订单
- 后续 V1.1 加 macro_consensus.yaml 或第三方经济数据源
```

`macro_consensus.yaml` 示例：

```yaml
calendar:
  - event_code: fomc_2026_07
    date: "2026-07-29"
    source: manual
    model_probability:
      fed_cut_25bps_or_more: 0.42
      fed_hold: 0.55
      fed_hike: 0.03
  - event_code: cpi_2026_07
    date: "2026-07-15"
    source: manual
    consensus:
      cpi_yoy: 2.8
      core_cpi_yoy: 3.1
```

---

## 11. 纸面交易引擎

### 11.1 核心原则

1. 所有纸面订单必须基于当时数据库里的 market snapshot。
2. 买入用 ask，卖出用 bid，不允许用 last price 成交。
3. 每个订单要记录触发信号、当时价格、成交快照 ID。
4. 手动纸面订单和信号自动纸面订单都要支持。
5. 模拟要保守，不做“理想成交”。

### 11.2 纸面订单类型

V1 只做 limit order。

```text
BUY YES limit_price = 用户愿意支付的最高价格
SELL YES limit_price = 用户愿意接受的最低价格
BUY NO limit_price = 用户愿意支付的最高价格
SELL NO limit_price = 用户愿意接受的最低价格
```

### 11.3 成交规则

```python
def try_fill(order, snapshot):
    if order.side == "BUY" and order.outcome_index == 0:
        executable = snapshot.outcome0_best_ask
        can_fill = executable is not None and executable <= order.limit_price

    elif order.side == "SELL" and order.outcome_index == 0:
        executable = snapshot.outcome0_best_bid
        can_fill = executable is not None and executable >= order.limit_price

    elif order.side == "BUY" and order.outcome_index == 1:
        executable = snapshot.outcome1_best_ask
        can_fill = executable is not None and executable <= order.limit_price

    elif order.side == "SELL" and order.outcome_index == 1:
        executable = snapshot.outcome1_best_bid
        can_fill = executable is not None and executable >= order.limit_price

    if not can_fill:
        return None

    slippage = config.paper.slippage_bps / 10000
    fill_price = executable * (1 + slippage) if order.side == "BUY" else executable * (1 - slippage)
    return Fill(price=fill_price, quantity=order.quantity, snapshot_id=snapshot.id)
```

### 11.4 仓位与 PnL

#### 买入成本

```text
cost = fill_price * quantity + fee
cash -= cost
```

#### 卖出收入

```text
proceeds = fill_price * quantity - fee
cash += proceeds
realized_pnl += (fill_price - avg_price) * quantity - fee
```

#### 未实现盈亏

```text
unrealized_pnl = (mark_price - avg_price) * quantity
```

YES 持仓 mark_price 用 YES bid 或 mid：

```text
conservative_mark = yes_bid
mid_mark = (yes_bid + yes_ask) / 2
```

V1 默认用 conservative_mark。

### 11.5 到期结算

市场已结算后：

```text
winning outcome: payout = quantity * 1.0
losing outcome: payout = 0
realized_pnl = payout - avg_price * quantity - fees
position.status = closed
```

如果暂时无法确定结算结果，保留 `pending_resolution`。

### 11.6 风控规则

V1 写死硬规则：

```text
单笔最大名义金额 <= account_equity * 3%
单市场最大风险 <= account_equity * 5%
单分类最大风险 <= account_equity * 15%
每日亏损超过 3% → 当天禁止新开仓
market_quality_score < 65 → 禁止自动纸面下单
spread > 0.08 → 禁止自动纸面下单
expires_at < now + 30min → 禁止新开仓
```

---

## 12. 后端 API 设计

### 12.1 Auth

#### POST `/auth/login`

Request:

```json
{
  "username": "biaoge",
  "password": "your_password"
}
```

Response:

```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "expires_at": "2026-07-08T00:00:00+08:00",
  "user": {
    "username": "biaoge",
    "role": "admin"
  }
}
```

#### GET `/auth/me`

Response:

```json
{
  "username": "biaoge",
  "role": "admin"
}
```

### 12.2 Radar

#### GET `/radar/markets`

Query:

```text
category=crypto|economics|finance
protocol=POLYMARKET|KALSHI
q=btc
sort=quality|volume|liquidity|closingSoon|edge
minQuality=65
limit=50
offset=0
```

Response:

```json
{
  "items": [
    {
      "market_id": "uuid",
      "event_id": "uuid",
      "protocol": "POLYMARKET",
      "category": "crypto",
      "question": "Will Bitcoin be above $80,000 on July 31?",
      "status": "OPEN",
      "closes_at": "2026-07-31T23:59:59Z",
      "outcomes": [
        {"index": 0, "label": "Yes", "bid": 0.57, "ask": 0.59, "spread": 0.02},
        {"index": 1, "label": "No", "bid": 0.40, "ask": 0.42, "spread": 0.02}
      ],
      "liquidity_usd": 12000,
      "volume_usd_24h": 3500,
      "open_interest_usd": 20000,
      "market_quality_score": 81,
      "latest_signal": {
        "action": "BUY",
        "side": "YES",
        "edge": 0.09,
        "confidence": 0.72
      }
    }
  ],
  "total": 123
}
```

### 12.3 Market Detail

#### GET `/markets/{market_id}`

返回市场基础信息、当前快照、质量评分、最新信号、当前纸面持仓。

#### GET `/markets/{market_id}/bars`

Query:

```text
range=24h|7d|30d|all
resolution=min15|hour1|hour4|day1
```

Response:

```json
{
  "market_id": "uuid",
  "bars": [
    {
      "t": 1780000000,
      "yes": {"o": 0.52, "h": 0.57, "l": 0.50, "c": 0.55},
      "no": {"o": 0.48, "h": 0.50, "l": 0.43, "c": 0.45},
      "yes_bid": 0.54,
      "yes_ask": 0.56,
      "volume_usd": 1200,
      "open_interest_usd": 8000,
      "trades": 34
    }
  ]
}
```

### 12.4 Signals

#### GET `/signals`

Query:

```text
action=BUY
category=crypto
minEdge=0.07
limit=50
```

#### POST `/signals/{signal_id}/paper-order`

根据一个信号创建纸面订单。

Request:

```json
{
  "account_id": "uuid",
  "notional": 100,
  "limit_price": 0.58
}
```

### 12.5 Paper Trading

#### POST `/paper/orders`

手动创建纸面订单。

```json
{
  "account_id": "uuid",
  "market_id": "uuid",
  "side": "BUY",
  "outcome_index": 0,
  "limit_price": 0.58,
  "quantity": 100
}
```

#### GET `/paper/positions`

返回当前持仓。

#### GET `/paper/performance`

返回账户表现：

```json
{
  "equity": 10420,
  "cash": 8600,
  "unrealized_pnl": 220,
  "realized_pnl": 200,
  "win_rate": 0.56,
  "max_drawdown": -0.08,
  "total_trades": 45
}
```

---

## 13. iOS App 设计

### 13.1 页面结构

```text
/login
  登录页

/(tabs)/radar
  市场雷达列表

/(tabs)/signals
  交易信号列表

/(tabs)/portfolio
  纸面账户、持仓、PnL

/(tabs)/settings
  API 地址、刷新频率、退出登录

/market/[id]
  市场详情、图表、信号、纸面下单入口

/paper/new-order
  手动纸面下单
```

### 13.2 Expo Router 保护路由

App 启动时从 SecureStore 读取 token，调用 `/auth/me` 验证。如果未登录，跳转 `/login`。如果已登录，进入 tabs。

```tsx
// app/_layout.tsx
import { Stack } from "expo-router";
import { useAuthStore } from "../src/stores/authStore";

export default function RootLayout() {
  const { isLoggedIn } = useAuthStore();

  return (
    <Stack>
      <Stack.Protected guard={!isLoggedIn}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={isLoggedIn}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="market/[id]" />
        <Stack.Screen name="paper/new-order" />
      </Stack.Protected>
    </Stack>
  );
}
```

### 13.3 App API Client

```ts
// src/api/client.ts
import * as SecureStore from "expo-secure-store";

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL!;

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await SecureStore.getItemAsync("access_token");

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json();
}
```

### 13.4 登录逻辑

```ts
// src/api/auth.ts
import * as SecureStore from "expo-secure-store";
import { apiFetch } from "./client";

export async function login(username: string, password: string) {
  const data = await apiFetch<{
    access_token: string;
    expires_at: string;
  }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  await SecureStore.setItemAsync("access_token", data.access_token);
  return data;
}

export async function logout() {
  await SecureStore.deleteItemAsync("access_token");
}
```

### 13.5 主要组件

| 组件 | 用途 |
|---|---|
| `MarketCard` | 展示市场问题、价格、质量分、流动性、信号 |
| `SignalBadge` | BUY/EXIT/HOLD/OBSERVE 视觉标签 |
| `ProbabilityChart` | YES/NO 概率线图 |
| `PaperOrderSheet` | 从市场详情页创建纸面订单 |
| `PositionCard` | 展示纸面持仓和 PnL |
| `RiskFlags` | 展示低流动性、宽价差、结算模糊等风险 |

### 13.6 Radar 页交互

```text
顶部：分类 Tab：Crypto / Macro / Watchlist
筛选：平台、质量分、成交量、流动性、关闭时间
排序：Quality / Edge / Volume / Liquidity / Closing Soon
列表：MarketCard
下拉刷新：默认重新调用后端缓存接口；需要实时数据时手动刷新当前市场或 watchlist
点击卡片：进入 Market Detail
```

### 13.7 Market Detail 页

展示：

```text
- 问题标题
- 平台和分类
- YES/NO 当前 bid/ask
- 隐含概率
- 价差
- 流动性、24h 成交量、OI
- 市场质量分
- 最新信号
- 概率图表
- 风险 flags
- 创建纸面订单按钮
```

---

## 14. 后台任务设计

### 14.1 Worker 进程

V1 使用独立 worker 进程跑 APScheduler，不要把定时任务放在 FastAPI web 进程里，避免多实例重复执行。

```text
python -m app.workers.ingest
python -m app.workers.signal
python -m app.workers.paper_mark
```

### 14.2 任务表

```text
job_runs
- id
- job_name
- started_at
- finished_at
- status
- error_message
- records_processed
- codex_requests_used

api_usage_ledger
- id
- ts
- provider              # codex
- kind                  # discovery / hot_snapshot / warm_snapshot / bars / resolution / manual_refresh
- request_count
- status                # success / failed
- duration_ms
- job_run_id
- metadata_json         # 用于记录 query_name、market_count、fetch_profile 等
```

### 14.3 任务列表

任务配置使用可读的列表形式，避免 DOCX 表格过窄导致任务名换行不可读。

```text
refresh_categories
  默认频率：每天
  Codex 消耗：低
  动作：拉 Codex 分类树。

discover_events
  默认频率：30 分钟
  Codex 消耗：中
  动作：拉 Crypto/Macro OPEN events，分页受限。

sync_hot_markets
  默认频率：5 分钟
  Codex 消耗：中
  动作：拉 watchlist、纸面持仓、强信号市场。

sync_warm_markets
  默认频率：30 分钟
  Codex 消耗：中
  动作：拉高质量候选市场。

sync_cold_markets
  默认频率：6 小时
  Codex 消耗：低
  动作：低频检查冷市场是否升温。

compute_quality
  默认频率：5 分钟
  Codex 消耗：0
  动作：使用本地快照更新市场质量分。

compute_signals
  默认频率：5 分钟
  Codex 消耗：0
  动作：使用本地快照运行策略，生成信号。

try_fill_paper_orders
  默认频率：5 分钟
  Codex 消耗：0
  动作：用最新本地快照撮合纸面订单。

mark_positions
  默认频率：5 分钟
  Codex 消耗：0
  动作：更新纸面持仓 mark price 和 PnL，数据过旧时打 stale 标记。

poll_resolutions
  默认频率：2 小时
  Codex 消耗：低
  动作：检查结算状态，临近结算优先。

daily_budget_rollup
  默认频率：每天
  Codex 消耗：0
  动作：汇总 Codex 使用量，输出日报。
```

---

## 15. 安全设计

### 15.1 V1 最小安全要求

1. Codex API Key 只保存在后端 `.env`。
2. App 只保存 JWT，不保存 Codex key，不保存密码。
3. 配置文件密码使用 bcrypt hash，不提交真实配置文件。
4. 后端所有接口默认需要 JWT，只有 `/health` 和 `/auth/login` 例外。
5. JWT secret 至少 32 字节随机字符串。
6. Docker Compose 不对公网暴露 PostgreSQL。
7. 如部署到 VPS，FastAPI 前面加 Nginx + HTTPS。
8. V1 访问控制依赖 HTTPS、强密码和 JWT；业务层不做网络来源限制，以支持 iPhone 蜂窝网络、VPN 和其他动态出口。

### 15.2 配置文件账号密码生成

```bash
cd backend
python -m app.tools.hash_password
# 输入密码，输出 bcrypt hash
```

### 15.3 不要做的事

```text
不要把 CODEX_API_KEY 写进 mobile/.env
不要把密码写进 app.json extra
不要把 JWT_SECRET 提交到 Git
不要在 App 里直连数据库
不要在 App 里直连 Codex
```

---

## 16. 本地开发流程

### 16.1 启动后端依赖

```bash
docker compose up -d postgres redis
```

### 16.2 后端初始化

```bash
cd backend
uv sync
cp ../config/app.example.yaml ../config/app.yaml
cp ../.env.example ../.env
alembic upgrade head
python -m app.tools.seed_watchlist
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 16.3 启动 worker

```bash
cd backend
python -m app.workers.ingest
python -m app.workers.signal
python -m app.workers.paper_mark
```

### 16.4 启动移动端

```bash
cd mobile
npm install
cp .env.example .env
npx expo start
```

用 iPhone 上的 Expo Go 扫码打开。

### 16.5 iPhone 访问本地后端

`mobile/.env` 里不能写 `localhost`，要写电脑局域网 IP：

```bash
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.10:8000
```

后端启动时用：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 17. 测试策略

### 17.1 单元测试

| 模块 | 测试重点 |
|---|---|
| Codex Client | retry、timeout、错误响应 |
| Normalizer | outcome label、外部 ID、时间转换 |
| Quality Engine | 分数边界、缺失字段、极端 spread |
| Strategy | 解析失败不交易、edge 计算正确 |
| Paper Engine | 买卖成交价、现金变化、持仓均价、PnL |
| Auth | 密码校验、JWT 过期、非法 token |

### 17.2 集成测试

使用录制的 Codex 响应 fixture，不要每次测试都打真实 API。

```text
tests/fixtures/codex/events_crypto.json
tests/fixtures/codex/markets_btc.json
tests/fixtures/codex/market_bars_btc.json
```

### 17.3 纸面交易回放测试

给定一组 market snapshots：

```text
snapshot t1: YES bid/ask = 0.55/0.57
创建 BUY YES limit 0.58 qty 100
预期成交价 = 0.57 + slippage
现金减少
持仓增加

snapshot t2: YES bid/ask = 0.62/0.64
mark price = 0.62
unrealized_pnl 正确

snapshot t3: SELL YES limit 0.61
预期以 bid 0.62 - slippage 成交
realized_pnl 正确
```

### 17.4 App 测试

V1 可先手动测试，后续加：

```text
- 登录成功/失败
- token 失效后回登录页
- radar 筛选和排序
- 市场详情加载图表
- 创建纸面订单
- 查看持仓和 PnL
```

---

## 18. 部署方案

### 18.1 自用 VPS Docker Compose

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: radar
      POSTGRES_PASSWORD: radar
      POSTGRES_DB: radar
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"

  redis:
    image: redis:7
    ports:
      - "127.0.0.1:6379:6379"

  api:
    build: ./backend
    env_file: .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"

  worker-ingest:
    build: ./backend
    env_file: .env
    command: python -m app.workers.ingest
    depends_on:
      - postgres
      - redis

  worker-signal:
    build: ./backend
    env_file: .env
    command: python -m app.workers.signal
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
```

### 18.2 推荐部署拓扑

```text
家庭/个人网络：
  iPhone Expo Go → 局域网 FastAPI → Codex

VPS：
  iPhone Expo Go → HTTPS Nginx → FastAPI → Postgres/Redis → Codex
```

如果部署到公网，必须加 HTTPS 和强密码；V1 业务层不按客户端网络来源拦截请求。

---

## 19. 里程碑计划

### Milestone 0：项目骨架

验收标准：

```text
- monorepo 建立
- backend FastAPI 可启动
- mobile Expo 可启动
- Docker Compose 可启动 Postgres/Redis
- /health 返回 ok
- /auth/login 可用
```

### Milestone 1：Codex 数据落库

验收标准：

```text
- 能拉 predictionCategories 并落库
- 能拉 Crypto/Macro open events 并落库
- 能拉 event markets 并落库
- market_snapshots 有数据
- job_runs 可记录成功/失败
```

### Milestone 2：Radar API + App 列表

验收标准：

```text
- /radar/markets 支持 category/protocol/sort/filter
- App 登录后看到市场列表
- 市场卡片显示 bid/ask、spread、volume、quality score
- 下拉刷新正常
```

### Milestone 3：市场详情与图表

验收标准：

```text
- /markets/{id} 返回详情
- /markets/{id}/bars 返回概率线图数据
- App 市场详情能显示 YES/NO 概率曲线
- 能展示风险 flags 和质量分解释
```

### Milestone 4：质量评分与信号

验收标准：

```text
- quality engine 自动更新 score
- crypto_threshold_v1 可解析部分 BTC/ETH/SOL 市场
- /signals 返回 BUY/OBSERVE/IGNORE 信号
- App signals 页可查看信号和理由
```

### Milestone 5：纸面交易

验收标准：

```text
- 可从信号创建纸面订单
- 可手动创建纸面订单
- worker 根据最新快照模拟成交
- positions、fills、performance 正常
- App portfolio 显示现金、持仓、PnL
```

### Milestone 6：复盘报表

验收标准：

```text
- 按策略统计胜率、平均 edge、PnL、最大回撤
- 按分类统计 Crypto/Macro 表现
- 能导出 CSV
- 能查看每笔订单当时的 signal 和 snapshot
```

---

## 20. V1 开发顺序建议

最短路径：

```text
1. 后端 auth + config
2. Codex client + GraphQL queries
3. 数据库 schema + Alembic
4. ingestion worker 落 events/markets/snapshots
5. /radar/markets API
6. Expo 登录 + Radar 列表
7. Market Detail + bars
8. market_quality_score
9. paper account/order/fill/position
10. crypto_threshold_v1 信号
11. App signals + paper order
12. performance 统计
```

不要先写复杂策略。先把数据闭环和纸面交易闭环打通。

---

## 21. 未来扩展预留

### 21.1 真实交易执行接口

V1 不实现真实交易，但接口先预留：

```python
class ExecutionAdapter(Protocol):
    venue_code: str

    async def place_limit_order(self, order: LiveOrderRequest) -> LiveOrderResult:
        ...

    async def cancel_order(self, external_order_id: str) -> None:
        ...

    async def get_open_orders(self) -> list[LiveOrder]:
        ...

    async def get_balances(self) -> list[VenueBalance]:
        ...
```

未来可以实现：

```text
PolymarketExecutionAdapter
KalshiExecutionAdapter
```

### 21.2 更多市场分类

新增分类只需要做三件事：

```text
1. categories.example.yaml 里加分类和关键词
2. 新增 strategy plugin 或只做 radar
3. App filter 显示该分类
```

候选扩展分类：

```text
- Technology / AI
- Regulation
- Company / Earnings
- Weather
- Energy
```

### 21.3 更多数据源

未来可接：

```text
- 交易所现货/永续价格
- 期权隐含波动率
- 宏观日历和经济学家共识
- 新闻/公告 RSS
- 链上大额转账
- 钱包/巨鲸行为
```

---

## 22. 官方资料依据

以下资料用于本方案的工程约束判断：

1. Codex GraphQL API：官方文档说明通过 `Authorization` header 调用 `https://graph.codex.io/graphql`，并支持 HTTPS queries 与 WSS subscriptions。
2. Codex Discover Prediction Markets：官方 recipe 说明使用 `predictionCategories`、`filterPredictionEvents`、`filterPredictionMarkets` 构建预测市场发现页，并说明 `bestAskCT` 可作为稳定币抵押市场的隐含概率、`spreadCT = bestAskCT - bestBidCT`。
3. Codex Prediction Charts：官方 recipe 说明 `predictionMarketBars`、`predictionEventBars`、`predictionEventTopMarketsBars` 可用于预测市场图表，支持 min1 到 week1 等分辨率。
4. Codex Pricing：Codex 网站显示 Growth 计划为 350 美元/月、1,000,000 requests/month；请求、webhook、websocket 推送都计为 request。本项目不能按独享 1,000,000 requests/month 设计，V1 默认只占用其中一小部分。
5. Expo Environment Variables：官方文档说明 `EXPO_PUBLIC_` 变量会被内联到客户端 bundle，并明确不要存放敏感信息。
6. Expo Router Protected Routes：官方文档说明可用 `Stack.Protected` 根据登录状态保护路由。
7. Expo SecureStore：官方文档说明 `expo-secure-store` 可在设备上加密保存小型 key-value，且包含在 Expo Go 中；但 Expo Go 中生物认证相关 `requireAuthentication` 有限制。
8. Expo Go / Development Builds：官方文档说明 Expo Go 适合快速体验和固定 native SDK 能力；需要自定义原生库或 native 配置时应迁移 development build。

---

## 23. 最终 V1 验收清单

系统达到 V1 完成时，应满足：

```text
[ ] iPhone 使用 Expo Go 可以登录系统
[ ] 后端配置文件账号密码登录可用
[ ] Codex API Key 不出现在移动端代码或 bundle 中
[ ] Crypto/Macro 市场能定时落库
[ ] Radar 页能按质量分、成交量、流动性、关闭时间排序
[ ] Market Detail 能查看价格、价差、流动性、图表
[ ] market_quality_score 可解释
[ ] crypto_threshold_v1 至少能对部分 BTC/ETH 阈值市场生成信号
[ ] 可创建手动纸面订单
[ ] 可从信号创建纸面订单
[ ] 纸面订单用 bid/ask 保守成交
[ ] 持仓、现金、PnL、胜率、回撤可查看
[ ] 每笔交易能追溯到 signal、snapshot 和当时价格
[ ] 每日 API 请求量有日志或统计
[ ] 系统部署文档可复现
```

---

## 24. 下一步可以直接开工的任务拆分

### Backend Task 1：项目初始化

```text
- 创建 FastAPI 项目
- 加载 .env 和 app.yaml
- structlog 日志
- /health
- Dockerfile
- docker-compose postgres/redis
```

### Backend Task 2：Auth

```text
- bcrypt password verify
- JWT create/verify
- POST /auth/login
- GET /auth/me
- auth dependency
```

### Backend Task 3A：Codex Usage Logging + Fetch Profile

目标：不用代码层卡预算，但要让 Codex 用量可见、可复盘、可配置。

Checklist：

```text
[ ] 所有 Codex 调用统一走 CodexClient 封装，便于日志、retry、timeout
[ ] 建 `api_usage_ledger` 表并记录 success / failed / duration_ms / kind
[ ] 实现 daily / monthly usage 查询接口或后台日志
[ ] 实现 fetch_profile 配置：light / normal / aggressive
[ ] App API 返回 freshness，并可选返回 codex_usage_hint
[ ] 后续额度提高时，只需要调 job 频率、watchlist 数量和 fetch_profile
```

### Backend Task 3：Codex Client

```text
- GraphQL POST client
- retry + timeout
- query: predictionCategories
- query: filterPredictionEvents
- query: filterPredictionMarkets
- query: predictionMarketBars
```

### Backend Task 4：DB + Ingestion

```text
- SQLAlchemy models
- Alembic migration
- normalize events/markets/outcomes
- upsert events/markets
- insert market_snapshots
```

### Mobile Task 1：Expo 项目初始化

```text
- create-expo-app
- Expo Router
- TanStack Query
- Zustand
- SecureStore
- API client
```

### Mobile Task 2：登录和路由保护

```text
- login screen
- SecureStore token
- /auth/me bootstrap
- Stack.Protected
```

### Mobile Task 3：Radar

```text
- filter store
- useRadarMarkets query
- MarketCard
- sorting/filtering UI
- pull to refresh
```

### Trading Task 1：Paper Engine

```text
- paper_accounts
- paper_orders
- paper_fills
- paper_positions
- create order
- try fill by latest snapshot
- mark positions
- performance endpoint
```

### Strategy Task 1：Quality + Crypto Threshold

```text
- market_quality_score
- rule-based market parser
- simple probability model
- signal generation
- risk flags
```
