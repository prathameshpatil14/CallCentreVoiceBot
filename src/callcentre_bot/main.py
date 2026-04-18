from fastapi import FastAPI

from .api import router

app = FastAPI(title="Call Centre Voice Bot", version="0.2.0")
app.include_router(router)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}
