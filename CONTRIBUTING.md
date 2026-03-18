# Contributing

## Development workflow

1. Create a Python 3.11+ environment.
2. Install the project in editable mode with dev dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

3. Run checks before opening a pull request:

```bash
make format
make lint
make typecheck
make test
```

## Project expectations

- Keep provenance attached to every extracted statement.
- Prefer small, typed modules over monolithic notebooks.
- Do not hardcode local institutional paths.
- Add tests for normalizers, extractors, and query behavior when changing them.
- Preserve backend abstraction boundaries so Neo4j, NetworkX, and future graph stores remain swappable.

## Pull requests

- Explain the problem, the change, and the validation performed.
- Include schema or output examples when modifying graph/query behavior.
- Note any assumptions about upstream parsed JSON structure.
