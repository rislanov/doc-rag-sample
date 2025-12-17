"""
Reranker Service - Cross-Encoder based re-ranking for RAG.

Uses BAAI/bge-reranker-v2-m3 for fast, accurate relevance scoring.
Supports Russian and 100+ other languages.
"""

import os
import logging
from typing import List, Optional
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
MODEL_NAME = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "512"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")

# Global model instance
model: Optional[CrossEncoder] = None


# --- Pydantic Models ---

class Document(BaseModel):
    """Document to be ranked."""
    id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Document text content")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata")


class RerankRequest(BaseModel):
    """Request for re-ranking documents."""
    query: str = Field(..., description="User query")
    documents: List[Document] = Field(..., description="Documents to rank")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of top results to return")


class RankedDocument(BaseModel):
    """Document with relevance score."""
    id: str
    content: str
    score: float = Field(..., description="Relevance score (0-1)")
    rank: int = Field(..., description="Position in ranking (1-based)")
    original_index: int = Field(..., description="Original position in input list (0-based)")


class RerankResponse(BaseModel):
    """Response with ranked documents."""
    query: str
    results: List[RankedDocument]
    model: str
    total_candidates: int
    processing_time_ms: float = Field(default=0, description="Processing time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model: str
    device: str
    ready: bool


# --- Model Loading ---

def load_model() -> CrossEncoder:
    """Load the Cross-Encoder model."""
    logger.info(f"Loading model: {MODEL_NAME} on {DEVICE}")
    
    model = CrossEncoder(
        MODEL_NAME,
        max_length=MAX_LENGTH,
        device=DEVICE
    )
    
    # Warmup with a test prediction
    logger.info("Warming up model...")
    _ = model.predict([("test query", "test document")])
    
    logger.info(f"Model loaded successfully on {DEVICE}")
    return model


# --- FastAPI App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    global model
    model = load_model()
    yield
    # Cleanup on shutdown
    logger.info("Shutting down reranker service")


app = FastAPI(
    title="Reranker Service",
    description="Cross-Encoder based re-ranking for RAG systems",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and model status."""
    return HealthResponse(
        status="healthy" if model is not None else "loading",
        model=MODEL_NAME,
        device=DEVICE,
        ready=model is not None
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """
    Re-rank documents by relevance to query.
    
    Uses Cross-Encoder to compute relevance scores for each (query, document) pair.
    Returns top_k most relevant documents sorted by score.
    """
    import time
    start_time = time.time()
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided")
    
    query = request.query
    documents = request.documents
    
    logger.info(f"Re-ranking {len(documents)} documents for query: {query[:50]}...")
    
    try:
        # Prepare pairs for Cross-Encoder
        pairs = [(query, doc.content) for doc in documents]
        
        # Get relevance scores
        scores = model.predict(
            pairs,
            batch_size=BATCH_SIZE,
            show_progress_bar=False
        )
        
        # Convert to float and normalize to 0-1 range (sigmoid already applied by model)
        scores = [float(s) for s in scores]
        
        # Normalize scores to 0-1 if they're not already
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 1
        if max_score > min_score:
            scores = [(s - min_score) / (max_score - min_score) for s in scores]
        else:
            scores = [0.5 for _ in scores]
        
        # Combine documents with scores and original index
        scored_docs = [(doc, score, idx) for idx, (doc, score) in enumerate(zip(documents, scores))]
        
        # Sort by score (descending)
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Take top_k
        top_docs = scored_docs[:request.top_k]
        
        processing_time = (time.time() - start_time) * 1000
        
        # Build response
        results = [
            RankedDocument(
                id=doc.id,
                content=doc.content,
                score=round(score, 4),
                rank=i + 1,
                original_index=orig_idx
            )
            for i, (doc, score, orig_idx) in enumerate(top_docs)
        ]
        
        logger.info(f"Re-ranking complete in {processing_time:.1f}ms. Top score: {results[0].score if results else 0:.4f}")
        
        return RerankResponse(
            query=query,
            results=results,
            model=MODEL_NAME,
            total_candidates=len(documents),
            processing_time_ms=round(processing_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Re-ranking failed: {e}")
        raise HTTPException(status_code=500, detail=f"Re-ranking failed: {str(e)}")


@app.post("/score")
async def score_single(query: str, document: str):
    """
    Score a single query-document pair.
    
    Useful for testing and debugging.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    try:
        score = float(model.predict([(query, document)])[0])
        return {"query": query, "document": document[:100], "score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
