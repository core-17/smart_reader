FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies without creating a virtual environment inside the container
RUN uv sync --frozen --no-cache

# Copy the entire backend source
COPY . .

# Start the application
CMD ["uv", "run", "main.py"]
