# Security & Quality Guide

Stimm is committed to high standards of code security and maintainability. This document outlines the tools and processes we use to ensure the platform remains secure and robust.

## Security Architecture

We use a layered approach to security:

1.  **Static Analysis (SAST)**: Scanning source code for vulnerabilities and bad practices.
2.  **Software Composition Analysis (SCA)**: Monitoring third-party dependencies for known vulnerabilities.
3.  **Automated Formatting & Linting**: Ensuring consistent code style and preventing common programming errors.

## Security Tools

### Python (Backend)

- **[Bandit](https://bandit.readthedocs.io/)**: Scans Python code for common security issues like insecure use of `subprocess`, `hardcoded passwords`, etc.
- **[Semgrep](https://semgrep.dev/)**: A highly customizable static analysis tool that finds complex security patterns across multiple languages.
- **[pip-audit](https://pypi.org/project/pip-audit/)**: Checks your current Python environment against the PyPA database of known vulnerabilities.
- **[Ruff](https://beta.ruff.rs/)**: Handles fast linting and formatting, enforcing safe coding standards.

### React (Frontend)

- **[ESLint SonarJS](https://github.com/SonarSource/eslint-plugin-sonarjs)**: Provides more than 100 rules for bug detection and code smells, specifically tailored for JavaScript and React.
- **[eslint-plugin-security](https://github.com/nodesecurity/eslint-plugin-security)**: Adds specific security rules for identifying potential vulnerabilities in JS code (e.g., regex injection, object injection).
- **npm audit**: Built-in tool to scan your `package-lock.json` for vulnerabilities in the dependency tree.

## Running Scans Locally

### Python Security Scans

```bash
# Run Bandit
uv run bandit -r src/

# Run Semgrep
uv run semgrep scan --config=auto .

# Run pip-audit
uv run pip-audit --desc
```

### Frontend Security Scans

```bash
cd src/front

# Run security-specific linting (including SonarJS)
npm run lint:security

# Run dependency audit
npm audit
```

## Git Hooks

Security checks are integrated into our [pre-commit](https://pre-commit.com/) hooks. They run automatically before every commit to prevent insecure code from entering the repository.

To install the hooks:

```bash
uv run pre-commit install
```

## Continuous Integration

Every Pull Request is scanned by GitHub Actions using the same tools listed above. A failure in any security check will block the PR from being merged.

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it following our [Security Policy](SECURITY.md).
