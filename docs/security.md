# Security Audit: Authentication and Credential Handling

Audit scope: authentication and authorization, AI credential encryption, secret handling, GitHub webhook signatures, auth-provider isolation, environment-specific auth safety, and session/token security.

| Audit area | Outcome | Evidence and findings |
| --- | --- | --- |
| Authentication | Pass | Protected user routes resolve identities through the configured `AuthProvider`. The Clerk adapter delegates token signature, expiry, and claim validation to the Clerk SDK; invalid identities fail closed. |
| Authorization | Pass | Resource routes scope access to the authenticated internal user. Repository, finding, and connection lookups use ownership-scoped 404 behavior; notification mutations mask cross-user access as 404, covered by an integration test. |
| Encryption | Pass | AI API keys are Fernet-encrypted before persistence. The encryption key is validated at settings load, decryption errors expose a generic message, and API status responses omit the key. |
| Secret handling | Finding fixed | Scheduler credentials are configured as `SecretStr`, compared with `compare_digest`, and are not included in responses or logs. Non-ASCII request headers previously raised during string comparison; comparison now uses UTF-8 bytes and fails closed. |
| Webhook signature validation | Finding fixed | GitHub webhooks verify the raw body with HMAC-SHA256 and constant-time comparison before parsing. A non-ASCII digest previously could raise during comparison; malformed digests now return invalid and the endpoint responds 401. |
| Authentication-provider isolation | Pass | User identities are mapped by both external ID and provider. GitHub App JWTs and installation tokens are used only for GitHub API access. The GitHub installation callback independently requires Clerk-backed user authentication and verifies a signed, expiring state token bound to that user. GitHub authorization is never used as a substitute for Clerk authentication. |
| Environment-specific authentication safety | Pass | Production settings reject the development auth provider and require Clerk verification configuration, a non-default session signing key, and a scheduler secret. The provider factory also blocks development auth outside development/test. |
| Session/token security | Pass | Development sessions use signed SessionMiddleware cookies and the development adapter is unavailable in production. Clerk validates its session tokens; GitHub install state is signed, expires after its configured TTL, and is checked against the authenticated user. |

Regression coverage added for malformed non-ASCII webhook signatures and scheduler shared-secret headers. Existing auth-enforcement, tenant-ownership, webhook, credential-encryption, and provider-isolation tests cover the remaining audited controls.