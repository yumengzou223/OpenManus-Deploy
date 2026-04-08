"""
微信小程序后端 - 论文检索与筛选 API
基于 arXiv API，实现论文搜索过滤
"""
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify
from flask_cors import CORS

# ====================== 配置 ======================
API_KEY = "wk_paper_search_2026_zouyumeng"
app = Flask(__name__)
CORS(app)

# ====================== arXiv 搜索逻辑 ======================
STRONG_TERMS = [
    "RAG", "Retrieval-Augmented", "Retrieval Augment",
    "retrieval augment", "retrieval-augmented", "augmented generation",
]
ALLOWED_CATEGORIES = {
    "cs.CL", "cs.LG", "cs.CV", "cs.AI", "cs.IR", "cs.NE",
    "cs.SE", "cs.CR", "cs.IT", "cs.RO", "cs.MA", "cs.SY",
    "eess.IV", "eess.SY", "eess.AS", "stat.ML", "q-fin",
    "q-bio", "q-bio.QM", "cs.HC",
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


async def search_arxiv(keyword: str, max_results: int) -> list[dict]:
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
                    seen_ids.add(entry_id)
                    all_entries.append(entry)
        except Exception:
            continue

    # 相关性过滤
    papers = []
    for entry in all_entries:
        parsed = parse_entry(entry, ns)
        if parsed and is_relevant(parsed["title"], parsed["summary"]):
            papers.append(parsed)
            if len(papers) >= max_results:
                break

    # 回退：取所有中相关性最高的
    if len(papers) < max_results:
        for entry in all_entries:
            parsed = parse_entry(entry, ns)
            if parsed and parsed not in papers:
                papers.append(parsed)
                if len(papers) >= max_results:
                    break

    return papers


# ====================== 路由 ======================
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "paper-fetcher-api"})


@app.route("/search", methods=["POST"])
def search_papers():
    # 鉴权
    api_key = request.headers.get("X-Api-Key", "")
    if api_key != API_KEY:
        return jsonify({"error": "API 密钥无效"}), 401

    body = request.get_json()
    if not body or not body.get("keyword"):
        return jsonify({"error": "关键词不能为空"}), 400

    keyword = body["keyword"].strip()
    max_results = min(int(body.get("max_results", 5)), 20)

    import asyncio
    papers = asyncio.run(search_arxiv(keyword, max_results))

    return jsonify({
        "total": len(papers),
        "keyword": keyword,
        "papers": papers,
    })


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "Paper Fetcher API",
        "docs": "POST /search",
        "endpoints": ["/health", "/search"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
