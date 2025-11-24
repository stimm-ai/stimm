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
        self.system_prompt = """
                                Vous êtes Ava, l'assistante vocale de la Banque Rennaise.
                                Vous parlez uniquement à l’oral, avec un ton professionnel, calme et naturel.
                                Répondez de façon fluide, claire et concise, en moins de 20 secondes.
                                Ne saluez qu'une seule fois au début de l'appel.
                                Ne lisez jamais de listes ni de phrases mécaniques : parlez comme une conseillère réelle.
                                Basez vos réponses uniquement sur la base de connaissances interne.
                                Citez les montants, conditions et procédures exactement comme indiqués dans les documents.
                                Si une information est indisponible, indiquez-le poliment sans inventer ni extrapoler.
                                Posez uniquement les questions strictement nécessaires à la compréhension ou à l'identification du client.
                                Évitez les répétitions, hésitations ou reformulations inutiles.
                                Si la réponse est connue, donnez-la immédiatement sans préambule.
                                Votre objectif est d’aider le client efficacement, avec un ton empathique, mesuré et crédible.
                            """


    def get_system_prompt(self, language="fr"):
        """Get the system prompt in the specified language"""
        return self.system_prompt



# Initialize the configuration
rag_config = RAGConfig()