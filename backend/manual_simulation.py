import os
import sys
import traceback

def simulate(env_vars):
    os.environ.clear()
    # Basic required env vars
    os.environ["GITHUB_APP_ID"] = "123"
    os.environ["GITHUB_APP_SLUG"] = "test"
    os.environ["GITHUB_APP_PRIVATE_KEY"] = "test-key"
    os.environ["GITHUB_APP_WEBHOOK_SECRET"] = "test-secret"
    os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    os.environ["DATABASE_URL"] = "sqlite:///test.db"

    for k, v in env_vars.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
            
    try:
        from app.core.config import Settings
        settings = Settings(_env_file=None)
        
        import app.core.config
        app.core.config.settings = settings
        from app.auth.factory import get_auth_provider
        
        provider = get_auth_provider()
        return True, f"{settings.auth_provider} | {type(provider).__name__}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

def run_simulation():
    with open('sim_out2.txt', 'w', encoding='utf-8') as f:
        errors = 0
        
        f.write("Scenario 1: production + valid Clerk config\n")
        ok, msg = simulate({"APP_ENV": "production", "AUTH_PROVIDER": "clerk", "CLERK_SECRET_KEY": "sk_live_123", "SESSION_SECRET_KEY": "override", "SCHEDULER_SHARED_SECRET": "sched123"})
        f.write(f"Result: {ok} - {msg}\n")
        if not ok or "ClerkAuthAdapter" not in msg:
            f.write("ERROR: Scenario 1 failed!\n")
            errors += 1

        f.write("\nScenario 2: production + missing Clerk config\n")
        ok, msg = simulate({"APP_ENV": "production", "AUTH_PROVIDER": "clerk", "SESSION_SECRET_KEY": "override", "SCHEDULER_SHARED_SECRET": "sched123"})
        f.write(f"Result: {ok} - {msg}\n")
        if ok:
            f.write("ERROR: Scenario 2 failed (should have failed closed)!\n")
            errors += 1

        f.write("\nScenario 3: production + development provider\n")
        ok, msg = simulate({"APP_ENV": "production", "AUTH_PROVIDER": "development", "SESSION_SECRET_KEY": "override", "SCHEDULER_SHARED_SECRET": "sched123"})
        f.write(f"Result: {ok} - {msg}\n")
        if ok:
            f.write("ERROR: Scenario 3 failed (should have failed closed)!\n")
            errors += 1

        f.write("\nScenario 4: test + development provider\n")
        ok, msg = simulate({"APP_ENV": "test", "AUTH_PROVIDER": "development"})
        f.write(f"Result: {ok} - {msg}\n")
        if not ok or "DevelopmentAuth" not in msg:
            f.write("ERROR: Scenario 4 failed!\n")
            errors += 1

        if errors > 0:
            sys.exit(1)
        else:
            f.write("\nAll manual scenarios passed!\n")

if __name__ == "__main__":
    run_simulation()
