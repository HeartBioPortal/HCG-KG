PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install install-dev format lint typecheck test validate-sample demo clean

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev,neo4j,llm]"

format:
	ruff format src tests
	ruff check --fix src tests

lint:
	ruff check src tests

typecheck:
	mypy src

test:
	pytest -q

validate-sample:
	hcg-kg validate --profile local-dev --input-glob "data/sample/*.json"

demo:
	./scripts/run_demo.sh

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
