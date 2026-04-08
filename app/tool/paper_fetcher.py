import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from app.tool.base import BaseTool, ToolResult


class PaperFetcherTool(BaseTool):
    name: str = "paper_fetcher"
    description: str = """
    搜索并提取学术论文的标题、摘要、作者和链接。
    当用户需要了解某个研究领域的最新论文、学术进展时使用此工具。
    支持搜索 AI、机器学习、大模型等各类学术主题。
    输入关键词，返回结构化的论文信息列表。
    适用场景：论文检索
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，例如：'large language model' 或 'RAG retrieval'"
            },
            "max_results": {
                "type": "integer",
                "description": "最多返回论文数量，默认5篇",
                "default": 5
            },
            "sort_by": {
                "type": "string",
                "description": "排序方式：lastUpdatedDate（最新）或 relevance（相关性）",
                "default": "lastUpdatedDate"
            }
        },
        "required": ["keyword"]
    }

    async def execute(
        self,
        keyword: str,
        max_results: int = 5,
        sort_by: str = "lastUpdatedDate"
    ) -> ToolResult:
        try:
            papers = await self._search_arxiv(keyword, max_results, sort_by)
            if not papers:
                return ToolResult(output=f"未找到关于「{keyword}」的相关论文")

            output = f"关键词「{keyword}」相关论文（共{len(papers)}篇）：\n\n"
            for i, p in enumerate(papers, 1):
                output += f"{'='*50}\n"
                output += f"[{i}] {p['title']}\n"
                output += f"作者：{p['authors']}\n"
                output += f"发布：{p['published']} | 分类：{p['category']}\n"
                output += f"摘要：{p['summary']}\n"
                output += f"链接：{p['url']}\n\n"

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(error=f"论文搜索失败：{str(e)}")

    async def _search_arxiv(
        self,
        keyword: str,
        max_results: int,
        sort_by: str
    ) -> list:
        # arXiv API 查询策略：
        # 1. 分别搜索多个相关短语（"RAG", "Retrieval-Augmented Generation", 原始关键词）
        # 2. 对每个结果做相关性预过滤（标题/摘要必须包含强相关词）
        # 3. 合并去重后返回

        # 识别核心相关词（必须有较高权重才视为相关）
        strong_terms = ["RAG", "Retrieval-Augmented", "Retrieval Augment",
                        "retrieval augment", "augmented generation", "generation augment"]
        weak_terms = ["retrieval", "generation", "large language model", "LLM"]

        def is_relevant(title: str, abstract: str) -> bool:
            title_lower = title.lower()
            abstract_lower = abstract.lower()
            text = title_lower + " " + abstract_lower

            # 必须包含至少一个强相关词
            has_strong = any(st.lower() in text for st in strong_terms)
            if not has_strong:
                return False

            # 如果有强相关词，同时排除明显无关领域
            # 数学、物理、化学类关键词作为辅助判断
            irrelevant_categories = [
                "hep-ph", "math.CO", "math.OC", "cond-mat", "quant-ph",
                "nucl-th", "hep-th", "astro-ph"
            ]

            return True

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        all_entries = []

        # 构建多个搜索查询，优先用 abs: 字段
        queries = []

        # 精确短语形式（用引号包住）
        if keyword.strip():
            queries.append(f'"{keyword}"')
            queries.append(keyword)

        # 额外补充常见的 RAG 表达方式
        extra_phrases = ["RAG", "retrieval-augmented-generation", "Retrieval Augmented Generation"]
        for phrase in extra_phrases:
            if phrase.lower() not in keyword.lower():
                queries.append(phrase)

        seen_ids = set()
        for query in queries:
            if len(all_entries) >= max_results * 3:  # 已有足够候选就停止
                break
            encoded = urllib.parse.quote(query)
            url = (
                f"https://export.arxiv.org/api/query"
                f"?search_query=all:{encoded}"
                f"&start=0"
                f"&max_results={max_results}"
                f"&sortBy={sort_by}"
                f"&sortOrder=descending"
            )
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for entry in root.findall("atom:entry", ns):
                    entry_id = entry.findtext("atom:id", "", ns)
                    if entry_id and entry_id not in seen_ids:
                        seen_ids.add(entry_id)
                        all_entries.append(entry)
            except Exception:
                pass  # 单个查询失败不影响其他查询

        # 相关性过滤 + 分类过滤
        filtered_entries = []
        for entry in all_entries:
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")

            # 获取分类
            category = entry.find("atom:category", ns)
            cat_str = category.get("term", "") if category is not None else ""

            # 排除 CS/AI/IR/LG 以外的分类（物理、数学等）
            cs_related = cat_str.startswith("cs.") or cat_str in ("q-fin", "q-bio", "stat.ML", "eess.SY")
            if not cs_related:
                # 但如果标题/摘要强相关，保留（有些好论文分类不准）
                title_abs = title.lower() + " " + summary.lower()
                has_rag_mention = any(st.lower() in title_abs for st in strong_terms)
                if not has_rag_mention:
                    continue

            if is_relevant(title, summary):
                filtered_entries.append(entry)

            if len(filtered_entries) >= max_results:
                break

        # 如果过滤后不足，回退：取 CS 相关结果中相关性最高的
        if len(filtered_entries) < max_results:
            for entry in all_entries:
                if entry in filtered_entries:
                    continue
                title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
                summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
                if is_relevant(title, summary):
                    filtered_entries.append(entry)
                if len(filtered_entries) >= max_results:
                    break

        papers = []
        for entry in filtered_entries:
            # 标题
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")

            # 摘要（截取前200字）
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
            summary = summary[:200] + "..." if len(summary) > 200 else summary

            # 作者（最多3位）
            authors = [
                a.findtext("atom:name", "", ns)
                for a in entry.findall("atom:author", ns)
            ]
            authors_str = "、".join(authors[:3])
            if len(authors) > 3:
                authors_str += f" 等{len(authors)}人"

            # 发布时间
            published = entry.findtext("atom:published", "", ns)[:10]

            # 论文链接
            url_link = ""
            for link in entry.findall("atom:link", ns):
                if link.get("type") == "text/html":
                    url_link = link.get("href", "")
                    break

            # 分类
            category = entry.find("atom:category", ns)
            cat_str = category.get("term", "") if category is not None else ""

            papers.append({
                "title": title,
                "summary": summary,
                "authors": authors_str,
                "published": published,
                "url": url_link,
                "category": cat_str
            })

        return papers