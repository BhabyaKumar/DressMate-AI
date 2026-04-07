import requests
import json

base_url = 'http://localhost:8000'

print("=" * 70)
print("Testing DressMate Phase 2 - Authentication & Chatbot Features")
print("=" * 70)

# Test 1: Registration
print('\n✓ Test 1: User Registration')
token = None
user_id = None
try:
    r = requests.post(f'{base_url}/api/auth/register', json={
        "email": "testuser@example.com",
        "password": "password123",
        "name": "Test User"
    })
    if r.status_code == 200:
        data = r.json()
        token = data.get("access_token")
        user_id = data.get("user_id")
        print(f'  Status: {r.status_code}')
        print(f'  User ID: {user_id}')
        print(f'  Token: {token[:20]}...')
    else:
        print(f'  Status: {r.status_code}')
        print(f'  Error: {r.text}')
except Exception as e:
    print(f'  Error: {e}')
    token = None
    user_id = None

# Test 2: Login
print('\n✓ Test 2: User Login')
try:
    r = requests.post(f'{base_url}/api/auth/login', json={
        "email": "testuser@example.com",
        "password": "password123"
    })
    if r.status_code == 200:
        data = r.json()
        token = data.get("access_token")
        print(f'  Status: {r.status_code}')
        print(f'  Login successful')
        print(f'  Token: {token[:20]}...')
    else:
        print(f'  Status: {r.status_code}')
        print(f'  Error: {r.text}')
except Exception as e:
    print(f'  Error: {e}')

# Test 3: Get Profile (with token)
print('\n✓ Test 3: Get User Profile')
if token:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f'{base_url}/api/auth/profile', headers=headers)
        if r.status_code == 200:
            profile = r.json()
            print(f'  Status: {r.status_code}')
            print(f'  Email: {profile.get("email")}')
            print(f'  Name: {profile.get("name")}')
        else:
            print(f'  Status: {r.status_code}')
            print(f'  Error: {r.text}')
    except Exception as e:
        print(f'  Error: {e}')
else:
    print('  Skipped (no token)')

# Test 4: Test image recommendation (still works)
print('\n✓ Test 4: Image Recommendation (existing feature)')
try:
    r = requests.get(f'{base_url}/api/stats')
    if r.status_code == 200:
        stats = r.json()
        print(f'  Status: {r.status_code}')
        print(f'  Total Products: {stats["total_products"]}')
        print(f'  Product Types: {len(stats["product_types"])}')
    else:
        print(f'  Status: {r.status_code}')
except Exception as e:
    print(f'  Error: {e}')

# Test 5: Test recommendation history (requires auth)
print('\n✓ Test 5: Recommendation History')
if token:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f'{base_url}/api/history', headers=headers)
        if r.status_code == 200:
            data = r.json()
            print(f'  Status: {r.status_code}')
            print(f'  History entries: {data["total"]}')
        else:
            print(f'  Status: {r.status_code}')
            print(f'  Error: {r.text}')
    except Exception as e:
        print(f'  Error: {e}')
else:
    print('  Skipped (no token)')

# Test 6: Chat endpoint (Gemini - may fail without API key)
print('\n✓ Test 6: AI Chat (Gemini)')
if token:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.post(f'{base_url}/api/chat?message=What%20colors%20look%20good?', 
                         headers=headers)
        if r.status_code == 200:
            data = r.json()
            print(f'  Status: {r.status_code}')
            print(f'  Response: {data.get("response", "")[:100]}...')
        elif r.status_code == 400:
            print(f'  Status: {r.status_code}')
            print(f'  Note: Gemini API key not configured (expected)')
            print(f'  Info: {r.json().get("detail", "")}')
        else:
            print(f'  Status: {r.status_code}')
    except Exception as e:
        print(f'  Error: {e}')
else:
    print('  Skipped (no token)')

print('\n' + "=" * 70)
print("✅ Phase 2 Features Tested!")
print("=" * 70)
print("\nNext steps:")
print("1. Configure GEMINI_API_KEY in .env for full chatbot experience")
print("2. Test image uploads with authentication to save to history")
print("3. Test frontend integration with new auth tokens")
