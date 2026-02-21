import os
import json
import sqlite3
import time
from datetime import datetime

class MemoryManager:
    def __init__(self):
        self.use_sqlite = False
        self.use_chroma = False
        self.redis_client = None
        self.conn = None
        self.chroma_client = None
        self.chroma_collection = None
        
        # Try connecting to Redis/Postgres (Docker Stack)
        try:
            import redis
            import psycopg2
            from pgvector.psycopg2 import register_vector
            
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=1)
            self.redis_client.ping()
            
            self.conn = psycopg2.connect(
                host="localhost",
                database="gemini_memory",
                user="gemini",
                password="gemini_password",
                connect_timeout=1
            )
            self.conn.autocommit = True
            # Postgres vector setup would go here if connected
            
        except Exception:
            # Fallback to local SQLite + ChromaDB if Docker is down
            self.use_sqlite = True
            self.db_path = os.path.join(os.path.dirname(__file__), "../ramshare/neural_bus.db")
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.conn = sqlite3.connect(self.db_path)
            self._init_sqlite()
            
            # Try ChromaDB for vectors
            try:
                import chromadb
                from sentence_transformers import SentenceTransformer
                import logging
                # Silence Transformers
                logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
                logging.getLogger("transformers").setLevel(logging.ERROR)
                
                # Small, fast, accurate local model
                self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')
                
                chroma_path = os.path.join(os.path.dirname(__file__), "../ramshare/chroma_db")
                self.chroma_client = chromadb.PersistentClient(path=chroma_path)
                
                # MULTI-LAYERED MEMORY
                self.collections = {
                    "agent_history": self.chroma_client.get_or_create_collection(name="agent_history"),
                    "user_interactions": self.chroma_client.get_or_create_collection(name="user_interactions"),
                    "project_data": self.chroma_client.get_or_create_collection(name="project_data")
                }
                # Default for backward compatibility
                self.chroma_collection = self.collections["agent_history"]
                self.use_chroma = True
            except Exception:
                pass

    def _init_sqlite(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at REAL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    content TEXT,
                    created_at TEXT
                )
            """)

    def cache_response(self, key, value, ttl=3600):
        if self.use_sqlite:
            expires_at = time.time() + ttl
            try:
                with self.conn:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                        (key, value, expires_at)
                    )
            except Exception: pass
        else:
            self.redis_client.setex(key, ttl, value)

    def get_cached_response(self, key):
        if self.use_sqlite:
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    val, expires_at = row
                    if time.time() < expires_at: return val
                    else: self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            except Exception: return None
        else:
            val = self.redis_client.get(key)
            return val.decode('utf-8') if val else None

    def store_memory(self, agent_id, content, embedding=None, metadata=None, collection_name="agent_history"):
        """Store a memory. Uses ChromaDB for vectors if available."""
        timestamp = datetime.now().isoformat()
        
        if self.use_chroma:
            try:
                coll = self.collections.get(collection_name, self.chroma_collection)
                # Generate embedding locally if not provided
                if embedding is None:
                    embedding = self.embed_model.encode(content).tolist()
                
                mem_id = f"mem_{int(time.time() * 1000)}"
                
                # Enhanced Lineage Metadata
                meta = metadata or {}
                meta.update({
                    "agent_id": agent_id,
                    "ts": timestamp,
                    "lineage_source": meta.get("run_dir", "manual_ingest"),
                    "data_quality_score": 1.0 # Default for system-generated data
                })

                coll.add(
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[meta],
                    ids=[mem_id]
                )
            except Exception as e:
                print(f"[MemoryManager] Chroma store failed ({collection_name}): {e}")

        if self.use_sqlite:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO agent_memory (agent_id, content, created_at) VALUES (?, ?, ?)",
                    (agent_id, content, timestamp)
                )
        elif self.conn:
            # Postgres logic would go here
            pass

    def search_memory(self, query_text=None, query_embedding=None, limit=10, collection_name="agent_history"):
        """Semantic search using ChromaDB or Postgres."""
        if self.use_chroma:
            try:
                coll = self.collections.get(collection_name, self.chroma_collection)
                if query_embedding is None and query_text is not None:
                    # Use local model to encode query
                    query_embedding = self.embed_model.encode(query_text).tolist()
                
                if query_embedding is not None:
                    results = coll.query(query_embeddings=[query_embedding], n_results=limit)
                else:
                    return []
                
                # Normalize to list of (content, score)
                out = []
                if results and 'documents' in results and results['documents']:
                    for doc, dist in zip(results['documents'][0], results['distances'][0]):
                        # distance to similarity roughly
                        out.append((doc, 1.0 - dist))
                return out
            except Exception as e:
                print(f"[MemoryManager] Chroma search failed ({collection_name}): {e}")
                return []
        
        # Postgres search logic would go here
        return []

    def close(self):
        if self.conn: self.conn.close()
        if self.redis_client: self.redis_client.close()
