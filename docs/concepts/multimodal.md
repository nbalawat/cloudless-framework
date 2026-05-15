# Multi-modal input

`cloudless.LLM.invoke` and `.stream` accept three media kwargs alongside
the text prompt:

| Kwarg     | Type                          | Bedrock              | Vertex Gemini      |
|-----------|-------------------------------|----------------------|--------------------|
| `images=` | `list[{data, mime_type}]`     | Nova Lite/Pro, Claude | All models        |
| `videos=` | `list[{data, mime_type}]`     | Nova Lite/Pro         | All models        |
| `audios=` | `list[{data, mime_type}]`     | Not supported (raises `InvalidInputError`) | Gemini Pro/Flash |

## Image

```python
with open("chart.png", "rb") as f:
    data = f.read()

result = await llm.invoke(
    "Describe this chart in one sentence.",
    images=[{"data": data, "mime_type": "image/png"}],
)
```

## Video

```python
result = await llm.invoke(
    "What happens in this clip?",
    videos=[{"data": video_bytes, "mime_type": "video/mp4"}],
    max_tokens=120,
)
```

Bedrock video formats: `mp4`, `webm`, `mov`, `mkv`, `flv`, `wmv`, `mpeg`, `three_gp`.

## Audio

```python
result = await llm.invoke(
    "Transcribe this voice note.",
    audios=[{"data": wav_bytes, "mime_type": "audio/wav"}],
)
```

Audio is Gemini-only. Calling Bedrock with `audios=` raises
`InvalidInputError` so the failure is obvious at the call site.

## Why bytes, not URLs

Cloud SDKs accept inline base64 or URI references. cloudless takes raw
bytes so authors don't have to build URI lists or pre-upload to GCS / S3.
For large media that would balloon a request, upload to your cloud
storage first and use the URI form via the underlying SDK directly.
