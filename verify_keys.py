import urllib.request
import json
import base64
import sys

env_file = 'frontend/.env'
lines = open(env_file).read().split('\n')
pk = next(line.split('=')[1].strip() for line in lines if line.startswith('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY='))
sk = next(line.split('=')[1].strip() for line in lines if line.startswith('CLERK_SECRET_KEY='))

pk_padded = pk.replace('pk_test_', '')
pk_padded += '=' * (-len(pk_padded) % 4)
pk_decoded = base64.b64decode(pk_padded).decode('utf-8').rstrip('$')
print('Instance:', pk_decoded)

pk_kids = []
try:
    req = urllib.request.Request(f'https://{pk_decoded}/.well-known/jwks.json', headers={'User-Agent': 'curl/7.68.0'})
    res1 = urllib.request.urlopen(req)
    pk_kids = [k['kid'] for k in json.loads(res1.read()).get('keys', [])]
    print('PK kids:', pk_kids)
except Exception as e:
    print('PK error:', e)

sk_kids = []
try:
    req2 = urllib.request.Request('https://api.clerk.com/v1/jwks', headers={'Authorization': 'Bearer ' + sk, 'User-Agent': 'curl/7.68.0'})
    res2 = urllib.request.urlopen(req2)
    sk_kids = [k['kid'] for k in json.loads(res2.read()).get('keys', [])]
    print('SK kids:', sk_kids)
except Exception as e:
    print('SK error:', e)

if len(set(pk_kids).intersection(set(sk_kids))) > 0:
    print('VERIFIED: Keys match.')
else:
    print('MISMATCH.')
    sys.exit(1)
