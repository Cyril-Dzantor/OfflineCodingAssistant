# assistant/config/settings.py

import os

MODEL_PATH = "Qwen 2.5/Q8/qwen2.5-coder-1.5b-instruct-q8_0.gguf"


# Hardware / Inference Settings
N_GPU_LAYERS = -1     
CONTEXT_WINDOW = 4096
MAX_TOKENS = 1024     
TEMPERATURE = 0.2     

# --- Interface Settings ---
STREAM_RESPONSE = True
SHOW_PERFORMANCE_STATS = True

# --- RAG & Embedding Settings ---
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_CACHE_DIR = "models/embeddings"
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 32
VECTOR_DB_PATH = ".cydags/vector_store.db"
PROJECT_MEMORY_PATH = ".cydags/memory.db"



