import json
from pathlib import Path
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import os
import csv

load_dotenv()

app = FastAPI(title="KG API", version="0.2.0")

MOCK_PATH = Path(__file__).parent / "mock_kb.json"

def load_mock_kb():
    if not MOCK_PATH.exists():
        return []
    return json.loads(MOCK_PATH.read_text(encoding="utf-8"))

def simple_retrieve(q: str, k: int = 5):
    kb = load_mock_kb()
    q_lower = q.lower().strip()
    scored = []
    for item in kb:
        text = f"{item.get('title','')} {item.get('content','')} {' '.join(item.get('tags',[]))}"
        t = text.lower()
        score = 0
        if q_lower in t:
            score += 3
        # 词命中加分（简单但够用）
        for token in q_lower.split():
            if token and token in t:
                score += 1
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    evidences = []
    for score, item in scored[:k]:
        evidences.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "content": item.get("content"),
            "source": "advertising_mock",
            "score": score
        })
    return evidences
# =========================
# Mock 数据：从 ads.csv 读取
# =========================
ADS_CSV_PATH = os.getenv("ADS_CSV_PATH", "ads.csv")  # 默认同级 ads.csv
print(">>> ADS_CSV_PATH =", ADS_CSV_PATH)
print(">>> exists =", os.path.exists(ADS_CSV_PATH))

# 你表格的列名可能不完全一样，这里做“兼容映射”
# 你可以按你CSV的真实列名改右边的字符串（可不改，先跑起来）
COLUMN_ALIASES = {
    "id": ["id", "ID", "序号", "编号"],
    "term": ["词汇", "词条", "关键词", "名称", "标题", "term"],
    "scene": ["场景", "语境", "背景", "scene"],
    "appeal": ["核心诉求", "诉求", "卖点", "利益点", "appeal"],
    "emotion": ["情绪", "情感", "emotion"],
    "tone": ["调性", "风格", "tone"],
    "content": ["内容摘要", "内容", "文本", "文案", "content"],
    "platform": ["平台", "渠道", "platform"],
    "brand": ["品牌", "brand"],
}

def _pick(row: Dict[str, str], keys: List[str]) -> str:
    for k in keys:
        if k in row and row[k] is not None and str(row[k]).strip() != "":
            return str(row[k]).strip()
    return ""

ADS_DATA = []

if os.path.exists(ADS_CSV_PATH):
    with open(ADS_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = {
                "id": _pick(row, COLUMN_ALIASES["id"]),
                "term": _pick(row, COLUMN_ALIASES["term"]),
                "scene": _pick(row, COLUMN_ALIASES["scene"]),
                "appeal": _pick(row, COLUMN_ALIASES["appeal"]),
                "emotion": _pick(row, COLUMN_ALIASES["emotion"]),
                "tone": _pick(row, COLUMN_ALIASES["tone"]),
                "platform": _pick(row, COLUMN_ALIASES["platform"]),
                "brand": _pick(row, COLUMN_ALIASES["brand"]),
                "content": _pick(row, COLUMN_ALIASES["content"]),
            }
            ADS_DATA.append(item)
print(f">>> Loaded ADS_DATA size = {len(ADS_DATA)}")

def load_ads_from_csv(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        # 没有 csv 就给一份最小样例，保证接口能用
        return [
            {
                "id": "demo-1",
                "term": "Citywalk",
                "scene": "城市出行/周末",
                "appeal": "轻松探索城市",
                "emotion": "愉悦",
                "tone": "轻松",
                "content": "用最少的预算走最多的路，发现城市的惊喜。",
                "platform": "小红书",
                "brand": "示例品牌",
            },
            {
                "id": "demo-2",
                "term": "种草",
                "scene": "社交平台推荐",
                "appeal": "降低决策成本",
                "emotion": "信任",
                "tone": "真实分享",
                "content": "真实体验 + 关键参数对比，帮你做选择。",
                "platform": "抖音",
                "brand": "示例品牌",
            },
        ]

    data: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            item = {
                "id": _pick(row, COLUMN_ALIASES["id"]) or str(idx),
                "term": _pick(row, COLUMN_ALIASES["term"]),
                "scene": _pick(row, COLUMN_ALIASES["scene"]),
                "appeal": _pick(row, COLUMN_ALIASES["appeal"]),
                "emotion": _pick(row, COLUMN_ALIASES["emotion"]),
                "tone": _pick(row, COLUMN_ALIASES["tone"]),
                "content": _pick(row, COLUMN_ALIASES["content"]),
                "platform": _pick(row, COLUMN_ALIASES["platform"]),
                "brand": _pick(row, COLUMN_ALIASES["brand"]),
                "_raw": row,  # 保留原始行，方便你后续扩展
            }
            # 过滤空行（term/content 全空的就不要）
            if (item["term"] or item["content"]):
                data.append(item)
    return data

ADS_DATA: List[Dict[str, Any]] = load_ads_from_csv(ADS_CSV_PATH)

# =========================
# 返回结构（给工作流用）
# =========================
class Evidence(BaseModel):
    id: str
    text: str
    meta: Dict[str, Any] = {}

class RetrieveResponse(BaseModel):
    query: str
    evidences: List[Evidence]

@app.get("/health")
def health():
    return {
        "ok": True,
        "data_source": "mock_csv" if os.path.exists(ADS_CSV_PATH) else "built_in_demo",
        "count": len(ADS_DATA),
        "ads_csv_path": os.path.abspath(ADS_CSV_PATH),
    }

@app.get("/ads/sample")
def ads_sample(n: int = Query(5, ge=1, le=50)):
    return ADS_DATA[:n]

def build_evidence_text(item: Dict[str, Any]) -> str:
    # 这是给大模型/工作流拼上下文用的“证据片段”
    parts = []
    if item.get("term"):
        parts.append(f"词汇/概念：{item['term']}")
    if item.get("scene"):
        parts.append(f"场景：{item['scene']}")
    if item.get("appeal"):
        parts.append(f"核心诉求：{item['appeal']}")
    if item.get("emotion"):
        parts.append(f"情绪：{item['emotion']}")
    if item.get("tone"):
        parts.append(f"调性：{item['tone']}")
    if item.get("platform"):
        parts.append(f"平台：{item['platform']}")
    if item.get("brand"):
        parts.append(f"品牌：{item['brand']}")
    if item.get("content"):
        parts.append(f"内容：{item['content']}")
    return "；".join(parts)

def simple_score(q: str, item: Dict[str, Any]) -> int:
    q = q.strip().lower()
    if not q:
        return 0
    hay = " ".join([
        str(item.get("term", "")),
        str(item.get("scene", "")),
        str(item.get("appeal", "")),
        str(item.get("emotion", "")),
        str(item.get("tone", "")),
        str(item.get("platform", "")),
        str(item.get("brand", "")),
        str(item.get("content", "")),
    ]).lower()
    # 简单打分：出现次数越多分越高
    return hay.count(q)

@app.get("/retrieve", response_model=RetrieveResponse)
def retrieve(q: str = Query(..., min_length=1), k: int = Query(5, ge=1, le=20)):
    scored = []
    for item in ADS_DATA:
        s = simple_score(q, item)
        if s > 0:
            scored.append((s, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k]

    evidences: List[Evidence] = []
    for _, item in top:
        evidences.append(Evidence(
            id=str(item["id"]),
            text=build_evidence_text(item),
            meta={
                "term": item.get("term"),
                "platform": item.get("platform"),
                "brand": item.get("brand"),
            }
        ))

    return RetrieveResponse(query=q, evidences=evidences)

# 方便工作流做“问答演示”的一个接口：把证据直接返回给大模型用
# 队友可以：先 call /retrieve -> 拿 evidences -> 放入 LLM prompt
@app.post("/qa")
def qa_mock(question: str):
    # 这里只做“可截图的假联动”：返回证据 + 给出一个示例回答模板
    # 真正智能问答由你队友的工作流/大模型完成
    evid = retrieve(question, k=5).evidences
    return {
        "question": question,
        "evidences": [e.dict() for e in evid],
        "answer_template": (
            "你可以让大模型按下面格式回答：\n"
            "1) 结论：...\n"
            "2) 依据：引用 evidences 的 id（例如 [demo-1]）\n"
            "3) 解释：结合场景/诉求/情绪/调性/平台给建议\n"
        )
    }