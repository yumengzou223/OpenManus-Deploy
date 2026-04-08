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
        url = (
            f"https://export.arxiv.org/api/query"
            f"?search_query=all:{encoded}"
            f"&start=0"
            f"&max_results={max_results}"
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


async def llm_decide_search(user_message: str) -> dict:
    """调用 DeepSeek LLM 解析用户意图"""

    system_prompt = """你是一个论文搜索助手。用户输入自然语言问题（包括中文、英文、混合），你需要将其转化为精确的 arXiv 英文搜索关键词。

输出 JSON 格式：
{
  "search_keyword": "英文搜索关键词（必须，能直接用于 arXiv API）",
  "year_filter": 最低发表年份（如2023），无限制则null,
  "max_results": 返回论文数量（默认8）,
  "explanation": "简要说明（中文1-2句）"
}

规则：
- search_keyword 必须是英文，中文必须翻译成英文
- 如果用户说"粒子群优化" → "particle swarm optimization"
- 如果用户说"近三年" → year_filter = 2023
- 如果用户说"近两年" → year_filter = 2024
- 如果用户说"近一年" → year_filter = 2025
- 如果用户提到金融/医疗/法律等具体领域 → 翻译并保留
- search_keyword 不要包含"近三年"等时间词，只做 year_filter
- max_results 默认 8"""

    if not DEEPSEEK_API_KEY:
        return {
            "search_keyword": user_message.strip(),
            "year_filter": None,
            "max_results": 8,
            "explanation": "未配置 LLM，直接搜索用户输入",
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]

            match = re.search(r"\{.*?\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            else:
                return {
                    "search_keyword": user_message.strip(),
                    "year_filter": None,
                    "max_results": 8,
                    "explanation": "无法解析 LLM 响应，直接搜索用户输入",
                }
    except Exception as e:
        return {
            "search_keyword": user_message.strip(),
            "year_filter": None,
            "max_results": 8,
            "explanation": f"LLM 调用失败（{str(e)}），直接搜索用户输入",
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
    """智能论文搜索接口 - LLM 解析自然语言"""
    api_key = request.headers.get("X-Api-Key", "")
    if api_key != API_KEY:
        return jsonify({"error": "API key invalid"}), 401

    body = request.get_json()
    if not body or not body.get("message"):
        return jsonify({"error": "message is required"}), 400

    user_message = body["message"].strip()
    if not DEEPSEEK_API_KEY:
        return jsonify({
            "error": "LLM not configured, please set DEEPSEEK_API_KEY environment variable"
        }), 500

    # LLM 决策
    decision = None
    try:
        import asyncio
        decision = asyncio.run(llm_decide_search(user_message))
    except Exception as e:
        return jsonify({
            "error": f"LLM decision failed: {str(e)}",
            "user_message": user_message,
        }), 500

    search_keyword = decision.get("search_keyword", user_message)
    year_filter = decision.get("year_filter")
    max_results = min(int(decision.get("max_results", 8)), 20)
    explanation = decision.get("explanation", "")

    # 执行搜索（最多尝试3次，逐步放宽条件）
    papers = []
    import asyncio

    # 第1次：原计划搜索
    papers = asyncio.run(search_arxiv(search_keyword, max_results, year_filter, search_keyword))

    # 第2次：如果结果少于3篇，去掉年份过滤
    if len(papers) < 3 and year_filter:
        papers = asyncio.run(search_arxiv(search_keyword, max_results, None, search_keyword))

    # 第3次：如果还是没结果，扩大关键词范围
    if len(papers) < 3:
        words = search_keyword.split()
        if len(words) >= 2:
            broad_keyword = " ".join(words[:max(1, len(words)-1)])
        else:
            broad_keyword = search_keyword.split()[0] if search_keyword else "machine learning"
        papers = asyncio.run(search_arxiv(broad_keyword, max_results, year_filter, broad_keyword))

    # 第4次：最后尝试更通用的搜索
    if len(papers) < 3:
        first_word = search_keyword.split()[0] if search_keyword else "machine learning"
        papers = asyncio.run(search_arxiv(first_word, max_results, year_filter, first_word))

    # ========== LLM 自检：对每篇论文打分排序 ==========
    if papers and DEEPSEEK_API_KEY:
        async def score_papers_sync(paper_list):
            scored = []
            for p in paper_list:
                score_prompt = f"""用户需求：\"{user_message}\"
论文标题：{p['title']}
论文摘要：{p['summary'][:300]}

请判断这篇论文是否符合用户需求，返回 JSON：
{{"score": 0-10之间的整数, "reason": "1句话说明原因（中文）"}}

评分标准：
- 10分：完全符合，用户需求的研究方向
- 7-9分：比较相关，方向接近
- 4-6分：有相关性但不够精确
- 1-3分：勉强相关
- 0分：完全无关"""
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        sc = await client.post(
                            DEEPSEEK_API_URL,
                            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": score_prompt}], "temperature": 0.2},
                        )
                        sc.raise_for_status()
                        content = sc.json()["choices"][0]["message"]["content"]
                        m = re.search(r'"score":\s*(\d+)', content)
                        score = int(m.group(1)) if m else 5
                        reason_match = re.search(r'"reason":\s*\"([^\"]+)\"', content)
                        reason = reason_match.group(1) if reason_match else ""
                except Exception:
                    score = 5
                    reason = ""
                scored.append({**p, "relevance_score": score, "relevance_reason": reason})
            scored.sort(key=lambda x: x["relevance_score"], reverse=True)
            return scored
        papers = asyncio.run(score_papers_sync(papers))

    return jsonify({
        "total": len(papers),
        "papers": papers,
        "keyword": search_keyword,
        "year_filter": year_filter,
        "explanation": explanation,
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
