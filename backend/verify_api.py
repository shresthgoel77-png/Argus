import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Dev login sets the auth_token cookie
        login_resp = await client.post("/api/v1/auth/dev-login")
        print(f"POST /api/v1/auth/dev-login -> Status: {login_resp.status_code}")
        
        print("--- CONCRETE HTTP API RESULTS (AUTHENTICATED) ---")
        
        resp_count = await client.get("/api/v1/notifications/unread-count")
        print(f"GET /api/v1/notifications/unread-count -> Status: {resp_count.status_code}, Response: {resp_count.json() if resp_count.status_code == 200 else resp_count.text}")
        
        resp_list = await client.get("/api/v1/notifications")
        print(f"GET /api/v1/notifications -> Status: {resp_list.status_code}")
            
        resp_mark = await client.post("/api/v1/notifications/read-all")
        print(f"POST /api/v1/notifications/read-all -> Status: {resp_mark.status_code}")
        
        print("---------------------------------")

if __name__ == "__main__":
    asyncio.run(test_api())
