from fastapi import FastAPI

app = FastAPI(
    title="Album Mosaic API",
    version="0.1.0",
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}