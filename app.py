import streamlit as st
import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
# from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.chains import RetrievalQA
from langchain_community.chat_models import ChatOllama
import tempfile

import storage
import db
import auth



# --- Page Configuration ---
st.set_page_config(
    page_title="INTELLIDOC_QA",
    page_icon="📄",
    layout="wide"
)
st.markdown("""
<style>

/* Make buttons look like inline icons */
section[data-testid="stSidebar"] .stButton button {
    background: none !important;
    border: none !important;
    padding: 2px !important;
    font-size: 14px !important;
    height: auto !important;
    min-height: auto !important;
}

/* Reduce gap between columns */
section[data-testid="stSidebar"] [data-testid="column"] {
    padding: 0px !important;
    gap: 2px !important;
    align-items: center !important;
}

/* Remove extra spacing */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}

/* Chat row spacing */
.chat-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None    
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "current_chat_id" not in st.session_state:
    chat_number = len(st.session_state.chats) + 1
    chat_id = f"Chat {chat_number}"

    st.session_state.chats[chat_id] = {
        "title": chat_id,
        "messages": [],
        "retriever": None,
        "files": None,
        "file_urls": None,
        "db_chat_id": None,
        "title_updated": False
    }

    st.session_state.current_chat_id = chat_id   
if "chat_ended" not in st.session_state:
    st.session_state.chat_ended = False
if "retriever" not in st.session_state:
    st.session_state.retriever = None
if "processed_file_names" not in st.session_state:
    st.session_state.processed_file_names = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0    
if "rename_chat" not in st.session_state:
    st.session_state.rename_chat = None  
if "chat_counter" not in st.session_state:
    st.session_state.chat_counter = 1      



# --- RAG Core Functions ---
#@st.cache_resource(show_spinner="Processing PDFs...")
def create_retriever_from_pdfs(pdf_files):
    """
    Takes a list of uploaded PDF files, processes them, and returns a retriever object.
    This function is cached to avoid reprocessing the same files.
    """
    try:
        all_documents = []

        # 1. Load all uploaded PDFs
        for pdf_file in pdf_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                tmpfile.write(pdf_file.getvalue())
                pdf_path = tmpfile.name

            loader = PyMuPDFLoader(pdf_path)
            documents = loader.load()
            os.remove(pdf_path)  # Clean up temp file
            all_documents.extend(documents)

        # 2. Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        text_chunks = text_splitter.split_documents(all_documents)

        if not text_chunks:
            st.error("Could not split the documents into chunks. The PDFs might be empty or unreadable.")
            return None

        # 3. Create embeddings & vector store (HuggingFace instead of Gemini embeddings)
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        vector_store = FAISS.from_documents(text_chunks, embedding=embeddings)

        # 4. Return retriever
        return vector_store.as_retriever()

    except Exception as e:
        st.error(f"An error occurred during PDF processing: {e}")
        return None


# --- Streamlit UI and Chat Logic ---
# 🔹 Ensure valid chat always exists
if (
    "current_chat_id" not in st.session_state or
    st.session_state.current_chat_id not in st.session_state.chats
):
    chat_id = "Chat 1"

    st.session_state.chats[chat_id] = {
        "title": chat_id,
        "messages": [],
        "retriever": None,
        "files": None,
        "file_urls": None,
        "db_chat_id": None,
        "title_updated":False
    }

    st.session_state.current_chat_id = chat_id

col1, col2, col3 = st.columns([6,1,1])

if not st.session_state.is_logged_in:
    with col2:
        if st.button("Login", key="nav_login"):
            st.session_state.page = "login"
            st.rerun()

    with col3:
        if st.button("Signup", key="nav_signup"):
            st.session_state.page = "signup"
            st.rerun()

# 🔹 Show Logout ONLY if logged in
else:
    with col3:
        if st.button("🚪 Logout", key="logout_btn"):
            st.session_state.is_logged_in = False
            st.session_state.user_id = None
            st.session_state.chats={}
            
            st.session_state.chat_ended = False

            st.session_state.page = "home"
            st.rerun()

if st.session_state.page == "login":
    st.title("🔐 Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", key="form_login"):
        user_id = auth.login_user(email, password)

        if user_id:
            # 🔹 Set session
            st.session_state.is_logged_in = True
            st.session_state.user_id = user_id

            # 🔹 Fetch chats from DB
            user_chats = db.get_user_chats(user_id)

            # 🔹 Reset session chats
            st.session_state.chats = {}

            # 🔹 Load chats
            for chat in user_chats:
                chat_id, title = chat

                messages = db.get_messages(chat_id)
                files = db.get_files(chat_id)
                file_urls = [f[1] for f in files] if files else None

                
                st.session_state.chats[chat_id] = {
                    "title": title,
                    "messages": [{"role": m[0], "content": m[1]} for m in messages],
                    "retriever": None,
                    "files": [f[0] for f in files] if files else None,
                    "file_urls": [f[1] for f in files] if files else None,
                    "db_chat_id": chat_id,
                    "title_updated" : True
                }

            # 🔥 Handle both cases (IMPORTANT)
            if st.session_state.chats:
                # Existing user
                st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
            else:
                
                chat_id = "Chat 1"

                st.session_state.chats[chat_id] = {
                    "title": chat_id,
                    "messages": [],
                    "retriever": None,
                    "files": None,
                    "file_urls": None,
                    "db_chat_id": None,
                    "title_updated" : False
                }

                st.session_state.current_chat_id = chat_id

            # 🔹 Redirect
            st.session_state.page = "home"
            st.rerun()

        else:
            st.error("Invalid credentials")

    if st.button("Back", key="login_back"):
        st.session_state.page = "home"
        st.rerun()

    st.stop()


if st.session_state.page == "signup":
    st.title("📝 Signup")

    name = st.text_input("Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Signup",key="form_signup"):
        user_id = auth.create_user(name, email, password)

        if user_id:
            st.success("Account created! Please login.")
            st.session_state.page = "login"
            st.rerun()
        else:
            st.error("User already exists")

    if st.button("Back",key="signup_back"):
        st.session_state.page = "home"
        st.rerun()

    st.stop() 





st.title("INTELLIDOC QA")

if st.button("End Chat"):
    st.session_state.chat_ended = True
    st.session_state.chats[st.session_state.current_chat_id]["messages"].append(
        {"role": "assistant", "content": "Thanks for chatting! Goodbye!"}
    )

st.markdown("---")
st.write("Upload one or more PDFs, and I'll answer your questions about them.")



# Sidebar for file upload
with st.sidebar:
    st.header("Upload Documents")

    # File uploader (with dynamic key)
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True,
        key=st.session_state.uploader_key
    )
    
    # Get current chat and char_id safely
    current_chat_id = st.session_state.current_chat_id
    current_chat = st.session_state.chats[st.session_state.current_chat_id]
    # Lazy retriever loading
    if current_chat["retriever"] is None and current_chat["file_urls"]:
        with st.spinner("Loading documents..."):
            pdf_files = []

            for url in current_chat["file_urls"]:
                file_obj = storage.download_file_from_url(url)
                if file_obj:
                    file_obj.name = "temp.pdf"
                    pdf_files.append(file_obj)

            if pdf_files:
                current_chat["retriever"] = create_retriever_from_pdfs(pdf_files)


    # --- Upload Logic ---
    if uploaded_files:

        current_chat = st.session_state.chats[current_chat_id]

        if st.session_state.is_logged_in and not current_chat.get("db_chat_id"):
            db_chat_id = db.create_chat(
                st.session_state.user_id,
                current_chat["title"]
            )
            current_chat["db_chat_id"] = db_chat_id
    
        file_names = [f.name for f in uploaded_files]

        # Process only if new files for THIS chat
        if current_chat["files"] != file_names:
            file_urls = []
            for file in uploaded_files:
                file_url = storage.upload_file_to_supabase(file, current_chat_id)
                if current_chat.get("db_chat_id"):
                    db.save_files(current_chat["db_chat_id"],file.name,file_url)

                file_urls.append(file_url)

            retriever = create_retriever_from_pdfs(uploaded_files)

            current_chat["retriever"] = retriever
            current_chat["files"] = file_names
            current_chat["file_urls"] = file_urls

            if retriever:
                st.success("Documents processed! You can now ask questions.")
            else:
                current_chat["files"] = None
                current_chat["file_urls"] = None

    # --- Show current chat document ---
    if current_chat["files"]:
        st.success(f"📄 Loaded: {', '.join(current_chat['files'])}")

    if not current_chat["retriever"]:
        st.info("Please upload a PDF for this chat")

    st.markdown("---")

    

    # --- New Chat Button ---
    if st.button("➕ New Chat"):
        st.session_state.chat_counter += 1
        chat_id = f"Chat {st.session_state.chat_counter}"
        

        st.session_state.chats[chat_id] = {
            "title" : chat_id,
            "messages": [],
            "retriever": None,
            "files": None,
            "file_urls" : None,
            "db_chat_id" : None,
            "title_updated":False
        }

        st.session_state.current_chat_id = chat_id
        st.session_state.chat_ended = False

        # Reset uploader UI
        st.session_state.uploader_key += 1

        st.rerun()

    # --- Chat List ---
    st.markdown("📜 Your Chats")

    for chat_id in list(st.session_state.chats.keys()):
        chat = st.session_state.chats[chat_id]
        chat_title = chat.get("title", chat_id)

        # Better spacing
        col1, col2, col3 = st.columns([10, 1, 1])
        if "rename_chat" in st.session_state and st.session_state.rename_chat == chat_id:

            with col1:
                new_name = st.text_input(
                    "Rename",
                    value=chat_title,
                    key=f"rename_input_{chat_id}"
                )

            with col2:
                if st.button("✔", key=f"save_{chat_id}"):
                    if new_name.strip():
                        chat["title"] = new_name.strip()
                        if chat.get("db_chat_id"):
                            db.update_chat_title(chat["db_chat_id"],chat["title"])

                    del st.session_state.rename_chat
                    st.rerun()

            with col3:
                if st.button("❌", key=f"cancel_{chat_id}"):
                    del st.session_state.rename_chat
                    st.rerun()
        else:
        # 🔹 Chat title
            with col1:
                if chat_id == st.session_state.current_chat_id:
                    st.markdown(f"<div style='font-size:15px;'>👉 <b>{chat_title}</b></div>", unsafe_allow_html=True)
                else:
                    if st.button(chat_title, key=f"chat_btn_{chat_id}"):
                        st.session_state.current_chat_id = chat_id
                        st.rerun()

            # 🔹 Delete
            with col2:
                if st.button("🗑", key=f"del_{chat_id}"):

                    chat = st.session_state.chats[chat_id]

                    # Delete from DB if exists
                    if chat.get("db_chat_id"):
                        db.delete_chat(chat["db_chat_id"])

                    # Delete from session
                    del st.session_state.chats[chat_id]

                    # Handle fallback
                    if st.session_state.chats:
                        st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
                    else:
                        new_id = "Chat 1"
                        st.session_state.chats[new_id] = {
                            "title": new_id,
                            "messages": [],
                            "retriever": None,
                            "files": None,
                            "file_urls": None,
                            "db_chat_id": None,
                            "title_updated": False
                        }
                        st.session_state.current_chat_id = new_id

                    st.rerun()
            # 🔹 Rename
            with col3:
                if st.button("✏", key=f"edit_{chat_id}"):
                    st.session_state.rename_chat = chat_id
                    st.rerun()

# Display chat history
for message in st.session_state.chats[st.session_state.current_chat_id]["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Chat input logic
if not st.session_state.chat_ended:
    current_chat = st.session_state.chats[st.session_state.current_chat_id]
    if current_chat["retriever"]:
        if prompt := st.chat_input("Ask a question about the documents..."):
            current_chat = st.session_state.chats[st.session_state.current_chat_id]

            if st.session_state.is_logged_in and not current_chat.get("db_chat_id"):
                db_chat_id = db.create_chat(
                st.session_state.user_id,
                current_chat["title"]
                )
                current_chat["db_chat_id"] = db_chat_id

            # Show user message
            with st.chat_message("user"):
                st.markdown(prompt)
            current_chat["messages"].append({"role": "user", "content": prompt})
            # Auto title from first question
            if not current_chat.get("title_updated",False):
                current_chat["title"] = prompt[:20] + "..."
                current_chat["title_updated"] = True
            # save to DB
                if current_chat.get("db_chat_id"):
                    db.update_chat_title(current_chat["db_chat_id"],current_chat["title"])
            if current_chat.get("db_chat_id"):
                db.save_message(current_chat["db_chat_id"],"user",prompt)    
            
            
            # Generate and show answer
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        prompt_template = ChatPromptTemplate.from_template("""
                        You are an expert assistant. Answer the question as detailed as possible based on the provided context.
                        Make sure to provide all the details and be friendly. If the answer is not in the provided context,
                        politely say, "The information is not available in the provided document." Do not invent answers.

                        Context:
                        {context}

                        Question:
                        {input}
                        """)
                        llm = ChatOllama(
                            model="phi3:mini", 
                            temperature=0.3,
                        )

                        document_chain = create_stuff_documents_chain(llm, prompt_template)
                        retrieval_chain = create_retrieval_chain(
                            current_chat["retriever"],
                            document_chain
                        )

                        response = retrieval_chain.invoke({"input": prompt})
                        answer = response.get("answer", "Sorry, I couldn't find an answer.")

                        st.markdown(answer)
                        st.session_state.chats[st.session_state.current_chat_id]["messages"].append(
                            {"role": "assistant", "content": answer}
                        )

                        # save to DB
                        if current_chat.get("db_chat_id"):
                            db.save_message(current_chat["db_chat_id"], "assistant", answer)

                    except Exception as e:
                        error_message = f"An error occurred: {e}"
                        st.error(error_message)
                        st.session_state.chats[st.session_state.current_chat_id]["messages"].append(
                            {"role": "assistant", "content": error_message}
                        )
                        if current_chat.get("db_chat_id"):
                            db.save_message(current_chat["db_chat_id"], "assistant", error_message)
    else:
        st.info("Please upload at least one PDF in the sidebar to get started.")
