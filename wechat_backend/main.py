"""
微信小程序后端 - 论文检索与筛选 API + DeepSeek LLM 智能决策
"""
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
import os
import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ====================== 配置 ======================
API_KEY = "wk_paper_search_2026_zouyumeng"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

STRONG_TERMS = [
    "RAG", "Retrieval-Augmented", "Retrieval Augment",
    "retrieval augment", "retrieval-augmented", "augmented generation",
    "large language model", "LLM", "transformer", "attention mechanism",
    "information retrieval", "neural ranking", "semantic search",
    "question answering", "knowledge base", "vector database",
]
ALLOWED_CATEGORIES = {
    "cs.CL", "cs.LG", "cs.CV", "cs.AI", "cs.IR", "cs.NE",
    "cs.SE", "cs.CR", "cs.IT", "cs.RO", "cs.MA", "cs.SY",
    "eess.IV", "eess.SY", "eess.AS", "stat.ML", "q-fin",
    "q-bio", "q-bio.QM", "cs.HC", "cs.IR",
}


def is_relevant(title: str, abstract: str, search_keyword: str = "") -> bool:
    """判断论文是否相关：标题或摘要必须包含搜索关键词的核心词（忽略停用词）"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    text = title_lower + " " + abstract_lower

    # RAG 相关搜索：使用强相关词过滤
    if any(rag_term in search_keyword.lower() for rag_term in ["rag", "retrieval augment", "llm", "large language"]):
        return any(term.lower() in text for term in STRONG_TERMS)

    # 非 RAG 搜索：提取搜索词的关键词（去掉停用词）
    stop_words = {"in", "of", "the", "a", "an", "for", "with", "and", "or", "to", "from",
                   "on", "by", "is", "are", "was", "were", "be", "been", "being",
                   "近三年", "近两年", "近一年", "的", "在", "研究", "应用", "领域", "最新", "近年来"}
    key_terms = [w.strip() for w in search_keyword.split()
                 if w.strip().lower() not in stop_words and len(w.strip()) > 1]

    if not key_terms:
        return True

    # 至少一个关键词出现在标题中，或多个出现在摘要中
    title_hits = sum(1 for term in key_terms if term.lower() in title_lower)
    abstract_hits = sum(1 for term in key_terms if term.lower() in abstract_lower)

    # 严格：标题至少命中1个，或摘要命中3个以上
    if title_hits >= 1:
        return True
    if abstract_hits >= 3:
        return True
    return False


def parse_entry(entry, ns):
    try:
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")

        category = entry.find("atom:category", ns)
        cat_str = category.get("term", "") if category is not None else ""

        # parse_entry 只解析数据，不过滤。过滤在 search_arxiv 的循环里做。

        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        authors_str = "、".join(authors[:3])
        if len(authors) > 3:
            authors_str += f" 等{len(authors)}人"

        published = entry.findtext("atom:published", "", ns)[:10]

        url_link = ""
        for link in entry.findall("atom:link", ns):
            if link.get("type") == "text/html":
                url_link = link.get("href", "")
                break

        return {
            "title": title,
            "authors": authors_str,
            "published": published,
            "category": cat_str,
            "summary": summary[:300] + "..." if len(summary) > 300 else summary,
            "url": url_link,
        }
    except Exception:
        return None


async def search_arxiv(keyword: str, max_results: int, year_filter: int = None, search_keyword: str = "") -> list[dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    all_entries = []
    seen_ids = set()

    is_rag_search = any(rag_term in keyword.lower() for rag_term in ["rag", "retrieval augment", "llm", "large language"])
    queries = [f'"{keyword}"', keyword]
    # 只有 RAG 相关搜索才补充 RAG 短语查询
    if is_rag_search:
        queries += ["RAG", "retrieval-augmented-generation", "Retrieval Augmented Generation"]
    queries = list(dict.fromkeys(q for q in queries if q.strip()))

    for query in queries:
        if len(all_entries) >= max_results * 4:
            break

        encoded = urllib.parse.quote(query)
        # 优先标题匹配（精确），同时搜全文（广泛）
        url = (
            f"https://export.arxiv.org/api/query"
            f"?search_query=ti:{encoded}+OR+all:{encoded}"
            f"&start=0"
            f"&max_results={max_results * 2}"
            f"&sortBy=submittedDate"
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
                    if year_filter:
                        published = entry.findtext("atom:published", "")[:4]
                        if int(published) < year_filter:
                            continue
                    seen_ids.add(entry_id)
                    all_entries.append(entry)
        except Exception:
            continue

    papers = []
    for entry in all_entries:
        parsed = parse_entry(entry, ns)
        if not parsed:
            continue

        # 分类过滤
        if parsed["category"] not in ALLOWED_CATEGORIES:
            continue

        # 相关性过滤
        if not is_relevant(parsed["title"], parsed["summary"], search_keyword):
            continue

        papers.append(parsed)
        if len(papers) >= max_results:
            break

    # 结果不够时回退：去掉相关性过滤，只保留分类过滤
    if len(papers) < max_results:
        for entry in all_entries:
            parsed = parse_entry(entry, ns)
            if not parsed or parsed in papers:
                continue
            if parsed["category"] not in ALLOWED_CATEGORIES:
                continue
            papers.append(parsed)
            if len(papers) >= max_results:
                break

    return papers


async def llm_plan_search(user_message: str) -> dict:
    """调用 DeepSeek LLM 分析用户意图并规划搜索方案"""

    system_prompt = """你是一个专业的研究论文搜索规划师。用户的自然语言问题（可能是中文、英文、混合），你要做深度理解，然后规划出最优的 arXiv 搜索策略。

输出 JSON（必须严格遵守格式）：
{
  "analysis": "用1-2句话描述你如何理解用户需求（中文）",
  "search_queries": [
    "搜索变体1（英文，精确主题）",
    "搜索变体2（英文，不同角度）",
    "搜索变体3（英文，更广泛范围）"
  ],
  "year_filter": 最低年份数字，如2023；无限制则null
}

搜索策略指南：
- 中文需求 → 必须翻译成英文，变体之间要有差异
- "粒子群优化" → 变体1: "particle swarm optimization", 变体2: "PSO algorithm optimization", 变体3: "swarm intelligence optimization"
- "近三年的 transformer 最新进展" → year_filter=2023，变体分别搜 transformer 架构改进、应用、理论
- 涉及具体领域（金融、医疗、法律）→ 每个变体都要带领域词
- 3个变体要有差异化，不能只是同义词替换"""

    if not DEEPSEEK_API_KEY:
        words = user_message.strip().split()
        return {
            "analysis": "未配置 LLM，直接搜索",
            "search_queries": [user_message.strip(), " ".join(words[:max(1, len(words)-1)]), words[0] if words else "machine learning"],
            "year_filter": None,
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}], "temperature": 0.5},
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception:
        pass
    return {
        "analysis": "LLM 解析失败，使用原始输入",
        "search_queries": [user_message.strip()],
        "year_filter": None,
    }
# ====================== 全局错误处理 ======================
@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": f"Server error: {str(e)}"}), 500


# ====================== 路由 ======================
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "paper-fetcher-api",
        "llm_enabled": bool(DEEPSEEK_API_KEY),
    })


@app.route("/chat", methods=["POST"])
def chat_search():
    """智能论文搜索接口 - LLM 规划多路搜索 + 统一打分"""
    import asyncio

    api_key = request.headers.get("X-Api-Key", "")
    if api_key != API_KEY:
        return jsonify({"error": "API key invalid"}), 401

    body = request.get_json()
    if not body or not body.get("message"):
        return jsonify({"error": "message is required"}), 400

    user_message = body["message"].strip()
    if not DEEPSEEK_API_KEY:
        return jsonify({"error": "LLM not configured"}), 500

    # Step 1：LLM 规划搜索方案
    plan = asyncio.run(llm_plan_search(user_message))
    queries = plan.get("search_queries", [user_message])
    year_filter = plan.get("year_filter")
    analysis = plan.get("analysis", "")

    # Step 2：多路并发搜索
    async def search_all():
        tasks = [search_arxiv(q, 8, year_filter, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_papers = []
        seen_ids = set()
        for res in results:
            if isinstance(res, list):
                for p in res:
                    if p["url"] not in seen_ids:
                        seen_ids.add(p["url"])
                        all_papers.append(p)
        return all_papers

    all_papers = asyncio.run(search_all())

    # 结果太少时：用更精炼的核心词重试
    if len(all_papers) < 3:
        core_words = [w for w in user_message.replace("近三年", "").replace("近两年", "").replace("最新", "").replace("研究", "").split() if len(w) > 2]
        for w in core_words[:2]:
            retry = asyncio.run(search_arxiv(w.strip(), 5, year_filter, w.strip()))
            for p in retry:
                if p["url"] not in {x["url"] for x in all_papers}:
                    all_papers.append(p)

    # Step 3：LLM 统一打分（批量，一次调用）
    if all_papers and DEEPSEEK_API_KEY:
        async def batch_score():
            papers_json = json.dumps([{"title": p["title"], "summary": p["summary"][:400], "url": p["url"]} for p in all_papers], ensure_ascii=False)
            score_prompt = f"""用户需求：\"{user_message}\"
以下是候选论文列表（JSON格式）：
{papers_json}

请对每篇论文打分（0-10），判断其与用户需求的匹配程度：
- 10分：完全符合，正是用户要找的
- 7-9分：相关，但不够精准
- 4-6分：有关系但偏差较大
- 0-3分：无关或错误

输出严格的JSON数组格式（无需其他内容）：
[{{"url": "url1", "score": 9, "reason": "中文原因"}}, {{"url": "url2", "score": 5, "reason": "中文原因"}}, ...]"""
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    sc = await client.post(
                        DEEPSEEK_API_URL,
                        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": score_prompt}], "temperature": 0.2},
                    )
                    sc.raise_for_status()
                    content = sc.json()["choices"][0]["message"]["content"]
                    # 提取 JSON 数组
                    m = re.search(r'\[.*\]', content, re.DOTALL)
                    if m:
                        scores = json.loads(m.group())
                        score_map = {item["url"]: {"score": item.get("score", 5), "reason": item.get("reason", "")} for item in scores}
                        for p in all_papers:
                            if p["url"] in score_map:
                                p["relevance_score"] = score_map[p["url"]]["score"]
                                p["relevance_reason"] = score_map[p["url"]]["reason"]
                            else:
                                p["relevance_score"] = 5
                                p["relevance_reason"] = ""
            except Exception:
                for p in all_papers:
                    p["relevance_score"] = 5
                    p["relevance_reason"] = ""

            all_papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return all_papers[:20]

        all_papers = asyncio.run(batch_score())

    return jsonify({
        "total": len(all_papers),
        "papers": all_papers,
        "analysis": analysis,
        "queries_used": queries,
        "user_message": user_message,
    })


@app.route("/search", methods=["POST"])
def search_papers():
    """直接搜索接口（不经过 LLM）"""
    api_key = request.headers.get("X-Api-Key", "")
    if api_key != API_KEY:
        return jsonify({"error": "API key invalid"}), 401

    body = request.get_json()
    if not body or not body.get("keyword"):
        return jsonify({"error": "keyword required"}), 400

    keyword = body["keyword"].strip()
    max_results = min(int(body.get("max_results", 5)), 20)
    year_filter = body.get("year_filter")

    import asyncio
    papers = asyncio.run(search_arxiv(keyword, max_results, year_filter, keyword))

    return jsonify({
        "total": len(papers),
        "keyword": keyword,
        "year_filter": year_filter,
        "papers": papers,
    })


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "Paper Fetcher API with DeepSeek LLM",
        "endpoints": ["/health", "/chat", "/search"],
        "llm_enabled": bool(DEEPSEEK_API_KEY),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
