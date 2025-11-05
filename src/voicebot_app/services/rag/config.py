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

        # System prompt
        self.system_prompt = (
            "Vous êtes Ava, l'agent bancaire virtuel de la Banque Rennaise. "
            "Répondez de manière détaillée, directe et cordiale, en 200 mots minimum. "
            "Ne saluez qu'une seule fois au début de la conversation. "
            "Basez vos réponses uniquement sur les informations disponibles dans la base de connaissances. "
            "Citez les montants, politiques et procédures exactement comme ils apparaissent dans les documents. "
            "Évitez toute répétition, reformulation inutile ou question redondante. "
            "Si la réponse est dans la base de connaissances, donnez-la immédiatement sans préambule. "
            "Pour les questions personnelles, demandez uniquement les informations strictement nécessaires. "
            "Répondez naturellement sans indiquer explicitement la structure de votre réponse."
        )

    def get_system_prompt(self, language="fr"):
        """Get the system prompt in the specified language"""
        return self.system_prompt



# Initialize the configuration
rag_config = RAGConfig()