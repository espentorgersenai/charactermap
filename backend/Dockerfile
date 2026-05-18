FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir hatch

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Install pandoc + minimal LaTeX for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-latex-base \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
