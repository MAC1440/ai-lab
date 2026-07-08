from fastapi import APIRouter
from pydantic import BaseModel

from services.embeddings import EmbeddingService


router = APIRouter(prefix="/embeddings", tags=["Embeddings"])


class EmbedTestRequest(BaseModel):
    text: str


@router.post("/test")
def test_embedding(request: EmbedTestRequest):
    service = EmbeddingService()
    vector = service.embed_text(request.text)

    return {
        "text": request.text,
        "vector_length": len(vector),
        "first_10_values": vector[:10],
    }