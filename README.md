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

```bash
git clone https://github.com/yumengzou223/OpenManus-Deploy.git
cd OpenManus-Deploy
cp config/config.example.toml config/config.toml
# 编辑 config.toml，填入你的 API Key
pip install -r requirements.txt
python main.py
```

## 致谢

- 感谢 [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus) 团队提供开源的 Agent 框架
- 感谢 [MetaGPT](https://github.com/geekan/MetaGPT) 社区的贡献

## License

MIT License - 继承自 OpenManus 原始项目许可
