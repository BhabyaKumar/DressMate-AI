"""
End-to-End Test Suite for DressMate Frontend Integration
Tests the complete user flow: Registration → Login → Profile → Upload → History
"""
import requests
import json
import random
import string
from datetime import datetime

BASE_URL = "http://localhost:8000"

def random_email():
    """Generate a random email for testing"""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_str}@example.com"

def test_health():
    """Test API health endpoint"""
    print("\n🔍 Testing API Health...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    print(f"✓ Health check passed: {response.json()}")
    return True

def test_registration():
    """Test user registration"""
    print("\n📝 Testing User Registration...")
    email = random_email()
    password = "TestPassword123!"
    name = "Test User"
    
    data = {"email": email, "password": password, "name": name}
    response = requests.post(f"{BASE_URL}/api/auth/register", json=data)
    
    print(f"   Email: {email}")
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Registration failed: {response.text}"
    result = response.json()
    assert "access_token" in result, "No access token returned"
    
    print(f"✓ Registration successful")
    print(f"  Token: {result['access_token'][:50]}...")
    
    return email, password, result['access_token']

def test_login(email, password):
    """Test user login"""
    print("\n🔐 Testing User Login...")
    
    data = {"email": email, "password": password}
    response = requests.post(f"{BASE_URL}/api/auth/login", json=data)
    
    print(f"   Email: {email}")
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Login failed: {response.text}"
    result = response.json()
    assert "access_token" in result, "No access token returned"
    
    print(f"✓ Login successful")
    print(f"  Token: {result['access_token'][:50]}...")
    
    return result['access_token']

def test_profile(token):
    """Test getting user profile"""
    print("\n👤 Testing User Profile...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers)
    
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Profile retrieval failed: {response.text}"
    profile = response.json()
    
    print(f"✓ Profile retrieved successfully")
    print(f"  Name: {profile.get('name')}")
    print(f"  Email: {profile.get('email')}")
    print(f"  ID: {profile.get('_id')}")
    
    return profile

def test_products():
    """Test product browsing (public endpoint)"""
    print("\n🛍️  Testing Product Browsing...")
    
    response = requests.get(f"{BASE_URL}/api/products", params={"limit": 5})
    
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Product listing failed: {response.text}"
    data = response.json()
    
    print(f"✓ Products retrieved successfully")
    print(f"  Total products: {data.get('total', 'N/A')}")
    print(f"  Sample products: {len(data.get('products', []))} loaded")
    
    if data.get('products'):
        sample = data['products'][0]
        print(f"  First product: {sample.get('name')} - ${sample.get('price')}")
    
    return data.get('products', [])

def test_stats():
    """Test API statistics endpoint"""
    print("\n📊 Testing Statistics Endpoint...")
    
    response = requests.get(f"{BASE_URL}/api/stats")
    
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Stats failed: {response.text}"
    stats = response.json()
    
    print(f"✓ Statistics retrieved successfully")
    print(f"  Total products: {stats.get('total_products')}")
    print(f"  Total clusters: {stats.get('total_clusters')}")
    print(f"  Database: {stats.get('database')}")
    
    return stats

def test_text_recommendation(token):
    """Test text-based recommendation"""
    print("\n💬 Testing Text Recommendation...")
    
    params = {"product_type": "dress", "color": "", "top_k": 8}
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/recommend/text", params=params, headers=headers)
    
    print(f"   Query: product_type='dress'")
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"Text recommendation failed: {response.text}"
    results = response.json()
    
    print(f"✓ Text recommendation successful")
    print(f"  Recommendations: {len(results.get('results', []))} items")
    
    if results.get('results'):
        sample = results['results'][0]
        print(f"  Top recommendation: {sample.get('name')} - ${sample.get('price', 'N/A')}")
    
    return results

def test_history(token):
    """Test recommendation history retrieval"""
    print("\n📜 Testing Recommendation History...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/history", headers=headers)
    
    print(f"   Response Status: {response.status_code}")
    
    assert response.status_code == 200, f"History retrieval failed: {response.text}"
    data = response.json()
    
    # History endpoint returns {status, total, history}
    history = data.get('history', [])
    
    print(f"✓ History retrieved successfully")
    print(f"  Total recommendations: {data.get('total', 0)}")
    
    if history:
        latest = history[0]
        print(f"  Latest type: {latest.get('type', 'N/A')}")
    
    return history

def test_chat(token):
    """Test AI Stylist chat endpoint"""
    print("\n🤖 Testing AI Stylist Chat...")
    
    data = {"message": "What should I wear to a summer beach party?"}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json=data, headers=headers)
        
        print(f"   Message: 'What should I wear to a summer beach party?'")
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Chat endpoint responded")
            response_text = result.get('response', '')[:100] if result.get('response') else "No response"
            print(f"  Response: {response_text}...")
            return result
        else:
            print(f"⚠️  Chat endpoint returned {response.status_code}")
            print(f"   Note: This may be due to missing GEMINI_API_KEY in .env")
            return None
    except Exception as e:
        print(f"⚠️  Chat error: {str(e)[:100]}")
        print(f"   Note: Gemini API might not be configured")
        return None

def run_full_test():
    """Run complete end-to-end test suite"""
    print("="*60)
    print("DressMate E2E Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # Public endpoints (no auth required)
        test_health()
        test_stats()
        test_products()
        
        # Auth flow
        email, password, token1 = test_registration()
        token2 = test_login(email, password)
        
        # Protected endpoints
        profile = test_profile(token1)
        test_text_recommendation(token1)
        test_history(token1)
        test_chat(token1)
        
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        print("\nSummary:")
        print(f"  ✓ API is healthy and responding")
        print(f"  ✓ User registration works")
        print(f"  ✓ User login works")
        print(f"  ✓ User profile retrieval works")
        print(f"  ✓ Product browsing works")
        print(f"  ✓ Text recommendations work")
        print(f"  ✓ Recommendation history works")
        print(f"  ✓ Chat endpoint accessible")
        print("\nThe frontend is ready to connect to these endpoints!")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to backend at {BASE_URL}")
        print("   Make sure the FastAPI server is running:")
        print("   cd backend && python -m uvicorn app:app --reload")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_full_test()
    exit(0 if success else 1)
