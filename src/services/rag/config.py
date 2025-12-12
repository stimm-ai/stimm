"""
RAG Service Configuration Module
"""

import os

from dotenv import load_dotenv

load_dotenv()


class RAGConfig:
    """Configuration for RAG Service"""

    def __init__(self):
        # Conversation cache configuration
        self.conv_cache_limit = int(os.getenv("CONVERSATION_CACHE_LIMIT", "128"))
        self.conv_cache_ttl_seconds = int(os.getenv("CONVERSATION_CACHE_TTL_SECONDS", "900"))
        self.conv_max_return_messages = int(os.getenv("CONVERSATION_MAX_RETURN_MESSAGES", "12"))

        # System prompt (generic fallback)
        self.system_prompt = """
                                Vous êtes un assistant vocal intelligent.
                                Répondez de façon claire, concise et utile.
                                Basez vos réponses sur les informations fournies.
                                Si une information est indisponible, indiquez-le poliment sans inventer.
                                Évitez les répétitions et les hésitations inutiles.
                                Parlez de manière naturelle et professionnelle.
                            """

    def get_system_prompt(self, language="fr"):
        """Get the system prompt in the specified language"""
        return self.system_prompt


# Initialize the configuration
rag_config = RAGConfig()
