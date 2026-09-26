"""
Skill library with embedding-based retrieval.

Stores and retrieves remediation skills using semantic similarity.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from .skill import RemediationSkill


class SkillLibrary:
    """
    Library of remediation skills with semantic search.

    Uses local sentence-transformers embeddings for similarity-based retrieval.
    Model: all-MiniLM-L6-v2 (80MB, 384-dim, fast and accurate)
    """

    def __init__(self, storage_path: str | None = None):
        """
        Initialize skill library.

        Args:
            storage_path: Path to skills JSON file (default: registry/remediation_skills.json)
        """
        if storage_path is None:
            base_dir = Path(__file__).parent.parent.parent.parent  # Huxley root
            storage_path = base_dir / "registry" / "remediation_skills.json"

        self.storage_path = Path(storage_path)
        self.skills: dict[str, RemediationSkill] = {}
        self.embeddings: dict[str, np.ndarray] = {}  # skill_id -> embedding vector

        # Initialize local embedding model (lazy load)
        self._embedding_model = None

        # Load existing skills
        self.load()

    @property
    def embedding_model(self):
        """Lazy load local embedding model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Use all-MiniLM-L6-v2: 80MB, 384-dim, fast and accurate
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for local embeddings. "
                    "Install with: pip install sentence-transformers"
                )
        return self._embedding_model

    def add_skill(self, skill: RemediationSkill) -> None:
        """
        Add skill to library and compute embedding.

        Args:
            skill: RemediationSkill to add
        """
        self.skills[skill.skill_id] = skill

        # Generate embedding for semantic search
        embedding_text = f"{skill.name} {skill.description} {' '.join(skill.error_patterns)}"
        self.embeddings[skill.skill_id] = self._get_embedding(embedding_text)

    def remove_skill(self, skill_id: str) -> None:
        """
        Remove skill from library.

        Args:
            skill_id: ID of skill to remove
        """
        if skill_id in self.skills:
            del self.skills[skill_id]
        if skill_id in self.embeddings:
            del self.embeddings[skill_id]

    def get_skill(self, skill_id: str) -> RemediationSkill | None:
        """
        Get skill by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            RemediationSkill or None if not found
        """
        return self.skills.get(skill_id)

    def search_by_error(
        self, error_message: str, category: str, top_k: int = 5
    ) -> list[RemediationSkill]:
        """
        Search for applicable skills using semantic similarity.

        Args:
            error_message: Error text to match
            category: FeedbackCategory value
            top_k: Number of top skills to return

        Returns:
            List of matching skills, sorted by relevance
        """
        if not self.skills:
            return []

        # First filter by category and pattern matching
        exact_matches = []
        for skill in self.skills.values():
            if skill.matches_error(error_message, category):
                exact_matches.append(skill)

        # If we have exact matches, prioritize them
        if exact_matches:
            # Sort by success rate and recency
            exact_matches.sort(
                key=lambda s: (s.metadata.success_rate, s.metadata.last_used or 0), reverse=True
            )
            return exact_matches[:top_k]

        # Fall back to semantic similarity
        return self._semantic_search(error_message, top_k)

    def _semantic_search(self, query: str, top_k: int) -> list[RemediationSkill]:
        """
        Perform semantic similarity search.

        Args:
            query: Query text
            top_k: Number of results

        Returns:
            List of most similar skills
        """
        if not self.embeddings:
            return []

        # Get query embedding
        query_embedding = self._get_embedding(query)

        # Calculate cosine similarity with all skills
        similarities = []
        for skill_id, skill_embedding in self.embeddings.items():
            similarity = self._cosine_similarity(query_embedding, skill_embedding)
            similarities.append((skill_id, similarity))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top-k skills
        return [self.skills[skill_id] for skill_id, _ in similarities[:top_k]]

    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding vector for text using local model.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array (384-dimensional)
        """
        # sentence-transformers returns numpy array directly
        return self.embedding_model.encode(text, convert_to_numpy=True)

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def list_skills(
        self, skill_type: str | None = None, min_success_rate: float | None = None
    ) -> list[RemediationSkill]:
        """
        List skills with optional filtering.

        Args:
            skill_type: Filter by SkillType value
            min_success_rate: Minimum success rate threshold

        Returns:
            List of matching skills
        """
        skills = list(self.skills.values())

        if skill_type:
            skills = [s for s in skills if s.skill_type.value == skill_type]

        if min_success_rate is not None:
            skills = [s for s in skills if s.metadata.success_rate >= min_success_rate]

        return skills

    def get_stats(self) -> dict[str, Any]:
        """
        Get library statistics.

        Returns:
            Dictionary of stats
        """
        if not self.skills:
            return {
                "total_skills": 0,
                "avg_success_rate": 0.0,
                "most_used_skill": None,
            }

        total_uses = sum(
            s.metadata.success_count + s.metadata.failure_count for s in self.skills.values()
        )

        avg_success_rate = np.mean([s.metadata.success_rate for s in self.skills.values()])

        # Find most used skill
        most_used = max(
            self.skills.values(), key=lambda s: s.metadata.success_count + s.metadata.failure_count
        )

        return {
            "total_skills": len(self.skills),
            "total_uses": total_uses,
            "avg_success_rate": float(avg_success_rate),
            "most_used_skill": most_used.name,
            "reliable_skills": len([s for s in self.skills.values() if s.metadata.is_reliable]),
        }

    def save(self) -> None:
        """Save skills to disk."""
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize skills
        data = {
            "skills": [skill.to_dict() for skill in self.skills.values()],
            "embeddings": {
                skill_id: embedding.tolist() for skill_id, embedding in self.embeddings.items()
            },
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load skills from disk."""
        if not self.storage_path.exists():
            return

        with open(self.storage_path) as f:
            data = json.load(f)

        # Load skills
        for skill_data in data.get("skills", []):
            skill = RemediationSkill.from_dict(skill_data)
            self.skills[skill.skill_id] = skill

        # Load embeddings
        for skill_id, embedding_list in data.get("embeddings", {}).items():
            self.embeddings[skill_id] = np.array(embedding_list)


# Global library instance
_library: SkillLibrary | None = None


def get_library() -> SkillLibrary:
    """
    Get global skill library instance.

    Returns:
        Global SkillLibrary singleton
    """
    global _library
    if _library is None:
        _library = SkillLibrary()
    return _library
