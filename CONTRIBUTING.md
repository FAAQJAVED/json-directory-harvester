# Contributing

Thank you for your interest in improving JSON Directory Harvester.

## Reporting Issues

Please open a GitHub Issue and include:
- Your Python version (`python --version`)
- Your OS (Windows / macOS / Linux)
- The contents of your `config.yaml` (with real URLs/keys removed)
- The full error message or unexpected behaviour you observed

## Suggesting Features

Open a GitHub Issue with the label `enhancement`. Describe the use case
and what behaviour you would expect.

## Submitting a Pull Request

1. Fork the repository
2. Create a branch: `git checkout -b fix/your-description`
3. Make your changes
4. Run the test suite: `pytest tests/ -v`
5. Run the linter: `ruff check .`
6. Open a pull request against `main`

## Code Style

- Python 3.9+ compatible syntax only
- Type hints on all public functions
- Docstrings with `Args:` and `Returns:` on all public functions
- No hardcoded API-specific strings — everything config-driven

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=. --cov-report=term-missing
```

## License

By contributing, you agree that your contributions will be licensed
under the same MIT licence as this project.
