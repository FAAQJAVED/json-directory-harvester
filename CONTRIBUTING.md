# Contributing to JSON Directory Harvester

Thank you for considering a contribution. Here is everything you need to know.

---

## Quick start

```bash
git clone https://github.com/FAAQJAVED/json-directory-harvester.git
cd json-directory-harvester
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v        # all 102 tests must pass before you open a PR
ruff check .            # linter must report zero issues
```

---

## What to work on

Check the [Issues](https://github.com/FAAQJAVED/json-directory-harvester/issues) tab.
Issues labelled **good first issue** are well-scoped starting points.

Before starting large changes, open an issue first so we can align on approach.

---

## Ground rules

| Rule | Detail |
|---|---|
| **Tests must pass** | Run `pytest tests/ -v` before every commit. All 102 existing tests must stay green. |
| **Linter must pass** | Run `ruff check .` before every commit. Zero issues required. |
| **New behaviour = new test** | Any bug fix or feature must include a test that proves it works. |
| **Pure-function tests only** | Tests must not open a browser, hit a real API, or require credentials. |
| **One concern per PR** | A PR fixing a bug should not also refactor unrelated code. |
| **Config-driven, not code-driven** | New features must be controlled by `config.yaml` — no hardcoded strings in source files. |

---

## Code style

- **Python 3.9+** — no walrus operator in tests, f-strings are fine
- **Type hints** on all public functions
- **Docstrings** on all public functions with `Args:` and `Returns:`
- **Line length** — 100 characters max (enforced by ruff)

---

## Adding a test

All tests use pytest. Follow the class + method pattern in existing test files:

```python
class TestMyNewFeature:

    def test_it_does_the_thing(self):
        result = my_function("input")
        assert result == "expected output"

    def test_it_handles_empty_input(self):
        assert my_function("") == ""
```

Tests needing temporary files must use `tmp_path`:

```python
def test_saves_to_disk(self, tmp_path):
    path = tmp_path / "output.json"
    save_something(str(path))
    assert path.exists()
```

Tests calling external APIs must mock them:

```python
from unittest.mock import MagicMock, patch

def test_fetch_returns_records(self):
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"id": "1", "name": "ACME"}]}
    mock_response.raise_for_status.return_value = None

    with patch("fetcher.requests.post", return_value=mock_response):
        records = fetch_all_records(config)
    assert len(records) == 1
```

Run the full suite before opening a PR:

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Commit message format

```
<type>: <short summary in sentence case>
```

Types: `fix` · `feat` · `test` · `docs` · `refactor` · `chore`

Examples:
```
fix: handle empty response_path in _navigate_response
feat: add inter_page_delay to runtime config
test: cover SCRAPER_API_KEY env var override in test_config
docs: add macOS keyboard permissions note to Troubleshooting
chore: add macos-latest to CI matrix
```

---

## Submitting a PR

1. Fork and create a branch: `git checkout -b fix/your-description`
2. Make your changes
3. Run `pytest tests/ -v` — all green
4. Run `ruff check .` — zero issues
5. Push and open a PR against `main`

---

## Extending the config schema

If you add a new runtime setting:

1. Add it to `config.yaml.example` with a comment explaining the key, type, and effect
2. Read it with `.get("key_name", default_value)` in the relevant source file
3. Document it in the Configuration Reference table in `README.md`
4. Add a test in `tests/test_config.py` confirming the default applies when the key is absent

---

## License

MIT © 2026 [FAAQJAVED](https://github.com/FAAQJAVED)
