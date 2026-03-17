from fastapi import FastAPI, Query
from typing import List, Dict, Any
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="KG API", version="1.0.1")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

def get_names(nodes) -> List[str]:
    result = []
    for n in nodes:
        if n is not None:
            props = dict(n)
            result.append(props.get("name", ""))
    return result

def search_medical_graph(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    cypher = """
    MATCH (d:Disease)
    WHERE d.name CONTAINS $q
    OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
    OPTIONAL MATCH (d)-[:HAS_COMPLICATION]->(c:Complication)
    OPTIONAL MATCH (d)-[:TREATED_BY]->(dr:Drug)
    OPTIONAL MATCH (d)-[:DIAGNOSED_BY]->(dg:Diagnosis)
    RETURN d,
           collect(DISTINCT s) AS symptoms,
           collect(DISTINCT c) AS complications,
           collect(DISTINCT dr) AS drugs,
           collect(DISTINCT dg) AS diagnoses
    LIMIT $limit
    """

    with driver.session() as session:
        records = session.run(cypher, q=q, limit=limit)
        rows = []

        for record in records:
            d = dict(record["d"])

            rows.append({
                "disease": d.get("name", ""),
                "disease_id": d.get("id", ""),
                "category": d.get("category", ""),
                "symptoms": get_names(record["symptoms"]),
                "complications": get_names(record["complications"]),
                "drugs": get_names(record["drugs"]),
                "diagnoses": get_names(record["diagnoses"])
            })

        return rows

@app.get("/health")
def health():
    try:
        with driver.session() as session:
            session.run("RETURN 1 AS ok").single()
        return {
            "ok": True,
            "data_source": "neo4j_medical",
            "neo4j_uri": NEO4J_URI
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "neo4j_uri": NEO4J_URI
        }

@app.get("/retrieve")
def retrieve(
    q: str = Query(..., min_length=1, description="疾病关键词，如：高血压"),
    top_k: int = Query(5, ge=1, le=20)
):
    results = search_medical_graph(q, top_k)
    return {
        "ok": True,
        "source": "neo4j_medical",
        "query": q,
        "count": len(results),
        "results": results
    }
