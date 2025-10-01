from fastapi import FastAPI

app = FastAPI(title="E-Commerce Graph API")

@app.get("/health")
def health():
    return {"status": "ok"}