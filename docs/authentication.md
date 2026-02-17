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

### Keycloak Development Setup

For testing external authentication with Keycloak, use the development compose file alongside the main development environment:

```bash
# Start the development environment first
docker compose -f compose.dev.yml up -d --build

# Start Keycloak
docker compose -f compose.keycloak.dev.yml up -d
```

Keycloak is available at `http://localhost:8080` with the admin credentials defined in `compose.keycloak.dev.yml`. Configure a realm and client to issue JWTs that the sapporo-service can verify.

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
