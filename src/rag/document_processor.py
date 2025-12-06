from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import JSONLoader
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain.vectorstores import Qdrant
from langchain.schema import Document
import json
import hashlib
from typing import List, Dict
import qdrant_client
import os

class DocumentProcessor:
    def __init__(self, embedding_model="text-embedding-3-small"):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Choose embedding model based on availability
        if os.getenv("OPENAI_API_KEY"):
            self.embeddings = OpenAIEmbeddings(
                model=embedding_model,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
        else:
            # Use free alternative
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
    
    def load_scraped_data(self, filepath: str) -> List[Document]:
        """Load scraped JSON data into LangChain Documents"""
        
        def metadata_func(record: Dict, metadata: Dict) -> Dict:
            """Extract metadata from JSON records"""
            metadata.update({
                "source": record.get("url", ""),
                "title": record.get("title", ""),
                "category": record.get("category", ""),
                "chunk_id": hashlib.md5(
                    f"{record.get('url', '')}_{json.dumps(record.get('paragraphs', []))}".encode()
                ).hexdigest()[:8]
            })
            return metadata
        
        loader = JSONLoader(
            file_path=filepath,
            jq_schema=".[]",
            content_key="paragraphs",
            metadata_func=metadata_func
        )
        
        return loader.load()
    
    def create_chunks(self, documents: List[Document]) -> List[Document]:
        """Split documents into manageable chunks"""
        chunks = []
        
        for doc in documents:
            # Combine paragraphs for splitting
            content = "\n\n".join(doc.page_content) if isinstance(doc.page_content, list) else doc.page_content
            
            # Split the content
            split_chunks = self.text_splitter.split_text(content)
            
            # Create new documents with metadata
            for i, chunk in enumerate(split_chunks):
                metadata = doc.metadata.copy()
                metadata["chunk_index"] = i
                metadata["total_chunks"] = len(split_chunks)
                
                chunks.append(Document(
                    page_content=chunk,
                    metadata=metadata
                ))
        
        return chunks
    
    def create_vector_store(self, chunks: List[Document], collection_name="agri_policies"):
        """Create and populate Qdrant vector store"""
        
        # Initialize Qdrant client (local for development)
        client = qdrant_client.QdrantClient(
            location=":memory:"  # Use "localhost:6333" for persistent storage
        )
        
        # Create vector store
        vector_store = Qdrant.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            url="http://localhost:6333",  # Change for production
            collection_name=collection_name,
            force_recreate=True  # Set to False for incremental updates
        )
        
        return vector_store
    
    def process_pipeline(self, data_path: str):
        """Complete processing pipeline"""
        print("Loading documents...")
        documents = self.load_scraped_data(data_path)
        
        print(f"Loaded {len(documents)} documents")
        print("Creating chunks...")
        chunks = self.create_chunks(documents)
        
        print(f"Created {len(chunks)} chunks")
        print("Creating vector store...")
        vector_store = self.create_vector_store(chunks)
        
        print("Vector store created successfully!")
        return vector_store