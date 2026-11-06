FROM python:3.12-slim
ARG VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="mcp-skills" \
      org.opencontainers.image.source="https://github.com/sellest/mcp-skills" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SKILLS_DATA_DIR=/data/skills
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --uid 10001 --create-home skills \
    && install -d -o skills -g skills /data/skills
USER skills
VOLUME ["/data/skills"]
EXPOSE 6004
CMD ["mcp-skills"]
