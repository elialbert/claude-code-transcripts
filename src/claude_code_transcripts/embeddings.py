"""Embedding generation service using sentence-transformers."""

from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the model on first use."""
        if self._model is None:
            print(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text(s).

        Args:
            text: Single text string or list of texts

        Returns:
            Numpy array of embeddings (single vector or matrix)
        """
        return self.model.encode(text, convert_to_numpy=True)

    def encode_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to encode

        Returns:
            List of floats representing the embedding vector
        """
        embedding = self.encode(text)
        return embedding.tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to encode

        Returns:
            List of embedding vectors
        """
        embeddings = self.encode(texts)
        return [emb.tolist() for emb in embeddings]

    @property
    def embedding_dim(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self.model.get_sentence_embedding_dimension()


# Global instance (lazy-loaded)
_embedding_service = None


def get_embedding_service(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingService:
    """
    Get or create the global embedding service instance.

    Args:
        model_name: Name of the model to use

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None or _embedding_service.model_name != model_name:
        _embedding_service = EmbeddingService(model_name)
    return _embedding_service
