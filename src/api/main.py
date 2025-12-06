from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import logging
from datetime import datetime

# Import RAG system
import sys
sys.path.append('..')
from rag.rag_pipeline import AgriPolicyRAG
from rag.document_processor import DocumentProcessor

# Initialize FastAPI app
app = FastAPI(
    title="Agricultural Policy Chatbot API",
    description="API for querying agricultural policy information",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence: float
    conversation_id: Optional[str] = None
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    model: str
    document_count: int
    uptime: float

# Global instances (in production, use dependency injection)
rag_system = None
start_time = datetime.now()

@app.on_event("startup")
async def startup_event():
    """Initialize RAG system on startup"""
    global rag_system
    try:
        # Initialize document processor
        processor = DocumentProcessor()
        
        # Load or create vector store
        # In production, you'd load from persistent storage
        vector_store = processor.create_vector_store([])  # Empty for now
        
        # Initialize RAG system
        rag_system = AgriPolicyRAG(vector_store)
        
        logging.info("RAG system initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize RAG system: {e}")
        raise

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.now() - start_time).total_seconds()
    
    return HealthResponse(
        status="healthy",
        model=rag_system.llm.model_name if rag_system else "unknown",
        document_count=rag_system.vector_store._collection.count() if rag_system else 0,
        uptime=uptime
    )

@app.post("/query", response_model=QueryResponse)
async def query_policy(request: QueryRequest):
    """Main query endpoint"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        # Process query
        result = rag_system.query(request.question)
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or f"conv_{datetime.now().timestamp()}"
        
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            confidence=result["confidence"],
            conversation_id=conversation_id,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logging.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/conversation/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """Clear conversation history"""
    if rag_system:
        rag_system.clear_memory()
        return {"status": "cleared", "conversation_id": conversation_id}
    return {"status": "no active conversation"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )