# AI BYOK providers

The existing per-user AI connection now accepts Gemini or Groq. The API key is validated, Fernet-encrypted into the existing `ai_connections` row, and never returned from the status endpoint. Settings model/key validation checks provider metadata; it does not prove that a content-generation request succeeds.

This work does not explain or fix the previously observed Gemini repository-summary 503; its cause remains unconfirmed.

Groq is called through `https://api.groq.com/openai/v1`, using `GET /models` for key and selected-model metadata checks and `POST /chat/completions` with JSON Schema response formatting for generations. The provider validates returned JSON against the application's Pydantic response models. Supported Groq selections are `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, and `qwen/qwen3.8-27b`. All are listed by Groq as supporting structured outputs. Groq's strict schema mode currently lists these models (and Muse Spark Open); this integration uses best-effort schema mode to retain compatibility with the existing optional bot response fields, then validates locally.

## Quota controls

The defaults are deliberately conservative and configurable with:

| Setting | Default |
| --- | ---: |
| `AI_USER_REQUESTS_PER_MINUTE` | 8 |
| `AI_GLOBAL_REQUESTS_PER_MINUTE` | 60 |
| `AI_PROVIDER_MODEL_REQUESTS_PER_MINUTE` | 30 |
| `AI_GLOBAL_CONCURRENCY` | 8 |
| `AI_USER_CONCURRENCY` | 2 |
| `AI_REQUEST_TIMEOUT_SECONDS` | 20 |
| `AI_MAX_INPUT_CHARS` | 24000 |
| `AI_MAX_OUTPUT_TOKENS` | 900 |
| `AI_CACHE_TTL_SECONDS` | 120 |
| `AI_CACHE_MAX_ENTRIES` | 256 |
| `AI_RETRY_BASE_DELAY_SECONDS` / `AI_RETRY_MAX_DELAY_SECONDS` | 0.25 / 2 |

Successful generation results are cached in a bounded process-local LRU with TTL and deduplicated while in flight. Cache keys include user and authorized repository IDs, connection revision, provider/model, feature/schema version, parameters, and a SHA-256 digest of bounded input; raw API keys are never used in cache identifiers. Authorization is checked before calls reach the cache. Failures are not cached. Provider generation attempts, including retries, consume local request budgets. Groq retry handling honors `Retry-After` within the configured maximum and uses exponential backoff with jitter otherwise. Groq rate-limit response headers are used to pause a model after its reported request/token window reaches zero.

These controls, the cache, cooldown state, and concurrency limits are process-local. Multi-worker or multi-instance deployments do not share them; configure equivalent limits at a trusted ingress or move state to a shared store before relying on fleet-wide enforcement. The provider's own account/org limits remain authoritative.

## Official documentation checked 2026-10-20

- [Groq API overview and OpenAI-compatible base URL](https://console.groq.com/docs/overview)
- [Groq Structured Outputs and supported models](https://console.groq.com/docs/structured-outputs)
- [Groq model catalog and model IDs](https://console.groq.com/docs/models)
- [Groq rate limits and response headers](https://console.groq.com/docs/rate-limits)
- [Groq quickstart and API-key creation](https://console.groq.com/docs/quickstart)
- [Groq billing FAQ and Free tier information](https://console.groq.com/docs/billing-faqs)

Groq's quickstart requires an API key created in a Groq account, and its billing FAQ documents a Free tier. The official rate-limits page says limits are organization-level and the exact account limits are shown in the account Limits page; its displayed tables are explicitly a high-level summary with exceptions. Groq's model catalog currently shows some models as priced per token and some as enterprise/contact-sales. A Free tier is not a promise of unlimited usage, availability, or access to every model; the integration does not assert that every selected model is free for every account. Check current account plan and model limits before enabling generation. No paid calls or paid dependencies are required by this integration.
