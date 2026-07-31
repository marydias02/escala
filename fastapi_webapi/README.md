# Backend API

### Quick Start

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Set up environment variables**:
   Create a `.env` file in the backend directory with required configuration.

3. **Run the development server**:
   ```bash
   uv run python -m app.main
   or
   uv run uvicorn api.main:app --reload --app-dir src
   ```
   The API will be available at `http://localhost:8000`
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
backend/
├── src/
│   └── api/
│       ├── dependencies/                # FastAPI dependency injections
│       ├── models/                      # Database models (schema source of truth)
│       ├── repositories/                # Data access layer (DAL)
│       ├── services/                    # Business logic layer
│       ├── routers/                     # FastAPI route handlers
│       ├── messages/                    # Message/event handling
│       ├── __init__.py
│       ├── main.py                      # FastAPI application
│       ├── properties.py                # Configuration and settings
│       └── development.py               # Development only scripts & utilities
├── pyproject.toml                       # Project metadata, dependencies, and tool config
└── README.md                            # This file
```

### Project Structure Legend

- **models/**: Database models that define your database schema. 
- **repositories/**: Data access layer handles all database queries and interactions.
- **services/**: Business logic layer contains core application logic independent of FastAPI.
- **routers/**: FastAPI route handlers define API endpoints and request/response schemas.
- **dependencies/**: FastAPI dependency injection for shared logic (auth, services, database sessions).
- **messages/**: Event/message handling for async operations, pub/sub patterns, or event streaming.

## Development

### Code Quality with Ruff

Ruff is an extremely fast Python linter and code formatter. It combines the functionality of multiple code quality tools (black, isort, flake8, etc.) into a single, blazing-fast tool.

#### Installation

Ruff is already included in the `dev` dependency group. Ensure it's installed:

```bash
uv sync --group dev
```

#### Format on Save in VS Code (Recommended)

To enable automatic formatting and linting when you save a file:

**1. Install the Ruff VS Code Extension**:
   - Open VS Code
   - Go to Extensions (Ctrl+Shift+X or Cmd+Shift+X on Mac)
   - Search for "Ruff"
   - Install the official extension by Astral

**2. Configure Autosave**:
   - Open VS Code
   - Go to Settings (Ctrl+,)
   - Search for "Format on Save" and enable it!

**3. Verify Setup**:
   - Create a new Python file.
   - Create formatting violations, for example:
     ```python
     import os
     import sys
     x=1  # Missing spaces around operator
     def    test():  # Extra spaces
         pass
     ```
   - Save the file (Ctrl+S)
   - Ruff should auto-fix the file

#### Running Ruff Locally

**Check for linting issues**:
```bash
uv run ruff check
```

**Auto-fix linting issues**:
```bash
uv run ruff check --fix
```

**Format code** (like Black):
```bash
uv run ruff format
```

**Combined check and format**:
```bash
uv run ruff check --fix && uv run ruff format
```


## Dev Commands

### Generate API Key

Generate a secure API key with its hash:

```bash
uv run generate_api_key
```

Output:
```json
{"HASHED_API_KEY": "argon2 hash", "X-API-KEY": "your-api-key"}
```


## Environment Variables

Create a `.env` file in the backend directory with required variables:

```
DATABASE_URL=postgresql://user:password@localhost:5432/database
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

## Troubleshooting

### Ruff Issues

**Ruff not formatting on save**:
- Verify the extension is installed: Extensions → Search "Ruff" → Install by Astral
- Check that `editor.formatOnSave` is `true` in settings
- Ensure Python default formatter is set to `astral-sh.ruff`
- Restart VS Code

**Ruff conflicts with other tools**:
- Disable Black, autopep8, and other formatters
- Remove conflicting formatter extensions
- Set only Ruff as the default Python formatter

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Ruff VS Code Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)
