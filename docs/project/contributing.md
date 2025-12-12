# Contributing

Thank you for your interest in contributing to Stimm! This document outlines the process for contributing code, documentation, bug reports, and feature requests.

## Code of Conduct

We expect all contributors to adhere to our Code of Conduct. Please be respectful and inclusive.

## How to Contribute

### 1. Reporting Bugs

If you find a bug, please open an issue on GitHub with the following information:

- A clear, descriptive title.
- Steps to reproduce the bug.
- Expected behavior.
- Actual behavior.
- Environment details (OS, Python version, Docker version, etc.).
- Any relevant logs or screenshots.

### 2. Suggesting Features

We welcome feature suggestions! Open an issue and describe:

- The problem you're trying to solve.
- Your proposed solution.
- Any alternative solutions you've considered.

### 3. Contributing Code

#### Fork and Clone

1. Fork the repository on GitHub.
2. Clone your fork locally:

```bash
git clone https://github.com/your‑username/stimm.git
cd stimm
```

#### Set Up Development Environment

Follow the [Development Guide](../developer-guide/development.md) to install dependencies and start supporting services.

#### Create a Branch

Create a feature branch:

```bash
git checkout -b feature/your‑feature‑name
```

#### Make Changes

- Write code that follows the existing style (see [Code Style](#code‑style)).
- Add tests for your changes (see [Testing Guide](../developer-guide/testing.md)).
- Update documentation if needed.

#### Commit Your Changes

Use descriptive commit messages. We follow the [Conventional Commits](https://www.conventionalcommits.org/) style.

Example:

```
feat: add support for OpenAI TTS provider
fix: resolve audio clipping in VAD service
docs: update installation instructions
```

#### Push and Open a Pull Request

Push your branch to your fork and open a pull request against the `main` branch of the upstream repository.

### 4. Review Process

- A maintainer will review your PR and may request changes.
- Ensure all CI checks pass (tests, linting, etc.).
- Once approved, a maintainer will merge your PR.

## Code Style

### Python

- Use **ruff** for formatting, import sorting, and linting (replaces black, isort, and flake8).
- Type hints are encouraged (use `mypy` for verification).

You can run the formatting and linting scripts:

```bash
# Format code (replaces black + isort)
uv run ruff format src/

# Lint code and auto-fix issues (replaces flake8)
uv run ruff check --fix src/

# Or use the convenient lint script that does both:
uv run lint
```

### TypeScript/React

- Use the existing ESLint configuration (`npm run lint` in `src/front`).
- Follow the React patterns used elsewhere in the codebase.

## Testing

All new code should be accompanied by tests. See the [Testing Guide](../developer-guide/testing.md) for details.

## Documentation

If your change affects user‑facing behavior, please update the relevant documentation:

- Docstrings for Python modules.
- Markdown files in `docs/`.
- README.md if necessary.

## License

By contributing to Stimm, you agree that your contributions will be licensed under the project's [AGPL v3 license](LICENSE). You also agree to the [Contributor License Agreement (CLA)](../README.md#contributing-cla) outlined in the README.

## Questions?

If you have questions or need help, feel free to open an issue.
