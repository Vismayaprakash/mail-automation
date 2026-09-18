import logging
import os
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from config import settings

logger = logging.getLogger(__name__)

class RAGManager:
    """Manages local vector store using ChromaDB for past email indexing and retrieval."""

    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_dir, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        
        # Use ChromaDB's built-in lightweight default embedding function (ONNX-backed, no PyTorch DLL dependencies)
        try:
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        except Exception:
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL_NAME
            )
        
        self.collection = self.client.get_or_create_collection(
            name="email_history",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def add_email(
        self,
        email_id: str,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        is_sent: bool = True
    ):
        """Index an email into local vector database."""
        document_text = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n\nContent:\n{body}"
        metadata = {
            "email_id": email_id,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "is_sent": str(is_sent)
        }
        
        try:
            self.collection.upsert(
                ids=[email_id],
                documents=[document_text],
                metadatas=[metadata]
            )
            logger.info(f"Successfully indexed email {email_id} into ChromaDB")
        except Exception as e:
            logger.error(f"Error indexing email {email_id} into ChromaDB: {e}")

    def query_context(self, sender_email: str, current_email_body: str, top_k: int = 3) -> str:
        """Retrieve relevant past interactions with a contact or similar emails."""
        try:
            results = self.collection.query(
                query_texts=[current_email_body],
                n_results=top_k,
                where={"$or": [{"sender": sender_email}, {"recipient": sender_email}]}
            )
        except Exception:
            # Fallback if no metadata filter matches
            try:
                results = self.collection.query(
                    query_texts=[current_email_body],
                    n_results=top_k
                )
            except Exception as e:
                logger.error(f"ChromaDB query error: {e}")
                return ""

        documents = results.get("documents", [[]])[0]
        if not documents:
            return ""

        formatted_docs = []
        for idx, doc in enumerate(documents, start=1):
            formatted_docs.append(f"--- Past Interaction #{idx} ---\n{doc}")

        return "\n\n".join(formatted_docs)

rag_manager = RAGManager()
