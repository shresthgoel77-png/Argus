import os
from dotenv import load_dotenv
import jwt
import time
import requests

load_dotenv()

app_id = os.getenv("GITHUB_APP_ID")
private_key = os.getenv("GITHUB_APP_PRIVATE_KEY")

if not app_id or not private_key:
    print("Missing GITHUB config")
    exit(1)

now = int(time.time())
payload = {
    # issued at time, 60 seconds in the past to allow for clock drift
    "iat": int(time.time()) - 60,
    # JWT expiration time (10 minute maximum)
    "exp": int(time.time()) + (10 * 60),
    # GitHub App's identifier
    "iss": app_id
}

encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
headers = {
    "Authorization": f"Bearer {encoded_jwt}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

response = requests.get("https://api.github.com/app/installations", headers=headers)
if response.status_code == 200:
    installations = response.json()
    print("Installations found:")
    for inst in installations:
        print(f"ID: {inst['id']}, Account: {inst['account']['login']}, Repos URL: {inst['repositories_url']}")
else:
    print(f"Failed to list installations: {response.status_code} {response.text}")
