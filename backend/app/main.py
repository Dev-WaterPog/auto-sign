from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import sign, sign_document, signatures, templates
from app.core.config import settings

app = FastAPI(title="Auto Sign API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Job-Id"],
)

app.include_router(signatures.router)
app.include_router(templates.router)
app.include_router(sign.router)
app.include_router(sign_document.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
