# Authentication

## Overview

The sapporo-service supports JWT-based authentication with two modes:

- **sapporo mode**: Built-in authentication with local user management. The service manages users, hashes passwords with Argon2, and issues/verifies JWTs using a local secret key. Suitable for standalone deployments.
- **external mode**: Delegates authentication to an external OpenID Connect Identity Provider (e.g., Keycloak). The service only verifies JWTs using the IdP's JWKS endpoint. Suitable for organizations with existing identity infrastructure.

When authentication is enabled, each run is associated with a username, ensuring users can only access their own runs.

### Protected Endpoints

| Endpoint | Method | Note |
|---|---|---|
| `/service-info` | GET | Optional: provides user-specific counts when authenticated |
| `/runs` | GET | |
| `/runs` | POST | |
| `/runs/{run_id}` | GET | |
| `/runs/{run_id}/cancel` | POST | |
| `/runs/{run_id}/status` | GET | |
| `/runs/{run_id}/outputs` | GET | |
| `/runs/{run_id}/outputs/{path}` | GET | |
| `/runs/{run_id}/ro-crate` | GET | |
| `/runs/{run_id}` | DELETE | |
| `/runs` | DELETE | Bulk delete (sapporo 2.1.0+) |

## auth_config.json

Configure authentication via `auth_config.json`:

```json
{
  "auth_enabled": true,
  "idp_provider": "sapporo",
  "sapporo_auth_config": {
    "secret_key": "your_secure_secret_key_here",
    "expires_delta_hours": 24,
    "users": [
      {
        "username": "user1",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$..."
      }
    ]
  },
  "external_config": {
    "idp_url": "https://keycloak.example.com/realms/your-realm",
    "jwt_audience": "account",
    "client_mode": "public",
    "client_id": "sapporo-client",
    "client_secret": "client-secret-here"
  }
}
```

Override the location using `--auth-config` or `SAPPORO_AUTH_CONFIG`.

### Configuration Fields

- `auth_enabled`: Enable/disable authentication
- `idp_provider`: `sapporo` (local) or `external` (IdP like Keycloak)
- `sapporo_auth_config`:
  - `secret_key`: JWT signing key (must be strong, see [Secret Key Generation](#secret-key-generation))
  - `expires_delta_hours`: JWT expiration time in hours (default: 24, max: 168)
  - `users`: List of users with `username` and `password_hash`
- `external_config`:
  - `idp_url`: External IdP URL (must use HTTPS in production)
  - `jwt_audience`: Expected JWT audience claim
  - `client_mode`: `confidential` or `public`
  - `client_id`/`client_secret`: OAuth2 credentials for confidential mode

## Sapporo Mode

For local authentication:

```bash
# Start the service
sapporo

# Get JWT token
TOKEN=$(curl -s -X POST \
    -H "Content-Type: multipart/form-data" \
    -F "username=user1" \
    -F "password=yourpassword" \
    localhost:1122/token | jq -r '.access_token')

# Verify token
curl -X GET -H "Authorization: Bearer $TOKEN" localhost:1122/me

# Access protected endpoints
curl -X GET -H "Authorization: Bearer $TOKEN" localhost:1122/runs
```

## External Mode

In external mode, integrate with an IdP like Keycloak. Users authenticate with the IdP, which issues JWTs that the sapporo-service verifies.

### Security Considerations

The external mode enforces the following security measures when verifying JWTs issued by the IdP:

- **Algorithm restriction**: Only RS256, RS384, and RS512 are accepted. HMAC-based algorithms (e.g., HS256) are rejected to prevent key confusion attacks.
- **Issuer verification**: The `iss` claim in the JWT is validated against the `issuer` field from the IdP's OIDC Discovery metadata.
- **JWKS key rotation**: When a JWT's `kid` header does not match any cached key, the JWKS is re-fetched from the IdP. If the key is still not found after refresh, the token is rejected.
- **TTL-based caching**: OIDC Discovery metadata is cached for 1 hour. JWKS is cached for 5 minutes. This ensures timely pickup of key rotations while reducing load on the IdP.
- **HTTP timeout**: All HTTP requests to the IdP use a 10-second timeout to prevent hanging.
- **Retry with exponential backoff**: Transient HTTP errors when fetching metadata or JWKS are retried up to 3 times with exponential backoff (0.5s, 1.0s, 2.0s).

### Keycloak Development Setup

A pre-configured Keycloak realm is provided for development and testing. The realm is automatically imported on first start via `keycloak/realm-export.json`.

```bash
# Start Keycloak (realm is auto-imported)
docker compose -f compose.keycloak.dev.yml up -d

# Wait for healthcheck to pass
docker compose -f compose.keycloak.dev.yml ps

# Start sapporo with external auth
export SAPPORO_ALLOW_INSECURE_IDP=true
sapporo --auth-config auth_config.json --debug
```

Keycloak admin console: `http://localhost:8080` (sapporo-admin / `sapporo-admin-password`)

#### Pre-configured Clients

| Client ID | Type | Secret | Use case |
|---|---|---|---|
| `sapporo-service-dev` | public | N/A | Frontend direct authentication |
| `sapporo-service-dev-confidential` | confidential | `sapporo-dev-client-secret` | Server-to-server authentication |

Both clients have `directAccessGrantsEnabled: true` (Resource Owner Password Grant) for testing convenience.

#### Test Users

| Username | Password |
|---|---|
| `test-user` | `test-user-password` |
| `test-user-2` | `test-user-2-password` |

#### auth_config.json Examples

Public mode (frontend obtains tokens directly from Keycloak):

```json
{
  "auth_enabled": true,
  "idp_provider": "external",
  "sapporo_auth_config": {
    "secret_key": "unused",
    "expires_delta_hours": 24,
    "users": []
  },
  "external_config": {
    "idp_url": "http://localhost:8080/realms/sapporo-dev",
    "jwt_audience": "account",
    "client_mode": "public",
    "client_id": "sapporo-service-dev",
    "client_secret": null
  }
}
```

Confidential mode (sapporo proxies token requests to Keycloak):

```json
{
  "auth_enabled": true,
  "idp_provider": "external",
  "sapporo_auth_config": {
    "secret_key": "unused",
    "expires_delta_hours": 24,
    "users": []
  },
  "external_config": {
    "idp_url": "http://localhost:8080/realms/sapporo-dev",
    "jwt_audience": "account",
    "client_mode": "confidential",
    "client_id": "sapporo-service-dev-confidential",
    "client_secret": "sapporo-dev-client-secret"
  }
}
```

## CLI Utilities

### Password Hashing

All passwords are stored as Argon2 hashes. Generate password hashes using the CLI:

```bash
sapporo-cli hash-password
# Follow the prompts to enter and confirm your password
# Output: Password hash: $argon2id$v=19$m=65536,t=3,p=4$...
```

Or with an inline password (not recommended for interactive use):

```bash
sapporo-cli hash-password --password "your_password"
```

### Secret Key Generation

Generate a cryptographically secure secret key:

```bash
sapporo-cli generate-secret
# Output: Secret key: <44-character secure random string>
```

In production mode (non-debug), weak secret keys are rejected. Always use a generated secret key in production deployments.

## HTTPS Requirement

When using external identity providers, HTTPS is required by default. This prevents token interception during authentication flows.

To allow HTTP connections during development (not recommended for production):

```bash
export SAPPORO_ALLOW_INSECURE_IDP=true
```
