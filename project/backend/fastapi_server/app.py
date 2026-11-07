from fastapi import FastAPI

from fastapi_server.routers import analysis, candles, performance

app = FastAPI(
    title="Investor API",
    description=(
        "Свечи, аналитика и бэктест сигналов из investor "
        "(TTL-кэш на стороне backend)"
    ),
    version="0.1.0",
)

app.include_router(candles.router)
app.include_router(analysis.router)
app.include_router(performance.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Investor API", "docs": "/docs"}
