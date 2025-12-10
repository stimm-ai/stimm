# Installation

This guide will help you install and set up the Stimm Platform for local development and production deployment.

## Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose
- [uv](https://docs.astral.sh/uv/) (for local development, optional but recommended)
- Python 3.10 or higher (if running backend locally)
- Node.js 18+ (if running frontend locally)

## Quick Start with Docker

The easiest way to run Stimm is using Docker Compose.

```bash
# Clone the repository
git clone https://github.com/stimm/stimm.git
cd stimm

# Create environment files
cp .env.example .env
cp docker/stimm/.env.example docker/stimm/.env
cp src/front/.env.example src/front/.env

# Build and start all services
docker-compose up --build
```

Once the services are up, you can access:

- **Frontend**: http://front.localhost
- **API Documentation**: http://api.localhost/docs
- **Traefik Dashboard**: http://localhost:8080

> [!NOTE]
> `front.localhost` and `api.localhost` should automatically resolve to `127.0.0.1` on most modern systems. If they do not, you can access the services directly via:
> - Frontend: http://localhost:3000
> - API: http://localhost:8001

## Local Development Setup

If you prefer to run services locally for development, follow these steps.

### 1. Start Supporting Services

Start the required infrastructure services (PostgreSQL, Qdrant, Redis, LiveKit, etc.) using Docker Compose:

```bash
docker compose up -d postgres qdrant traefik livekit redis sip
```

### 2. Set Up Python Environment

Using uv (recommended):

```bash
# Install dependencies
uv sync --group dev --group docs

# Set up environment files and Python path (optional)
./scripts/setup_env.sh
```

### 3. Run Backend Locally

```bash
uv run python -m src.main
```

The backend will be available at http://localhost:8001.

### 4. Run Frontend Locally

In a separate terminal:

```bash
cd src/front
npm install
npm run dev
```

The frontend will be available at http://localhost:3000.

## Database Initialization

When starting from scratch, the PostgreSQL database needs to have its schema created. The **stimm Docker image automatically runs migrations on startup** (via an entrypoint script). This means you don't need to run any manual migration steps when using Docker Compose.

If you are running the backend locally (without Docker), you can run migrations manually:

```bash
uv run alembic upgrade head
```

After migrations are applied, the database will contain the necessary tables (`agents`, `users`, `rag_configs`, etc.) and a default system user.

**Note:** If you encounter errors about missing tables, ensure migrations have been run. You can check the current migration version with:

```bash
docker compose exec postgres psql -U stimm_user -d stimm -c "SELECT * FROM alembic_version;"
```

## Next Steps

- [Quick Start](quick-start.md) – Run your first voice conversation.
- [Configuration](configuration.md) – Learn about environment variables and configuration options.
