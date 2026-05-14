"""Integration tests — talk to real AWS / GCP. Per user directive: NO mocks.

Each integration test:
  - Requires actual cloud credentials (AWS profile + optional GCP SA key)
  - Costs a small amount per run (~$0.0001 per Bedrock smoke test)
  - Is marked with `@pytest.mark.integration` so unit-only runs skip them
  - Cleans up after itself if it creates any cloud resources

Run with:
  pytest tests/integration/ -v
  pytest -m integration

Skip with:
  pytest -m "not integration"
"""
