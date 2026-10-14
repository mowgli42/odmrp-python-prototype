FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml ./backend/
COPY backend/odmrp_sim ./backend/odmrp_sim
RUN pip install --no-cache-dir ./backend
COPY java-node/dist/odmrp-java-node.jar /opt/odmrp/odmrp-java-node.jar
COPY docker/odmrp-node/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV ODMRP_IMPL=java \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENTRYPOINT ["/entrypoint.sh"]
