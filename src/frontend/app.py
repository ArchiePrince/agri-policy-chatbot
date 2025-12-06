import streamlit as st
import requests
import json
from datetime import datetime

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="🌾 AgriPolicy Assistant",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
    }
    .assistant-message {
        background-color: #f3e5f5;
        border-left: 5px solid #9c27b0;
    }
    .source-card {
        padding: 0.5rem;
        margin: 0.5rem 0;
        background: #f5f5f5;
        border-radius: 0.25rem;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "api_available" not in st.session_state:
    st.session_state.api_available = False

# Sidebar
with st.sidebar:
    st.title("🌾 AgriPolicy Assistant")
    st.markdown("---")
    
    # API Status
    st.subheader("System Status")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            health = response.json()
            st.success(f"✅ API Healthy")
            st.info(f"Model: {health['model']}")
            st.info(f"Documents: {health['document_count']}")
            st.session_state.api_available = True
        else:
            st.error("❌ API Unavailable")
            st.session_state.api_available = False
    except:
        st.error("❌ Cannot connect to API")
        st.session_state.api_available = False
    
    st.markdown("---")
    
    # Clear conversation
    if st.button("🔄 Clear Conversation", use_container_width=True):
        if st.session_state.conversation_id:
            requests.post(f"{API_BASE_URL}/conversation/{st.session_state.conversation_id}/clear")
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()
    
    st.markdown("---")
    st.markdown("""
    ### About
    This assistant uses the Agricultural Policy Toolkit to provide accurate, up-to-date information on agricultural policies worldwide.
    
    ### Features
    • Policy information retrieval
    • Implementation guidance
    • Regional policy comparison
    • Source citation
    """)

# Main chat interface
st.title("🌾 Agricultural Policy Assistant")
st.markdown("Ask questions about agricultural policies, subsidies, regulations, and best practices.")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display sources for assistant messages
        if message["role"] == "assistant" and "sources" in message:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"""
                    <div class="source-card">
                        <strong>{source['title']}</strong><br>
                        <small>Category: {source['category']}</small><br>
                        <small>Relevance: {source['relevance_score']:.2%}</small>
                    </div>
                    """, unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Ask about agricultural policies..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        if not st.session_state.api_available:
            st.error("API is unavailable. Please check the backend server.")
        else:
            try:
                # Prepare API request
                request_data = {
                    "question": prompt,
                    "conversation_id": st.session_state.conversation_id,
                    "user_id": "demo_user"  # In production, use actual user auth
                }
                
                # Call API
                response = requests.post(
                    f"{API_BASE_URL}/query",
                    json=request_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Update conversation ID
                    if not st.session_state.conversation_id:
                        st.session_state.conversation_id = result["conversation_id"]
                    
                    # Display answer
                    message_placeholder.markdown(result["answer"])
                    
                    # Display confidence
                    st.caption(f"Confidence: {result['confidence']:.2%}")
                    
                    # Display sources in expander
                    with st.expander("📚 Sources"):
                        for source in result["sources"]:
                            st.markdown(f"""
                            <div class="source-card">
                                <strong>{source['title']}</strong><br>
                                <small>URL: {source['url'][:50]}...</small><br>
                                <small>Category: {source['category']}</small><br>
                                <small>Relevance: {source['relevance_score']:.2%}</small>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Add to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"]
                    })
                    
                else:
                    st.error(f"API Error: {response.status_code}")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("Powered by Agricultural Policy Toolkit")
with col2:
    st.caption(f"Conversation ID: {st.session_state.conversation_id or 'None'}")
with col3:
    st.caption(f"Messages: {len(st.session_state.messages)}")