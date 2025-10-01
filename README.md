# Knowledge Graphs TD1 — Neo4j + Postgres + FastAPI

**Goal:** Explore Neo4j for recommendations, build a minimal FastAPI service, and migrate data from Postgres to Neo4j via a simple ETL.

This project provisions a local stack with Postgres, Neo4j (with APOC and GDS plugins), and a Python app exposing a small recommendation API powered by Neo4j.

## What’s implemented so far

- **Relational seed data** in Postgres: customers, categories, products, orders, order_items, and user events (`view`, `click`, `add_to_cart`). See `postgres/init/01_schema.sql` and `postgres/init/02_seed.sql`.
- **ETL to Neo4j** in `app/etl.py`:
  - Waits for Postgres and Neo4j to be ready.
  - Loads constraints and helper queries from `app/queries.cypher`.
  - Extracts rows from Postgres and creates labeled nodes and relations in Neo4j:
    - `(:Customer)`, `(:Category)`, `(:Product)`, `(:Order)`
    - `(:Product)-[:IN_CATEGORY]->(:Category)`
    - `(:Customer)-[:PLACED]->(:Order)-[:CONTAINS]->(:Product)` with quantities on the `CONTAINS` relation
    - Event relations from customers to products using APOC: `[:VIEW]`, `[:CLICK]`, `[:ADD_TO_CART]` with timestamps
- **Recommendation API** in `app/main.py` (FastAPI + Neo4j driver):
  - `GET /recs/{customer_id}?limit=5` returns products frequently co-purchased with the customer’s past purchases.
- **Exploration and GDS examples** in `app/queries.cypher`:
  - Schema constraints and indexes
  - Co-occurrence examples (product-product, customer-based)
  - Category-based recommendations
  - GDS examples for Jaccard similarity and Personalized PageRank
- **Dockerized local stack** via `docker-compose.yml` with exposed ports:
  - App: `http://localhost:8000`
  - Neo4j Browser: `http://localhost:7474` (bolt on `7687`, auth `neo4j/password`)
  - Postgres: `localhost:5432` (db `shop`, user `postgres`, pwd `postgres`)

## Architecture overview

- **Postgres** stores the transactional seed data for a toy shop.
- **ETL (`app/etl.py`)** reads Postgres tables and writes a graph model to Neo4j.
- **Neo4j** hosts the graph and powers recommendation queries (Cypher, optionally GDS).
- **FastAPI (`app/main.py`)** exposes a simple `/recs/{customer_id}` endpoint that runs a co-occurrence-style Cypher query.

Data flow: Postgres → ETL → Neo4j → FastAPI query → JSON response

## Getting started

1) Start the stack

```bash
docker compose up -d
```

This will start:
- Postgres with schema + seed data (auto-initialized from `postgres/init/*`).
- Neo4j 5.x with APOC and GDS enabled.
- Python app container running FastAPI on port 8000.

2) Run the ETL (once containers are healthy)

```bash
docker compose exec app python etl.py
```

You should see logs indicating Postgres/Neo4j readiness and then “ETL completed”.

3) Try the API

```bash
curl "http://localhost:8000/recs/C1?limit=5"
```

Example response shape:

```json
{
  "customer": "C1",
  "recommendations": [
    { "product_id": "P2", "name": "USB-C Hub", "score": 2 },
    { "product_id": "P4", "name": "Mechanical Keyboard", "score": 1 }
  ]
}
```

4) Explore the graph in Neo4j Browser

- Open `http://localhost:7474`, login `neo4j/password`.
- Paste queries from `app/queries.cypher` to inspect labels/relations and run sample recommendation and GDS queries.

## System details

### Services and configuration

- App container installs `fastapi`, `uvicorn`, `psycopg2-binary`, `neo4j` as per `app/requirements.txt` and starts Uvicorn with autoreload.
- Environment variables (configured in `docker-compose.yml`):
  - `POSTGRES_DSN=postgresql://postgres:postgres@postgres:5432/shop`
  - `NEO4J_URI=bolt://neo4j:7687`
  - `NEO4J_USER=neo4j`
  - `NEO4J_PASSWORD=password`

### Data model (Neo4j)

- Nodes: `Customer(id, name, join_date)`, `Category(id, name)`, `Product(id, name, price)`, `Order(id, ts)`
- Relations:
  - `Customer-[:PLACED]->Order`
  - `Order-[:CONTAINS {quantity}]->Product`
  - `Product-[:IN_CATEGORY]->Category`
  - `Customer-[:VIEW|:CLICK|:ADD_TO_CART {ts, id}]->Product` (created via APOC)

### API endpoint

- `GET /recs/{customer_id}?limit=5`
  - Strategy: customer-based co-occurrence over past purchases. Excludes items already purchased by the customer.
  - Returns `[ {product_id, name, score} ]` ordered by frequency.

## Development notes

- Use `docker compose logs -f app` to tail the FastAPI logs.
- You can re-run `app/etl.py` safely; MERGE patterns avoid duplicating nodes and relations.
- `app/queries.cypher` creates constraints and helpful indexes on first load.

## Troubleshooting

- API returns empty recommendations: ensure you ran the ETL and that the customer has at least one order (`C1`, `C2`, `C3` are seeded).
- Neo4j connection errors: confirm Browser at `http://localhost:7474` and that `NEO4J_URI`/auth in `docker-compose.yml` match container settings.
- Postgres auth errors: verify DSN `postgresql://postgres:postgres@postgres:5432/shop` and that the DB is initialized (check `docker compose logs postgres`).

## Next steps (nice to have)

- Add more endpoints: product-to-product co-purchase, category-based, GDS-backed similarity.
- Add Swagger docs summary and examples for `/recs`.
- Parameterize ETL batch sizes and add basic metrics.
- Optionally trigger ETL automatically on app start (guarded by an env flag).