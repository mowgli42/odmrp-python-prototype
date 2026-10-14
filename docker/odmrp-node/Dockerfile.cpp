# FakeNode stub appliance until a real C++ ODMRP port lands (issue #4).
FROM python:3.12-slim
WORKDIR /app
COPY backend/pyproject.toml ./backend/
COPY backend/odmrp_sim ./backend/odmrp_sim
RUN pip install --no-cache-dir ./backend
COPY docker/odmrp-node/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV ODMRP_IMPL=fake
LABEL odmrp.impl=cpp odmrp.stub=true
ENTRYPOINT ["/entrypoint.sh"]
