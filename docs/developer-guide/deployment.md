# Deployment Guide

This guide covers deploying Stimm to a production environment.

## Deployment Options

### 1. Docker Compose (Single Server)

The simplest production deployment is to run the same Docker Compose stack used for development, but with production‑ready configuration.

**Steps:**

1. Clone the repository on your server.

2. Create production environment files (do not use the example files directly). Set strong passwords, generate LiveKit API keys, and replace `localhost` URLs with your domain.

3. Adjust `docker‑compose.yml` as needed (e.g., increase resource limits, add volumes for persistent data).

4. Start the stack:

```bash
docker compose up -d --build
```

5. Set up a reverse proxy (like Traefik, already included) or Nginx to handle SSL termination and domain routing.

**Pros:** Simple, consistent with development.  
**Cons:** Not scalable, single point of failure.

### 2. Kubernetes

For scalable, high‑availability deployments, you can deploy Stimm on Kubernetes.

**Components:**

- **PostgreSQL** – StatefulSet with persistent volume.
- **Qdrant** – StatefulSet or use cloud Qdrant.
- **Redis** – StatefulSet or managed service.
- **LiveKit** – Deployment (or use LiveKit Cloud).
- **Stimm Backend** – Deployment with horizontal scaling.
- **Stimm Frontend** – Deployment or serve static files via CDN.

Example Kubernetes manifests are not yet provided but can be derived from the Docker Compose definitions.

### 3. Hybrid (Managed Services)

Use managed services for databases and AI providers to reduce operational overhead.

- **Database**: AWS RDS, Google Cloud SQL, or Azure Database for PostgreSQL.
- **Vector DB**: Qdrant Cloud or Pinecone.
- **Redis**: Elasticache, Memorystore, or Redis Cloud.
- **LiveKit**: LiveKit Cloud.

Adjust environment variables accordingly.

## Configuration for Production

### Environment Variables

Ensure the following variables are set appropriately:

```env
# Security
LIVEKIT_API_KEY=strong‑random‑key
LIVEKIT_API_SECRET=strong‑random‑secret
DATABASE_URL=postgresql://user:password@host:5432/db
REDIS_URL=redis://host:6379

# URLs (use your domain)
STIMM_API_URL=https://api.yourdomain.com
FRONTEND_URL=https://yourdomain.com
LIVEKIT_URL=wss://livekit.yourdomain.com

# Logging
LOG_LEVEL=INFO
```

### SSL/TLS

- Use Traefik with Let's Encrypt (already configured in `docker‑compose.yml`).
- Alternatively, place an Nginx proxy in front of the services and obtain SSL certificates via Certbot.

### Data Persistence

Map Docker volumes for:

- PostgreSQL data
- Qdrant storage
- Redis data
- Uploaded documents (if storing locally)

Example volume configuration in `docker‑compose.yml`:

```yaml
volumes:
  postgres_data:
  qdrant_storage:
  redis_data:
```

## Scaling

### Backend

The backend is stateless except for WebSocket connections. You can scale horizontally by running multiple backend instances behind a load balancer that supports WebSocket (e.g., Traefik, Nginx with `proxy_pass`).

Ensure that:
- **Redis** is used for shared state (session cache, SIP bridge coordination).
- **LiveKit** is configured to allow multiple backend instances to connect.

### Frontend

The frontend is a static Next.js application. You can build it and serve it via a CDN or a simple web server.

## Monitoring

### Logs

Collect logs from all containers using a centralized logging solution (e.g., ELK stack, Loki, Datadog).

### Metrics

Stimm emits Prometheus‑style metrics via the `/metrics` endpoint (if enabled). You can scrape them with Prometheus and visualize with Grafana.

### Health Checks

Each service provides a health endpoint:

- Backend: `GET /health`
- LiveKit: `GET /health` (via LiveKit API)
- PostgreSQL, Redis, Qdrant: TCP connectivity checks.

Use these endpoints for Kubernetes liveness/readiness probes or Docker healthchecks.

## Backup and Recovery

### Database Backups

Regularly backup PostgreSQL and Qdrant data.

- **PostgreSQL**: Use `pg_dump` or a managed backup solution.
- **Qdrant**: Use snapshot functionality.

### Configuration Backups

Backup your environment files, Docker Compose files, and any custom scripts.

## Upgrading

1. Pull the latest version of the Stimm repository.
2. Review changelog for breaking changes.
3. Run database migrations (if any):

```bash
docker compose exec stimm‑app uv run alembic upgrade head
```

4. Rebuild and restart services:

```bash
docker compose up -d --build
```

## Troubleshooting

### Common Issues

- **LiveKit connection failures**: Check that LiveKit API keys are correct and the LiveKit server is reachable.
- **Database migration errors**: Ensure the database is running and the connection string is correct.
- **Audio not working**: Verify that WebRTC ports (UDP 50000‑60000) are open on your firewall.

### Getting Help

If you encounter issues not covered here, please open an issue on [GitHub](https://github.com/stimm/stimm) or join our [Discord community](https://discord.gg/stimm).
