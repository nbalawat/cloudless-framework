# AgentCore A2A runtime contract:
#  - ARM64 (required by AgentCore Runtime)
#  - Container exposes the A2A server on port 9000
#  - /ping returns {"status": "Healthy"} (auto-implemented by serve_a2a)
#  - /.well-known/agent-card.json served by serve_a2a
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

# System deps kept minimal — pure Python stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

# AgentCore A2A protocol mode → port 9000
EXPOSE 9000

# serve_a2a auto-binds 0.0.0.0 when /.dockerenv is present
CMD ["python", "agent.py"]
