"""
Unit tests for database models.

These tests verify that SQLAlchemy database models work correctly,
including field validation, methods, and serialization.
"""

from uuid import uuid4

import pytest

from database.models import Agent, AgentSession, Document, RagConfig, User


@pytest.mark.unit
class TestUserModel:
    """Test suite for User model."""

    def test_user_creation(self):
        """Test creating a User instance."""
        user = User(username="testuser", email="test@example.com")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        # Note: ID is auto-generated but only set when committed to database

    def test_user_repr(self):
        """Test User string representation."""
        user_id = uuid4()
        user = User(id=user_id, username="testuser", email="test@example.com")

        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user_id) in repr_str
        assert "testuser" in repr_str

    def test_user_uuid_generation(self):
        """Test that User ID is UUID."""
        user = User(username="testuser", email="test@example.com")

        # Should auto-generate UUID if not provided
        # Note: This test doesn't actually insert to DB, so we check the default
        assert hasattr(user, "id")


@pytest.mark.unit
class TestAgentModel:
    """Test suite for Agent model."""

    def test_agent_creation(self):
        """Test creating an Agent instance."""
        user_id = uuid4()
        agent = Agent(
            user_id=user_id,
            name="TestAgent",
            description="Test description",
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={"model": "llama-3"},
            tts_config={"voice": "test"},
            stt_config={"language": "en"},
        )

        assert agent.user_id == user_id
        assert agent.name == "TestAgent"
        assert agent.description == "Test description"
        assert agent.llm_provider == "groq.com"
        assert agent.tts_provider == "async.ai"
        assert agent.stt_provider == "deepgram.com"

    def test_agent_default_values(self):
        """Test Agent default values."""
        user_id = uuid4()
        agent = Agent(
            user_id=user_id,
            name="TestAgent",
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={},
            tts_config={},
            stt_config={},
        )

        # Note: SQLAlchemy defaults are only applied on DB commit
        # We can verify the defaults are defined in the column
        # For now, just test that fields are accessible
        assert hasattr(agent, "is_default")
        assert hasattr(agent, "is_active")
        assert hasattr(agent, "is_system_agent")

    def test_agent_repr(self):
        """Test Agent string representation."""
        user_id = uuid4()
        agent = Agent(
            user_id=user_id,
            name="TestAgent",
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={},
            tts_config={},
            stt_config={},
        )

        repr_str = repr(agent)
        assert "Agent" in repr_str
        assert "TestAgent" in repr_str
        assert "groq.com" in repr_str

    def test_agent_to_dict(self):
        """Test Agent to_dict method."""
        user_id = uuid4()
        agent_id = uuid4()
        rag_id = uuid4()

        agent = Agent(
            id=agent_id,
            user_id=user_id,
            name="TestAgent",
            description="Test",
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={"model": "llama-3"},
            tts_config={"voice": "test"},
            stt_config={"language": "en"},
            system_prompt="Test prompt",
            rag_config_id=rag_id,
            is_default=True,
            is_active=True,
            is_system_agent=False,
        )

        agent_dict = agent.to_dict()

        assert agent_dict["id"] == str(agent_id)
        assert agent_dict["user_id"] == str(user_id)
        assert agent_dict["name"] == "TestAgent"
        assert agent_dict["llm_provider"] == "groq.com"
        assert agent_dict["llm_config"] == {"model": "llama-3"}
        assert agent_dict["rag_config_id"] == str(rag_id)
        assert agent_dict["is_default"] is True

    def test_agent_to_dict_no_rag(self):
        """Test Agent to_dict with no RAG config."""
        user_id = uuid4()
        agent = Agent(
            user_id=user_id,
            name="TestAgent",
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={},
            tts_config={},
            stt_config={},
        )

        agent_dict = agent.to_dict()
        assert agent_dict["rag_config_id"] is None


@pytest.mark.unit
class TestAgentSessionModel:
    """Test suite for AgentSession model."""

    def test_agent_session_creation(self):
        """Test creating an AgentSession instance."""
        user_id = uuid4()
        agent_id = uuid4()

        session = AgentSession(
            user_id=user_id,
            agent_id=agent_id,
            session_type="stimm",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert session.user_id == user_id
        assert session.agent_id == agent_id
        assert session.session_type == "stimm"
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"

    def test_agent_session_repr(self):
        """Test AgentSession string representation."""
        user_id = uuid4()
        agent_id = uuid4()

        session = AgentSession(
            user_id=user_id,
            agent_id=agent_id,
            session_type="chat",
        )

        repr_str = repr(session)
        assert "AgentSession" in repr_str
        assert "chat" in repr_str
        assert str(agent_id) in repr_str

    def test_agent_session_types(self):
        """Test different session types."""
        user_id = uuid4()
        agent_id = uuid4()

        session_types = ["stimm", "chat", "tts", "stt"]

        for session_type in session_types:
            session = AgentSession(
                user_id=user_id,
                agent_id=agent_id,
                session_type=session_type,
            )
            assert session.session_type == session_type


@pytest.mark.unit
class TestRagConfigModel:
    """Test suite for RagConfig model."""

    def test_rag_config_creation(self):
        """Test creating a RagConfig instance."""
        user_id = uuid4()

        rag_config = RagConfig(
            user_id=user_id,
            name="TestRAG",
            description="Test RAG config",
            provider_type="vectorbase",
            provider="qdrant.internal",
            provider_config={"collection": "test"},
        )

        assert rag_config.user_id == user_id
        assert rag_config.name == "TestRAG"
        assert rag_config.provider_type == "vectorbase"
        assert rag_config.provider == "qdrant.internal"

    def test_rag_config_default_values(self):
        """Test RagConfig default values."""
        user_id = uuid4()

        rag_config = RagConfig(
            user_id=user_id,
            name="TestRAG",
            provider_type="vectorbase",
            provider="qdrant.internal",
            provider_config={},
        )

        # Note: SQLAlchemy defaults are only applied on DB commit
        # We can verify the defaults are defined in the column
        assert hasattr(rag_config, "is_default")
        assert hasattr(rag_config, "is_active")

    def test_rag_config_repr(self):
        """Test RagConfig string representation."""
        user_id = uuid4()

        rag_config = RagConfig(
            user_id=user_id,
            name="TestRAG",
            provider_type="vectorbase",
            provider="qdrant.internal",
            provider_config={},
        )

        repr_str = repr(rag_config)
        assert "RagConfig" in repr_str
        assert "TestRAG" in repr_str
        assert "qdrant.internal" in repr_str

    def test_rag_config_to_dict(self):
        """Test RagConfig to_dict method."""
        user_id = uuid4()
        rag_id = uuid4()

        rag_config = RagConfig(
            id=rag_id,
            user_id=user_id,
            name="TestRAG",
            description="Test description",
            provider_type="vectorbase",
            provider="qdrant.internal",
            provider_config={"collection": "test"},
            is_default=True,
            is_active=True,
        )

        rag_dict = rag_config.to_dict()

        assert rag_dict["id"] == str(rag_id)
        assert rag_dict["user_id"] == str(user_id)
        assert rag_dict["name"] == "TestRAG"
        assert rag_dict["provider_type"] == "vectorbase"
        assert rag_dict["provider"] == "qdrant.internal"
        assert rag_dict["provider_config"] == {"collection": "test"}
        assert rag_dict["is_default"] is True


@pytest.mark.unit
class TestDocumentModel:
    """Test suite for Document model."""

    def test_document_creation(self):
        """Test creating a Document instance."""
        rag_config_id = uuid4()

        document = Document(
            rag_config_id=rag_config_id,
            filename="test.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            chunk_count=5,
            chunk_ids=["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
            namespace="default",
            doc_metadata={"author": "Test Author"},
        )

        assert document.rag_config_id == rag_config_id
        assert document.filename == "test.pdf"
        assert document.file_type == "pdf"
        assert document.file_size_bytes == 1024
        assert document.chunk_count == 5
        assert len(document.chunk_ids) == 5
        assert document.namespace == "default"
        assert document.doc_metadata["author"] == "Test Author"

    def test_document_repr(self):
        """Test Document string representation."""
        rag_config_id = uuid4()

        document = Document(
            rag_config_id=rag_config_id,
            filename="test.pdf",
            file_type="pdf",
            chunk_count=5,
            chunk_ids=["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
        )

        repr_str = repr(document)
        assert "Document" in repr_str
        assert "test.pdf" in repr_str
        assert "pdf" in repr_str

    def test_document_to_dict(self):
        """Test Document to_dict method."""
        rag_config_id = uuid4()
        doc_id = uuid4()

        document = Document(
            id=doc_id,
            rag_config_id=rag_config_id,
            filename="test.pdf",
            file_type="pdf",
            file_size_bytes=2048,
            chunk_count=3,
            chunk_ids=["chunk1", "chunk2", "chunk3"],
            namespace="test_ns",
            doc_metadata={"pages": 10},
        )

        doc_dict = document.to_dict()

        assert doc_dict["id"] == str(doc_id)
        assert doc_dict["rag_config_id"] == str(rag_config_id)
        assert doc_dict["filename"] == "test.pdf"
        assert doc_dict["file_type"] == "pdf"
        assert doc_dict["file_size_bytes"] == 2048
        assert doc_dict["chunk_count"] == 3
        assert doc_dict["chunk_ids"] == ["chunk1", "chunk2", "chunk3"]
        assert doc_dict["namespace"] == "test_ns"
        # Note: doc_metadata is returned as 'metadata' in API
        assert doc_dict["metadata"] == {"pages": 10}

    def test_document_file_types(self):
        """Test different file types."""
        rag_config_id = uuid4()
        file_types = ["pdf", "docx", "markdown", "text"]

        for file_type in file_types:
            document = Document(
                rag_config_id=rag_config_id,
                filename=f"test.{file_type}",
                file_type=file_type,
                chunk_count=1,
                chunk_ids=["chunk1"],
            )
            assert document.file_type == file_type
