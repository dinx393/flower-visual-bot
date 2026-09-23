FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY app ./app
COPY knowledge ./knowledge

CMD ["python", "-c", "from app.agent.knowledge import knowledge_cache; from app.agent.memory import case_memory_cache; print('knowledge=' + knowledge_cache.get().version + ' memory=' + case_memory_cache.get().version)"]
