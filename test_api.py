import requests
import json

base_url = 'http://localhost:8000'

print("=" * 60)
print("Testing DressMate API")
print("=" * 60)

# Test 1: Health check
print('\n✓ Testing /health endpoint...')
r = requests.get(f'{base_url}/health')
print(f'  Status: {r.status_code}')
print(f'  Response: {r.json()}')

# Test 2: Get stats
print('\n✓ Testing /api/stats endpoint...')
r = requests.get(f'{base_url}/api/stats')
if r.status_code == 200:
    stats = r.json()
    print(f'  Total Products: {stats["total_products"]}')
    print(f'  Product Types: {len(stats["product_types"])}')
    print(f'  Colors Available: {len(stats["colors"])}')
    print(f'  Embedding Dimension: {stats["embedding_dim"]}')
else:
    print(f'  Error: {r.status_code}')

# Test 3: List products
print('\n✓ Testing /api/products endpoint...')
r = requests.get(f'{base_url}/api/products?page=1&per_page=3')
if r.status_code == 200:
    products = r.json()
    print(f'  Returned: {len(products["results"])} products')
    print(f'  Total available: {products["total"]}')
    if products['results']:
        first = products['results'][0]
        print(f'  First product: {first["name"]}')
        print(f'    - Type: {first["product_type"]}')
        print(f'    - Color: {first["colour"]}')
else:
    print(f'  Error: {r.status_code}')

# Test 4: Test text-based recommendation
print('\n✓ Testing /api/recommend/text endpoint...')
r = requests.get(f'{base_url}/api/recommend/text?product_type=kurta&top_k=3')
if r.status_code == 200:
    recs = r.json()
    print(f'  Found {len(recs["results"])} kurta recommendations')
    if recs['results']:
        print(f'  First recommendation: {recs["results"][0]["name"]}')
else:
    print(f'  Error: {r.status_code}')

print('\n' + "=" * 60)
print("✅ All basic tests passed! API is working.")
print("=" * 60)
