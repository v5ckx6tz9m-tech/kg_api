from fastapi import FastAPI, Query
from typing import List, Dict, Any
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="KG API", version="1.0.0")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

def node_display_name(props: Dict[str, Any]) -> str:
    return (
        props.get("name")
        or props.get("疾病")
        or props.get("症状")
        or props.get("药物")
        or props.get("诊断")
        or props.get("并发症")
        or str(props)
    )

def search_medical_graph(q: str, limit: int = 10) -> List[Dict[str, Any]]:
    cypher = """
    MATCH (d:Disease)
    WHERE d.name CONTAINS $q
       OR d.disease CONTAINS $q
       OR d.疾病 CONTAINS $q
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
        result = session.run(cypher, q=q, limit=limit)
        rows = []

        for record in result:
            disease_node = record["d"]
            symptoms = record["symptoms"]
            complications = record["complications"]
            drugs = record["drugs"]
            diagnoses = record["diagnoses"]

            disease_props = dict(disease_node) if disease_node else {}

            def names(nodes):
                out = []
                for n in nodes:
                    if n is None:
                        continue
                    out.append(node_display_name(dict(n)))
                return out

            rows.append({
                "disease": node_display_name(disease_props),
                "disease_props": disease_props,
                "symptoms": names(symptoms),
                "complications": names(complications),
                "drugs": names(drugs),
                "diagnoses": names(diagnoses),
            })

        return rows

@app.get("/health")
def health():
    return {
        "ok": True,
        "data_source": "neo4j_medical",
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
