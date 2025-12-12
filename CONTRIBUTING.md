# Contributing to Stimm

First off, thanks for taking the time to contribute! 🎉

We love your input! We want to make contributing to Stimm as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Development Workflow](#development-workflow)
  - [Issues](#issues)
  - [Branching Strategy](#branching-strategy)
  - [Commit Messages](#commit-messages)
  - [Pull Requests](#pull-requests)
- [Coding Standards](#coding-standards)
  - [Python](#python)
  - [Frontend (TypeScript/React)](#frontend-typescriptreact)
- [Testing](#testing)
- [Documentation](#documentation)
- [License](#license)

## Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all. Please be respectful and inclusive in all interactions.

## Getting Started

### Prerequisites

- **Python**: 3.9+
- **Node.js**: 18+ (for frontend)
- **Docker**: For running supporting services (Redis, LiveKit, etc.)
- **uv**: We use [`uv`](https://github.com/astral-sh/uv) for fast and reliable Python package management.
- **Git**: For version control.

### Installation

1.  **Fork and Clone**
    ```bash
    git clone https://github.com/YOUR_USERNAME/stimm.git
    cd stimm
    ```

2.  **Backend Setup**
    ```bash
    # Install dependencies using uv
    uv sync
    
    # Setup environment
    cp .env.example .env
    ```

3.  **Frontend Setup**
    ```bash
    cd src/front
    npm install
    cp .env.example .env.local
    ```

For detailed setup instructions, please refer to our [Development Guide](docs/developer-guide/development.md).

## Development Workflow

### Issues

Scan through our [existing issues](https://github.com/stimm-ai/stimm/issues) to find one that interests you. If you find a bug or have a feature request, please open a new issue using our templates.

### Branching Strategy

We use a simplified feature branch workflow.

1.  **Sync your fork** with the upstream repository.
2.  **Create a new branch** for your specific changes:
    ```bash
    git checkout -b type/short-description
    # Example: feat/add-openai-tts
    ```

   Use prefixes like `feat/`, `fix/`, `docs/`, `refactor/` to keep things organized.

### Commit Messages

We strictly follow **[Conventional Commits](https://www.conventionalcommits.org/)**. This helps us automate releases and changelogs.

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools

**Example**:
```text
feat(agents): add support for ElevenLabs streaming
fix(vad): resolve silence detection threshold issue
docs: update installation instructions
```

### Pull Requests

1.  **Push to your fork** and submit a Pull Request against the `main` branch.
2.  **Description**: Describe your changes clearly. Link to any relevant issues (e.g., `Fixes #123`).
3.  **Self-Review**: Look over your code one last time. Did you add comments? Did you remove debug prints?
4.  **CI Checks**: Ensure all GitHub Actions pass.

## Coding Standards

### Python

We use modern Python tooling to ensure code quality.

- **Formatter**: `black` (line length 88)
- **Import Sorter**: `isort`
- **Linter**: `flake8`
- **Type Checking**: Type hints are encouraged.

**Run checks locally**:
```bash
uv run black src/ tests/
uv run isort src/ tests/
uv run flake8 src/ tests/
```

### Frontend (TypeScript/React)

- **Linter**: `ESLint`
- **Formatter**: `Prettier` (integrated with ESLint)

**Run checks locally**:
```bash
cd src/front
npm run lint
```

## Testing

We take quality seriously. Please include tests for any new features or bug fixes.

- **Backend**: We use `pytest`.
  ```bash
  uv run pytest
  ```
- **Integration**: Check `tests/integration/` for end-to-end scenarios.

See the [Testing Guide](docs/developer-guide/testing.md) for more details.

## Documentation

- If you change a feature, update the relevant docs in `docs/`.
- If you add a new dependency, remember to update `pyproject.toml` or `package.json`.
- Docs are written in Markdown.

## License

By contributing to Stimm, you agree that your contributions will be licensed under the project's [AGPL v3 license](LICENSE).