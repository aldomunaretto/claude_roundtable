FROM python:3.12-slim

WORKDIR /app

# Install uv (project's package manager)
RUN pip install --no-cache-dir uv

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy project source
COPY main.py ./
COPY backend ./backend

RUN uv sync --frozen

EXPOSE 8001

CMD ["uv", "run", "python", "-m", "backend.main"]
