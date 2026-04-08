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


def is_relevant(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    return any(term.lower() in text for term in STRONG_TERMS)


def parse_entry(entry, ns):
    try:
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")

        category = entry.find("atom:category", ns)
        cat_str = category.get("term", "") if category is not None else ""

        if cat_str not in ALLOWED_CATEGORIES:
            if not is_relevant(title, summary):
                return None

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


async def search_arxiv(keyword: str, max_results: int, year_filter: int = None) -> list[dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    all_entries = []
    seen_ids = set()

    queries = [
        f'"{keyword}"',
        keyword,
        "RAG",
        "retrieval-augmented-generation",
        "Retrieval Augmented Generation",
    ]
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
        if parsed and is_relevant(parsed["title"], parsed["summary"]):
            papers.append(parsed)
            if len(papers) >= max_results:
                break

    if len(papers) < max_results:
        for entry in all_entries:
            parsed = parse_entry(entry, ns)
            if parsed and parsed not in papers:
                papers.append(parsed)
                if len(papers) >= max_results:
                    break

    return papers


async def llm_decide_search(user_message: str) -> dict:
    """调用 DeepSeek LLM 解析用户意图"""

    system_prompt = """你是一个论文搜索助手。用户输入自然语言问题，你需要将其转化为精确的 arXiv 搜索查询。

分析用户意图，输出 JSON 格式：
{
  "search_keyword": "转化的搜索关键词（英文，最重要）",
  "year_filter": 最低发表年份（如2022），无限制则null,
  "max_results": 返回论文数量（默认8）,
  "explanation": "你做了什么搜索决策的简要说明（中文，1-2句）"
}

规则：
- search_keyword 必须是英文，能直接用于 arXiv API 搜索
- 如果用户提到具体领域（如医疗、法律、金融），关键词要包含
- 如果用户说"近三年"、"近两年"，year_filter 用2023
- 如果用户没指定数量，max_results 默认 8"""

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
    papers = asyncio.run(search_arxiv(search_keyword, max_results, year_filter))

    # 第2次：如果结果少于3篇，去掉年份过滤
    if len(papers) < 3 and year_filter:
        papers = asyncio.run(search_arxiv(search_keyword, max_results, None))

    # 第3次：如果还是没结果，换更宽泛的关键词
    if len(papers) < 3:
        broad_keyword = "RAG " + " ".join(search_keyword.split()[-2:])
        papers = asyncio.run(search_arxiv(broad_keyword, max_results, year_filter))

    # 第4次：最后尝试只搜 RAG
    if len(papers) < 3:
        papers = asyncio.run(search_arxiv("RAG retrieval augmented generation", max_results, year_filter))

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
    papers = asyncio.run(search_arxiv(keyword, max_results, year_filter))

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
