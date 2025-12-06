import os
from dotenv import load_dotenv
from document_processor import DocumentProcessor

# Load environment variables
load_dotenv()

def main():
    # Initialize processor
    processor = DocumentProcessor()
    
    # Process the scraped data
    data_path = "data/agripolicy_content.json"
    
    if not os.path.exists(data_path):
        print("No data found. Please run the scraper first.")
        return
    
    # Run processing pipeline
    vector_store = processor.process_pipeline(data_path)
    
    # Save vector store configuration
    config = {
        "collection_name": "agri_policies",
        "embeddings": "text-embedding-3-small" if os.getenv("OPENAI_API_KEY") else "all-MiniLM-L6-v2",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "total_chunks": vector_store._collection.count() if hasattr(vector_store, '_collection') else "unknown"
    }
    
    with open("data/vector_store_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("Knowledge base initialized successfully!")

if __name__ == "__main__":
    main()