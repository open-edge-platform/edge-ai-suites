# Testing and Coverage

The sample application uses **pytest** for unit testing. Test files are located in the `tests/` directory under the `app/` folder.

## Install Test Dependencies

```bash
cd app
uv sync --group test
```

## Run All Tests

```bash
uv run pytest
```

## Run a Specific Test File

```bash
uv run pytest tests/test_main.py
```

## Run Tests with Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=term-missing
```

## Generate an HTML Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=html
```

Open `htmlcov/index.html` in a browser to view the detailed coverage report.
