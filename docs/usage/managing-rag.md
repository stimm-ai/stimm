# Managing RAG Configurations

Retrieval-Augmented Generation (RAG) allows Stimm agents to answer questions based on your own documents. This guide explains how to create, configure, and manage RAG configurations.

## What is a RAG Configuration?

A RAG configuration defines:

- **Provider** – Which vector database to use (Qdrant.Internal).
- **Collection/Index** – The name of the vector collection where documents are stored.
- **Embedding model** – The sentence-transformer model used to convert text into vectors.
- **Retrieval parameters** – Top-k, similarity threshold, etc.
- **Ultra-low-latency mode** – Optimizations for real-time retrieval.

Each configuration can be associated with one or more agents, enabling per-agent knowledge bases.

## Creating a RAG Configuration

### Via Web Interface

1. Navigate to **RAG** in the sidebar.
2. Click **Create RAG Configuration**.
3. Select a provider from the dropdown. The form will dynamically show the required fields for that provider.

   **Common fields:**
   - **Name** – A descriptive name (e.g., “Product-Docs”, “Internal-Wiki”).
   - **Description** – Optional.
   - **Collection Name** – The vector collection (will be created if it doesn’t exist).
   - **Embedding Model** – Pre-trained model from Hugging Face (e.g., `all-MiniLM-L6-v2`).
   - **Top-K** – Number of chunks to retrieve per query (default 5).
   - **Ultra-low-latency** – Check to enable caching and parallel retrieval.

4. Click **Save**. The configuration is now ready for document ingestion.

### Via API

```bash
curl -X POST "http://api.localhost/api/rag-configs/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product-Docs",
    "provider": "qdrant.internal",
    "config": {
      "collection_name": "product_docs",
      "embedding_model": "all-MiniLM-L6-v2",
      "top_k": 5,
      "ultra_low_latency": true
    }
  }'
```

## Uploading Documents

Once a RAG configuration exists, you can upload documents to it.

### Supported Formats

- PDF (.pdf)
- Microsoft Word (.docx)
- Markdown (.md)
- Plain text (.txt)

### Upload via Web Interface

1. Go to the RAG configuration details page (click on the configuration name).
2. Switch to the **Documents** tab.
3. Drag and drop files or click **Upload Documents**.
4. After upload, the system will automatically chunk, embed, and store the documents in the vector database. Progress is shown in the UI.

### Upload via API

```bash
curl -X POST "http://api.localhost/api/rag-configs/{config_id}/documents" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

## Setting a Default Configuration

One RAG configuration can be marked as the default. Agents that do not have an explicit RAG configuration will use the default.

To set a configuration as default:

1. In the RAG list, click the **Set as Default** button next to the configuration.
2. Confirm the action.

You can also use the API endpoint `PUT /api/rag-configs/{id}/set-default`.

## Editing a Configuration

You can edit any field of a RAG configuration except the provider (changing the provider would require re-ingesting all documents). To edit:

1. Click the edit icon (✏️) next to the configuration.
2. Modify the fields and save.

## Deleting a Configuration

Deleting a RAG configuration also removes all associated documents from the vector database. This action cannot be undone.

1. Click the delete icon (🗑) next to the configuration.
2. Confirm deletion.

## Monitoring Ingestion Status

After uploading documents, you can check ingestion status via the **Documents** tab. Each document shows its processing state (pending, processing, completed, error). Errors are logged and displayed.

## Using RAG with Agents

When creating or editing an agent, you can select a RAG configuration from the dropdown. The agent will then use that configuration for retrieval during conversations.

If you change an agent’s RAG configuration, existing conversations continue with the previous configuration; new conversations will use the new one.

## Performance Tuning

- **Embedding model**: Smaller models are faster but less accurate. Choose based on your latency/accuracy trade-off.
- **Top-K**: Higher values increase recall but also latency.
- **Ultra-low-latency**: Enable if you need sub-second retrieval. This pre-loads the embedding model and caches frequent queries.
- **Chunk size**: The system uses a default chunk size of 512 tokens. This is not configurable via the UI but can be adjusted by modifying the ingestion code.

## Troubleshooting

- **“Collection not found”**: Ensure the collection name matches exactly what the provider expects.
- **“Embedding model download failed”**: Check network connectivity and Hugging Face token (if required).
- **“No results retrieved”**: Verify that documents have been successfully ingested and that the query is relevant.

## Next Steps

- Learn about [Managing Agents](managing-agents.md).
- Explore the [Architecture](../developer/architecture-overview.md) to understand how RAG fits into the pipeline.
- Read the [API Reference](../api-reference/rest.md) for programmatic management.
