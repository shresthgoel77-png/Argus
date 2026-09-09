# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests\auth-protected-routes.spec.ts >> Authentication and Protected Routes >> programmatic logout revokes access
- Location: e2e\tests\auth-protected-routes.spec.ts:25:9

# Error details

```
AggregateError: apiRequestContext.post: connect ECONNREFUSED ::1:8000
connect ECONNREFUSED 127.0.0.1:8000
Call log:
  - → POST http://localhost:8000/api/v1/auth/dev-login
    - user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.8010.12 Safari/537.36
    - accept: */*
    - accept-encoding: gzip,deflate,br

```