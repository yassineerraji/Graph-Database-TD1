import os
from fastapi import FastAPI
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI()

@app.get("/recs/{customer_id}")
def recs(customer_id: str, limit: int = 5):
    query = """
    MATCH (c:Customer {id:$cid})-[:PLACED]->(:Order)-[:CONTAINS]->(p:Product)
    MATCH (o2:Order)-[:CONTAINS]->(p)
    MATCH (o2)-[:CONTAINS]->(rec:Product)
    WHERE NOT (c)-[:PLACED]->(:Order)-[:CONTAINS]->(rec)
    WITH rec, count(*) AS score
    RETURN rec.id AS product_id, rec.name AS name, score
    ORDER BY score DESC LIMIT $limit
    """
    with driver.session() as s:
        rows = s.run(query, {"cid": customer_id, "limit": limit}).data()
    return {"customer": customer_id, "recommendations": rows}