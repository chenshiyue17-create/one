<p align="center">
  <a href="https://github.com/cv-cat/XHS_ALL_IN_ONE" target="_blank">
    <picture>
      <img width="220" src="./author/logo.jpg" alt="XHS_ALL_IN_ONE logo">
    </picture>
  </a>
</p>

<div align="center">

# XHS_ALL_IN_ONE

**小红书一站式智能运营平台 — 采集、分析、AI 创作、自动发布，全链路闭环**

[![Skills](https://img.shields.io/badge/skills-supported-success)](https://github.com/cv-cat/XhsSkills)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/nodejs-20%2B-green)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

</div>

> 市面上的小红书工具要么只能爬数据，要么只能发笔记，要么需要手动复制粘贴到 AI 平台再贴回来。
> **XHS_ALL_IN_ONE 是第一个把「采集 → 内容库 → AI 改写 → 图片润色 → 一键发布 → 定时自动运营」全链路打通的开源平台。**
> 一个浏览器标签页，完成别人用 5 个工具才能做的事。

**⚠️ 本项目仅供学习交流使用，禁止任何商业化行为，如有违反，后果自负**

---

## 核心优势

| | 传统方案 | XHS_ALL_IN_ONE |
|---|---|---|
| **数据采集** | 写脚本 / 用第三方爬虫 | 平台内搜索 + 一键入库，素材自动下载到本地 |
| **内容管理** | Excel / 文件夹 / 各种笔记软件 | 统一内容库，标签筛选，卡片预览 |
| **AI 改写** | 复制到 ChatGPT → 手动粘贴回来 | 编辑器内一键改写，标题/正文/标签全覆盖 |
| **图片处理** | Photoshop / 在线工具 | AI 图片润色 + 参考图，原位替换 |
| **发布** | 手动打开创作者平台上传 | 选账号 → 点发布，支持定时 |
| **自动化** | 没有 / 需要写代码 | 配置关键词 + 频率，全自动：搜索→改写→发布 |
| **多账号** | 反复切换浏览器 | 账号矩阵统一管理，2h 自动健康巡检 |

---

## 平台预览

### 账号矩阵 — 多账号绑定与健康管理

支持绑定多个 PC / Creator 账号，扫码登录、手机验证码、Cookie 导入三种方式。Cookie 加密存储，2 小时自动健康巡检，过期自动通知。

<img src="./static/frontend_1.jpg" width="600" />

### 笔记发现 — 关键词搜索与详情预览

输入关键词一键搜索小红书全站笔记，支持排序、类型、时间等多维筛选。点击笔记卡片打开详情抽屉，查看无水印原图、互动数据、评论区，一键保存到内容库。

<img src="./static/frontend_2.jpg" width="600" />

### 内容库 — 采集内容的统一管理

所有采集到的笔记统一沉淀在内容库，属于平台用户而非某个 XHS 账号。卡片/列表双视图，支持自定义标签、关键词搜索、批量操作、JSON/CSV 导出。

<img src="./static/frontend_3.jpg" width="600" />

### 草稿工坊 — AI 改写与内容编辑

三栏布局：草稿队列 + 编辑器 + AI 助手。从内容库深拷贝笔记进入草稿，AI 一键改写正文、润色标题、生成标签，拖拽排序图片素材，编辑完成直接送入发布中心。

<img src="./static/frontend_4.jpg" width="600" />

### 素材优化 — AI 图片润色

选择草稿中的任意图片，添加参考图，输入润色指令，AI 生成优化后的图片并原位替换。当前素材和优化结果并排对比，点击即可放大预览。

<img src="./static/frontend_5.jpg" width="600" />

### 发布中心 — 一键发布到小红书

预览草稿内容和图片素材，选择 Creator 账号，设置可见性和发布模式（立即/定时），发布校验通过后一键发布到小红书创作者平台。

<img src="./static/frontend_6.jpg" width="600" />

### 自动运营 — 全自动内容生产管线

设置关键词和调度频率（每日/每周/自定义间隔），系统自动执行完整管线：搜索热门笔记 → AI 改写标题+正文 → 上传图片素材 → 通过 Creator API 自动发布。真正的无人值守。

<img src="./static/frontend_7.jpg" width="600" />

---

## ⭐ 完整功能清单

### 底层 SDK（逆向签名算法，透明封装）

| 模块 | 功能 | 状态 |
|------|------|------|
| **小红书 PC 端** | 二维码登录 / 手机验证码登录 | ✅ |
| | 搜索笔记 & 搜索用户 | ✅ |
| | 获取笔记详情（无水印图片 & 视频） | ✅ |
| | 获取笔记评论 | ✅ |
| | 获取用户发布 / 喜欢 / 收藏的笔记 | ✅ |
| | 获取用户主页信息 / 自己的账号信息 | ✅ |
| | 获取主页推荐 / 未读消息 | ✅ |
| **创作者平台** | 二维码登录 / 手机验证码登录 | ✅ |
| | 上传图集 / 视频作品 | ✅ |
| | 查看已发布作品列表 | ✅ |
| **蒲公英平台** | KOL 博主列表 & 粉丝画像 & 合作邀请 | ✅ |
| **千帆平台** | 分销商列表 & 合作品类 / 商品信息 | ✅ |

### Web 运营平台

| 模块 | 功能 |
|------|------|
| **账号矩阵** | 多 PC / Creator 账号绑定、Cookie 加密存储、2h 自动健康巡检、过期通知 |
| **笔记发现** | 关键词搜索、URL 直查、多维筛选、已保存标记、一键入库 |
| **数据抓取** | 批量 URL / 搜索 / 评论抓取、Excel 导出、素材本地下载 |
| **内容库** | 卡片/列表双视图、自定义标签、批量操作、JSON/CSV 导出、查看原文 |
| **草稿工坊** | 三栏编辑器、AI 改写正文、润色标题/标签、拖拽排序素材、AI 图片润色 |
| **图片工坊** | AI 图片生成（支持参考图）、图片描述、AI/普通图片资产管理 |
| **发布中心** | 图集发布、定时发布、发布校验、状态追踪、重试/取消 |
| **自动运营** | 定时任务（每日/每周/自定义间隔）、全自动管线：搜索→AI改写→上传→发布 |
| **数据洞察** | 仪表盘总览、互动趋势、Top 内容、热门话题、评论分析 |
| **竞品监控** | 关键词/账号/品牌/URL 监控、自动爬取刷新、快照历史 |
| **任务中心** | 全量任务审计、调度器状态、耗时追踪 |
| **通知系统** | Cookie 过期 / 任务失败自动通知、铃铛实时展示 |
| **模型配置** | 支持任意 OpenAI 兼容 API（火山引擎、阿里云百炼、OpenAI 中转等） |

### 平台扩展（规划中）

| 平台 | 状态 |
|------|------|
| 小红书 (XHS) | ✅ 已实现 |
| 抖音 (Douyin) | Coming Soon |
| 快手 (Kuaishou) | Coming Soon |
| 微博 (Weibo) | Coming Soon |
| 闲鱼 (Xianyu) | Coming Soon |
| 淘宝 (Taobao) | Coming Soon |

---

## 🧩 Skills 支持

当前项目已支持基于 skills 的能力接入，可直接作为底层能力仓库使用，也可通过标准化 skills 方式被上层 Agent 工具链引入。

封装好的 skills 请查看 [XhsSkills](https://github.com/cv-cat/XhsSkills)，可被 `Clawbot`、`Claude Code`、`Codex` 等工具直接引入与集成。

---

## 🛠️ 快速开始

### 环境要求

- Python 3.10+
- Node.js 20+

### 安装依赖

```bash
git clone https://github.com/cv-cat/XHS_ALL_IN_ONE.git
cd XHS_ALL_IN_ONE

pip install -r requirements.txt
npm install
cd frontend && npm install && cd ..
```

### 启动项目

```bash
# 一键启动（后端 + 前端）
python main.py --with-frontend
```

启动后访问：
- 前端: http://localhost:5173
- API 文档: http://localhost:8000/docs

首次启动自动创建数据库，注册账号即可使用。

### 服务器运营版

生产环境可直接访问：

- Web: http://47.87.68.74/spider-xhs/
- 健康检查: http://47.87.68.74/spider-xhs/api/health
- 状态接口: http://47.87.68.74/spider-xhs/api/system/status

服务器默认由 systemd 管理 `one-xhs` 服务，后端直接用 conda 环境启动 Uvicorn，并由后端托管 `frontend/dist`：

```bash
sudo systemctl status one-xhs --no-pager
sudo journalctl -u one-xhs -n 200 --no-pager
curl http://127.0.0.1:8000/api/system/status
```

部署时需要固定：

```bash
FRONTEND_SERVE_STATIC=true
FRONTEND_BUILD_DIR=/home/ecs-assist-user/one/frontend/dist
VITE_APP_BASE=/spider-xhs/
```

### 本地登录助手

服务器网页无法直接读取你电脑上的浏览器 Cookie。本项目提供了本地登录助手，用于安全地从本机浏览器同步登录状态。

**注意：** 如果你使用 `./start.sh` 或 `python main.py` 启动项目，**本地助手会自动在后台启动**，无需手动运行。

如果你需要单独运行或在其他机器上运行：

```bash
chmod +x ./start-local-helper.sh
./start-local-helper.sh
```

在 macOS 上也可以直接双击：

```bash
./打开小红书工作台.command
```

它会先检查并拉起本地登录助手，确认 `127.0.0.1:8765/health` 成功后，再自动打开本地同步工作台：`http://127.0.0.1:8765/`。

当前唯一桌面入口：

- `~/Desktop/XHS工作台.app`

该入口统一指向 `/Users/cc/XHS_ALL_IN_ONE`，启动后会自动拉起本地助手并打开当前正确工作台。旧的 `.command` / `.app` 入口会自动归档到 `~/Desktop/_XHS旧入口归档`，避免版本混乱。

推荐使用新的本地闭环：

1. 在本地工作台里登录服务器账号
2. 点击「检测助手」
3. 点击「读取 Cookie」
4. 点击「同步到服务器」
5. 自动跳转服务器账号页查看结果

这样本地授权和 Cookie 读取都在 `127.0.0.1` 页面内完成，不再依赖服务器网页直接访问本机回环地址。

助手接口只监听 `127.0.0.1:8765`，Cookie 上传必须由用户点击触发，不会后台自动上传。

### 运维中心

访问 `/ops` 可查看服务状态、Nginx 检查、前端构建状态和日志。写操作只允许白名单：

- 重启 `one-xhs`
- 重载 Nginx
- 重新构建前端
- 重新运行部署检查

高危操作必须二次确认，并在页面输入 `SYSTEM_OPS_TOKEN`。未设置 token 时接口返回禁用状态。

### Docker 部署

```bash
docker compose up -d
```

---

## 📁 项目结构

```
XHS_ALL_IN_ONE/
├── main.py                         # 统一启动入口
├── config/                         # YAML 配置（default / production）
├── apis/                           # XHS 底层 SDK（逆向签名 + HTTP 接口）
├── xhs_utils/                      # 签名算法封装
├── static/                         # 签名核心 JS 文件
├── backend/
│   └── app/
│       ├── main.py                 # FastAPI 应用
│       ├── core/                   # 配置、数据库、安全、时区
│       ├── models/                 # SQLAlchemy 数据模型（20+ 张表）
│       ├── api/                    # API 路由
│       ├── services/               # 业务逻辑 + 定时调度
│       ├── adapters/xhs/           # XHS SDK 适配层
│       └── storage/                # 媒体文件 + 导出文件
├── frontend/
│   └── src/
│       ├── pages/platforms/xhs/    # 各功能页面
│       ├── components/layout/      # 侧边栏 + 通知系统
│       ├── lib/api.ts              # HTTP 客户端
│       └── types/                  # TypeScript 类型
├── tests/                          # 后端测试（126 passed）
├── Dockerfile                      # 多阶段构建
└── docker-compose.yml              # 编排文件
```

---

## ⚙️ 配置说明

分层配置，优先级：`config/default.yaml` < `CONFIG_FILE` < `.env` < 环境变量

```yaml
database:
  type: "sqlite"                    # sqlite 或 mysql
security:
  secret_key: "change-me"          # JWT 签名密钥
scheduler:
  enabled: false                    # 启用定时任务（自动运营/监控/Cookie巡检）
```

主要环境变量：`SECRET_KEY`、`DATABASE_TYPE`、`DATABASE_URL`、`SCHEDULER_ENABLED`、`SYSTEM_OPS_TOKEN`

### 常见故障

- 页面打不开：先查 `curl http://127.0.0.1:8000/api/health`，再查 `sudo systemctl status one-xhs --no-pager`。
- `/spider-xhs/` 白屏：确认前端用 `VITE_APP_BASE=/spider-xhs/ npm run build` 构建，且 `frontend/dist/index.html` 存在。
- 本地登录同步失败：优先使用 `./start-unified-workbench.sh`、`./打开小红书工作台.command` 或桌面 `XHS工作台.app` 打开本地工作台；确认浏览器已登录小红书，再执行读取和同步。

### 单入口整理

如需手动重建桌面唯一入口：

```bash
./start-unified-workbench.sh
```

它会执行三件事：

1. 归档旧的 XHS 桌面启动器
2. 重建唯一桌面入口 `XHS工作台.app`
3. 自动打开当前正确的本地工作台页面
- 运维操作 403：确认服务环境变量里配置了 `SYSTEM_OPS_TOKEN`，页面输入值一致。
- 前端构建失败：查看 `/tmp/xhs-frontend-rebuild.log` 或 `/tmp/xhs-*.log`。

---

## 🗝️ 注意事项

- `apis/` 是底层 SDK 层，**请勿直接修改**，上层通过 `backend/app/adapters/` 中转调用
- Cookie 有时效性，平台内置 2 小时自动健康巡检 + 过期通知
- 所有敏感数据（Cookie、API Key）使用 Fernet 加密存储
- AI 功能需在「模型配置」页面配置 OpenAI 兼容的 API 端点（支持火山引擎、阿里云百炼等）

---

## 🧸 额外说明

1. 感谢 Star ⭐ 和 Follow，项目会持续更新
2. 作者联系方式在主页，有问题随时联系
3. 欢迎 PR 和 Issue，也欢迎关注作者其他项目

<div align="center">
</div>

---

## 📈 Star History

<a href="https://www.star-history.com/#cv-cat/XHS_ALL_IN_ONE&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=cv-cat/XHS_ALL_IN_ONE&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=cv-cat/XHS_ALL_IN_ONE&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=cv-cat/XHS_ALL_IN_ONE&type=Date" />
  </picture>
</a>

---

## 🍔 交流群

如果你对爬虫和 AI Agent 感兴趣，请加作者主页 wx 通过邀请加入群聊

ps: 请加群13、14，人满或者过期 issue | wx 提醒

![group13](https://github.com/user-attachments/assets/cc06a36f-7abf-4646-a4a3-c2c841a77a88)

![group14](https://github.com/user-attachments/assets/7c73f29e-0c46-4708-81a5-cc8527023de2)

---

## License

MIT License - see [LICENSE](LICENSE) for details.
