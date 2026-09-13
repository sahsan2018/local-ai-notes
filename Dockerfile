FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home notes && mkdir /data && chown notes:notes /data
COPY alembic.ini ./
COPY migrations ./migrations
USER notes
ENV DATABASE_URL=sqlite:////data/notes.db
EXPOSE 8000
CMD ["uvicorn", "local_ai_notes.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
