# OpenManus-Deploy

> 基于 [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus) 开源项目定制开发的 AI 信息采集与自动化工具站点。

## 项目起源

本项目基于 MetaGPT 团队开发的 [OpenManus](https://github.com/FoundationAgents/OpenManus)（MIT License）开源项目进行定制开发。OpenManus 是一个通用的 AI Agent 框架，能够在 3 小时内完成构建并持续迭代，支持浏览器自动化、文件操作、代码执行等多种工具调用能力。

## 本项目改进内容

在原始 OpenManus 框架基础上，本项目进行了以下定制化开发：

### 1. 定制工具链：信息采集与爬取

- **爬虫工具集成**：基于 httpx + BeautifulSoup 封装了新闻采集工具（NewsScraperTool），支持 Bing News 搜索，可按关键词抓取最新资讯、摘要与来源链接
- **搜索工具扩展**：集成多搜索引擎（Google / DuckDuckGo / Baidu / Bing）的网页搜索能力，支持自动降级与多语言结果

### 2. Prompt 工程优化

- 针对信息采集场景优化 Agent 提示词，提升任务拆解能力
- 设计意图分类 Prompt，引导 Agent 自主选择合适的工具组合
- 动态注入浏览器上下文，增强多轮对话状态感知

### 3. 交互接口与网站部署

- 接入 DeepSeek Chat API 作为后端大模型，降低部署成本
- 基于 OpenManus Agent 构建 AI 信息采集工具网站，用户输入关键词即可自动完成：搜索 → 抓取 → 整理全流程
- 支持实时任务状态展示与结果导出

### 4. 环境配置与工程化

- 完善 config.toml 配置管理，支持多模型切换（DeepSeek / GPT-4o / Claude 等）
- Docker 化部署支持，开箱即用
- 完整日志记录，便于问题排查与效果分析

## 技术栈

| 类别 | 技术 |
|------|------|
| Agent 框架 | OpenManus（基于 MetaGPT） |
| 后端模型 | DeepSeek Chat / GPT-4o / Claude |
| 浏览器自动化 | Playwright（CDP 协议） |
| 网页爬取 | httpx + BeautifulSoup |
| 异步框架 | asyncio |
| 部署 | Docker / Python 3.12 |

## 快速开始

### 1. 克隆本仓库

```bash
git clone https://github.com/yumengzou223/OpenManus-Deploy.git
cd OpenManus-Deploy
```

### 2. 配置 API Key

```bash
cp config/config.example.toml config/config.toml
# 编辑 config.toml，填入你的 API Key
```

推荐使用 DeepSeek API（性价比高）：

```toml
[llm]
model = "deepseek-chat"
base_url = "https://api.deepseek.com/v1"
api_key = "your-deepseek-api-key"
```

### 3. 安装依赖并运行

```bash
pip install -r requirements.txt
python main.py
```

### 4. 可选：启用浏览器自动化

```bash
playwright install
```

## 项目结构

```
OpenManus-Deploy/
├── app/
│   ├── agent/          # Agent 核心（Manus / ToolCallAgent / ReActAgent）
│   ├── tool/           # 工具实现（浏览器/文件/Python/爬虫/搜索）
│   ├── prompt/         # Prompt 模板
│   ├── llm.py          # LLM 调用封装
│   └── config.py       # 配置管理
├── config/             # 配置文件
├── main.py             # 入口
└── run_flow.py         # 多 Agent 工作流（可选）
```

## 主要工具一览

| 工具名 | 功能 |
|--------|------|
| python_execute | 安全执行 Python 代码 |
| browser_use_tool | 浏览器自动化操作 |
| str_replace_editor | 文件查看 / 创建 / 编辑 |
| news_scraper | Bing News 关键词新闻采集 |
| web_search | 多引擎网页搜索 |
| crawl4ai | AI 驱动的网页内容抓取 |
| Terminate | 结束任务 |

## 致谢

- 感谢 [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus) 团队提供开源的 Agent 框架
- 感谢 [MetaGPT](https://github.com/geekan/MetaGPT) 社区的贡献
- 感谢 [Anthropic](https://www.anthropic.com) 的 Claude 系列模型支持

## License

MIT License - 继承自 OpenManus 原始项目许可

---

*本项目仅供学习与研究使用，如需商业应用请参考原始 OpenManus 项目许可。*
