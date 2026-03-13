# utils/embedding_model.py
from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_chroma_fn = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device='cpu')
    return _model

def get_chroma_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    global _chroma_fn
    if _chroma_fn is None:
        _chroma_fn = SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    return _chroma_fn