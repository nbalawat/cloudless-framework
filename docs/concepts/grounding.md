# Grounding & retrieval

Gemini models can ground generation against external knowledge. cloudless
exposes this via a single `grounding=` kwarg on `cloudless.LLM`:

## Google Search

```python
llm = cloudless.LLM(model="gemini-flash", grounding=True)
text = await llm.invoke("When did Apollo 11 land on the moon?")
# Response includes citation metadata for the search results consulted
```

## Custom datastore (Vertex AI Search)

```python
DATASTORE = "projects/123/locations/global/collections/default_collection/dataStores/my-docs"

llm = cloudless.LLM(model="gemini-flash", grounding=DATASTORE)
text = await llm.invoke("What does our onboarding doc say about refunds?")
```

The model retrieves from your Discovery Engine corpus instead of (or in
addition to) Google Search.

## When to use which

| Use case                                      | Grounding mode                            |
|-----------------------------------------------|-------------------------------------------|
| Current events, sports, weather               | `grounding=True` (Google Search)          |
| Internal documentation, contracts, policies   | `grounding="<datastore-resource-name>"`   |
| Both                                          | Two separate calls; merge in your agent   |
| Don't ground — answer from training only      | `grounding=False` (default)               |

## Provisioning the datastore

cloudless does not manage Discovery Engine datastores — provisioning is
multi-step (parser config, ingestion mode, search-tier) and best done
once via the GCP console or Terraform. Once the datastore exists, drop
its resource name into your `cloudless.LLM` call.

Datastore resource name format:

```
projects/<project-num>/locations/<location>/collections/default_collection/dataStores/<datastore-id>
```

`location` is typically `global`, `us`, or `eu`.

## Citation metadata

When grounding is enabled, the LLM response includes citation metadata.
At v0.x, cloudless surfaces this as the raw text response — the citation
extraction helper is on the roadmap. Inspect `resp.candidates[0].grounding_metadata`
directly via the underlying SDK if you need it now.
