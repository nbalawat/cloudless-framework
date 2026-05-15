# Identity & authentication

cloudless ships three identity primitives for A2A peer auth.

| Identity                | Token model                  | Use when                                          |
|-------------------------|------------------------------|---------------------------------------------------|
| `CognitoIdentity`       | Long-lived M2M JWT, cached   | Cross-cloud peer calls (AWS↔GCP). Default.        |
| `SigV4Identity`         | Per-request SigV4 signature  | Peer endpoint is API Gateway / Lambda URL with IAM auth. |
| `OAuth3LOIdentity`      | Per-user OAuth access token  | Tool needs the end user's authority (e.g., Google Drive). |

## Cognito M2M (default)

```python
from cloudless.runtime import CognitoIdentity

identity = CognitoIdentity(
    domain="cloudless-spike.auth.us-east-1.amazoncognito.com",
    client_id="abc123",
    client_secret="...",
    scope="cloudless/peer",
)
```

The identity is configured once at runtime startup. `A2APeerClient`
caches tokens until ~60s before expiry.

## SigV4 (AWS-native)

```python
from cloudless.runtime import SigV4Identity

identity = SigV4Identity(service="execute-api", region="us-east-1")
```

`A2APeerClient` detects the SigV4 sentinel and signs each request
individually rather than attaching a Bearer header. Use this when peers
sit behind API Gateway / Lambda Function URLs configured for IAM auth.

## OAuth 3LO (end-user-scoped)

```python
from cloudless.runtime import OAuth3LOConfig, OAuth3LOIdentity

cfg = OAuth3LOConfig(
    provider="google",
    client_id="...",
    client_secret="...",
    authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
    token_endpoint="https://oauth2.googleapis.com/token",
    redirect_uri="https://app.example/oauth/callback",
    scopes=("https://www.googleapis.com/auth/drive.readonly",),
)
identity = OAuth3LOIdentity(cfg)
```

### Lifecycle

```python
from cloudless.runtime.identity import OAuthRequired

try:
    token = await identity.get_token(user_id=ctx.user.id)
except OAuthRequired as e:
    # No token yet — pause for user consent
    yield PauseChunk(
        reason="OAuth consent required",
        pending_action={"authorize_url": e.authorize_url, "state": e.state},
    )
    return

# After callback completes:
await identity.handle_callback(user_id=ctx.user.id, code=code, state=state)

# On next invocation, get_token returns the stored access token.
```

Tokens are stored in a pluggable `TokenStore`. Default is in-memory; for
production, plug in a `SecretsManagerTokenStore` or `FirestoreTokenStore`.

PKCE (S256) is enabled by default. Refresh tokens are automatically used
when access tokens expire.

## A2A server side

Inbound A2A requests are validated by the deploy adapter's auth envelope
(JWT for Cognito, IAM SigV4, or OAuth bearer for 3LO). `build_a2a_app`'s
`require_audience` parameter adds a light defensive check; the heavy
lifting is done by the cloud-native auth wrapper around the runtime.
