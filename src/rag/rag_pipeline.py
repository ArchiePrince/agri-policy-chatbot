from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.memory import ConversationBufferMemory
from typing import List, Dict, Any
import logging

class AgriPolicyRAG:
    def __init__(self, vector_store, model_name="gpt-3.5-turbo"):
        self.vector_store = vector_store
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=0.1,  # Lower temperature for more factual responses
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Create specialized retriever
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",  # Maximal Marginal Relevance for diversity
            search_kwargs={
                "k": 5,  # Number of documents to retrieve
                "score_threshold": 0.7,  # Minimum similarity score
                "fetch_k": 20  # Initial pool size for MMR
            }
        )
        
        # Add compression to filter irrelevant parts
        compressor = LLMChainExtractor.from_llm(self.llm)
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=self.retriever
        )
        
        # Memory for conversation context
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        # Create specialized prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question", "chat_history"],
            template="""
            You are an expert agricultural policy assistant. Your knowledge comes exclusively from the Agricultural Policy Toolkit.
            
            CONTEXT FROM POLICY TOOLKIT:
            {context}
            
            CONVERSATION HISTORY:
            {chat_history}
            
            USER QUESTION: {question}
            
            INSTRUCTIONS:
            1. Answer based ONLY on the provided context
            2. If the context doesn't contain relevant information, say "I don't have information about that in the policy toolkit."
            3. For policy questions, be precise and cite specific sections or documents
            4. Format your answer clearly with bullet points for multiple items
            5. Always end with the source documents you used
            
            ANSWER:
            """
        )
        
        # Create QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.compression_retriever,
            memory=self.memory,
            chain_type_kwargs={
                "prompt": self.prompt_template,
                "verbose": True
            },
            return_source_documents=True
        )
    
    def query(self, question: str, conversational_context: List[Dict] = None) -> Dict[str, Any]:
        """
        Query the RAG system with a question
        
        Args:
            question: User's question
            conversational_context: Previous conversation turns
            
        Returns:
            Dict containing answer and source documents
        """
        try:
            # Add conversational context if provided
            if conversational_context:
                for turn in conversational_context[-3:]:  # Last 3 turns
                    if turn["role"] == "user":
                        self.memory.chat_memory.add_user_message(turn["content"])
                    else:
                        self.memory.chat_memory.add_ai_message(turn["content"])
            
            # Execute query
            result = self.qa_chain({"query": question})
            
            # Format response
            response = {
                "answer": result["result"],
                "sources": [],
                "confidence": self._calculate_confidence(result.get("source_documents", []))
            }
            
            # Extract unique sources
            seen_sources = set()
            for doc in result.get("source_documents", []):
                source = doc.metadata.get("source", "Unknown")
                title = doc.metadata.get("title", "Untitled")
                if source not in seen_sources:
                    response["sources"].append({
                        "url": source,
                        "title": title,
                        "category": doc.metadata.get("category", "General"),
                        "relevance_score": doc.metadata.get("score", 0.0)
                    })
                    seen_sources.add(source)
            
            return response
            
        except Exception as e:
            logging.error(f"Error in RAG query: {e}")
            return {
                "answer": "I encountered an error processing your request. Please try again.",
                "sources": [],
                "confidence": 0.0
            }
    
    def _calculate_confidence(self, source_documents: List) -> float:
        """Calculate confidence score based on retrieved documents"""
        if not source_documents:
            return 0.0
        
        # Simple confidence calculation based on number and relevance of sources
        scores = [doc.metadata.get("score", 0.5) for doc in source_documents if hasattr(doc, 'metadata')]
        
        if not scores:
            return 0.5
        
        avg_score = sum(scores) / len(scores)
        
        # Boost confidence if we have multiple sources
        source_count = len(set(doc.metadata.get("source", "") for doc in source_documents))
        count_boost = min(0.3, source_count * 0.1)
        
        return min(1.0, avg_score + count_boost)
    
    def add_document(self, document: Dict):
        """Add new document to the vector store"""
        # Implementation for incremental updates
        pass
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()