FROM python:3.11-slim

WORKDIR /app/

# Copy bare minimum to install dependencies first
COPY ./poetry-requirements.txt ./pyproject.toml ./poetry.toml ./poetry.lock ./README.md /app/

# install poetry
RUN pip install -r poetry-requirements.txt

# install dependencies
RUN poetry install --no-root

# Copy rest of the files
COPY ./src/ /app/src/

# install app
RUN poetry install --only-root

# "activate" env used by poetry to install
ENV PATH="/app/.venv/bin:$PATH"

# disable buffering so that logs are rendered to stdout asap
ENV PYTHONUNBUFFERED=1
