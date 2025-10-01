import os
import psycopg2
from neo4j import GraphDatabase

PG_DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@postgres:5432/shop")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

def fetchall(cur, query):
    cur.execute(query)
    return cur.fetchall()

def run_etl():
    # 1) Read relational data
    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()

    customers = fetchall(cur, "SELECT id, name, join_date FROM customers;")
    categories = fetchall(cur, "SELECT id, name FROM categories;")
    products = fetchall(cur, "SELECT id, name, price, category_id FROM products;")
    orders = fetchall(cur, "SELECT id, customer_id, ts FROM orders;")
    order_items = fetchall(cur, "SELECT order_id, product_id, quantity FROM order_items;")
    events = fetchall(cur, "SELECT id, customer_id, product_id, event_type, ts FROM events;")

    cur.close()
    pg.close()

    # 2) Write to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # Clean slate (optional during dev)
        session.run("MATCH (n) DETACH DELETE n")

        # Nodes
        session.run("""
        UNWIND $rows AS r
        MERGE (:Customer {id:r.id, name:r.name, join_date:r.join_date})
        """, rows=[{"id": c[0], "name": c[1], "join_date": str(c[2])} for c in customers])

        session.run("""
        UNWIND $rows AS r
        MERGE (:Category {id:r.id, name:r.name})
        """, rows=[{"id": x[0], "name": x[1]} for x in categories])

        session.run("""
        UNWIND $rows AS r
        MERGE (p:Product {id:r.id})
        SET p.name = r.name, p.price = r.price
        WITH p, r
        MATCH (c:Category {id:r.category_id})
        MERGE (p)-[:IN_CATEGORY]->(c)
        """, rows=[{"id": p[0], "name": p[1], "price": float(p[2]), "category_id": p[3]} for p in products])

        session.run("""
        UNWIND $rows AS r
        MERGE (:Order {id:r.id, ts:r.ts})
        """, rows=[{"id": o[0], "ts": str(o[2])} for o in orders])

        # Relationships: customer -> order
        session.run("""
        UNWIND $rows AS r
        MATCH (cust:Customer {id:r.customer_id})
        MATCH (o:Order {id:r.order_id})
        MERGE (cust)-[:PLACED]->(o)
        """, rows=[{"customer_id": o[1], "order_id": o[0]} for o in orders])

        # Relationships: order -> product
        session.run("""
        UNWIND $rows AS r
        MATCH (o:Order {id:r.order_id})
        MATCH (p:Product {id:r.product_id})
        MERGE (o)-[rel:CONTAINS]->(p)
        SET rel.quantity = r.quantity
        """, rows=[{"order_id": oi[0], "product_id": oi[1], "quantity": int(oi[2])} for oi in order_items])

        # Behavioral events: customer -> product
        session.run("""
        UNWIND $rows AS r
        MATCH (cust:Customer {id:r.customer_id})
        MATCH (p:Product {id:r.product_id})
        CALL {
          WITH r, cust, p
          WITH r, cust, p, CASE r.event_type
              WHEN 'view' THEN 'VIEW'
              WHEN 'click' THEN 'CLICK'
              WHEN 'add_to_cart' THEN 'ADD_TO_CART'
            END AS reltype
          CALL apoc.create.relationship(cust, reltype, {ts:r.ts, event_id:r.id}, p) YIELD rel
          RETURN rel
        }
        RETURN count(*) AS created
        """, rows=[{"id": e[0], "customer_id": e[1], "product_id": e[2], "event_type": e[3], "ts": str(e[4])} for e in events])

    driver.close()
    return {
        "customers": len(customers),
        "categories": len(categories),
        "products": len(products),
        "orders": len(orders),
        "order_items": len(order_items),
        "events": len(events),
    }

if __name__ == "__main__":
    print(run_etl())

  

