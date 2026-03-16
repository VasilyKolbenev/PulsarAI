# Contributing to Pulsar AI

Thank you for your interest in contributing to Pulsar AI!

## Quick Start

```bash
# Clone and install
git clone https://github.com/VasilyKolbenev/LLM-forge_v1.git
cd LLM-forge_v1
pip install -e ".[dev,ui]"

# Frontend
cd ui && npm install && cd ..

# Run tests
make test
```

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature main
   ```

2. Make your changes following the code style below.

3. Run tests and linting:
   ```bash
   make test
   make lint
   ```

4. Build the frontend:
   ```bash
   make build
   ```

5. Commit with conventional messages:
   ```
   feat: add new experiment export format
   fix: correct loss calculation for DPO
   refactor: simplify pipeline callback
   docs: update API documentation
   test: add coverage for session store
   ```

6. Open a pull request against `main`.

## Code Style

### Python
- **Type hints** on all function signatures
- **PEP 8** naming conventions
- **Google-style** docstrings for public functions
- Use `logging` instead of `print()` in production code
- Maximum line length: 100 characters
- Format with `black`, lint with `ruff`

### TypeScript (Frontend)
- React functional components with hooks
- Tailwind CSS for styling
- Components in `ui/src/components/`
- Pages in `ui/src/pages/`

## Project Structure

```
src/pulsar_ai/       # Python package
  training/          # SFT, DPO training logic
  eval/              # Evaluation framework
  storage/           # SQLite persistence layer
  compute/           # SSH + remote execution
  ui/                # FastAPI backend + static files
ui/                  # React frontend (Vite + Tailwind)
tests/               # pytest test suite
docs/                # MkDocs documentation
```

## Testing

- All new features require tests
- Tests go in `tests/` mirroring source structure
- Use pytest fixtures (shared ones in `tests/conftest.py`)
- Naming: `test_<function>_<scenario>_<expected>`

```bash
make test          # Quick run
make test-cov      # With coverage report
```

## Docker

```bash
make docker        # Build image
make docker-up     # Start with compose
make docker-down   # Stop
```

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
