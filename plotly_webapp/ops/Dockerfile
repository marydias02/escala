# FROM git.ltplabs.net:5050/libs/custom-docker-images/py-3.11-slim-uv

# ARG UV_INDEX_LTPYPI_USERNAME="gitlab-ci-token"
# ARG UV_INDEX_LTPYPI_PASSWORD

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# ENV PATH="/root/.local/bin:$PATH"

# RUN apt-get update && apt-get install --no-install-recommends -y curl build-essential

# WORKDIR /app

# COPY pyproject.toml uv.lock .python-version ./
# RUN uv sync

# # Copy the contents of app
# COPY . .

# # Run command
# CMD ["uv", "run", "gunicorn", "-b", "0.0.0.0:8050", "-w", "1", "-t", "60", "app:app"]