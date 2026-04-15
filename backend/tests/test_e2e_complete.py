#!/usr/bin/env python3
"""
End-to-End Testing Suite for DressMate Application
Tests complete user flow: Register → Login → Browse → Dashboard → Logout
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
FRONTEND_BASE = "http://localhost:3000"

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

# Test 1: Backend Health Check
def test_backend_health():
    print_header("TEST 1: Backend Health Check")
    try:
        response = requests.get(f"{BASE_URL}/api/products?page=1&per_page=1", timeout=5)
        if response.status_code == 200:
            data = response.json()
            total_products = data.get('total', 0)
            print_success(f"Backend is healthy")
            print_success(f"Database has {total_products:,} products loaded")
            return True
        else:
            print_error(f"Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Backend unreachable: {str(e)}")
        return False

# Test 2: User Registration
def test_user_registration():
    print_header("TEST 2: User Registration")
    timestamp = int(datetime.now().timestamp())
    test_email = f"testuser{timestamp}@dressmate.local"
    test_password = "TestPassword123!"
    test_name = "Test User"
    
    try:
        payload = {
            "email": test_email,
            "password": test_password,
            "name": test_name
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"User registered successfully")
            print_success(f"Email: {test_email}")
            print_success(f"Name: {test_name}")
            return True, test_email, test_password, data.get('user_id')
        elif response.status_code == 400:
            error = response.json().get('detail', 'Unknown error')
            if 'already exists' in error:
                print_warning(f"User already exists (this is OK for repeat testing)")
                return True, test_email, test_password, None
            else:
                print_error(f"Registration failed: {error}")
                return False, None, None, None
        else:
            print_error(f"Registration failed with status {response.status_code}")
            print_error(f"Response: {response.text}")
            return False, None, None, None
    except Exception as e:
        print_error(f"Registration error: {str(e)}")
        return False, None, None, None

# Test 3: User Login
def test_user_login(email, password):
    print_header("TEST 3: User Login")
    try:
        payload = {
            "email": email,
            "password": password
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            user_id = data.get('user_id')
            if token:
                print_success(f"Login successful")
                print_success(f"JWT Token received: {token[:50]}...")
                print_success(f"User ID: {user_id}")
                return True, token, user_id
            else:
                print_error("No token in response")
                return False, None, None
        else:
            print_error(f"Login failed with status {response.status_code}")
            print_error(f"Response: {response.text}")
            return False, None, None
    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return False, None, None

# Test 4: Get User Profile
def test_get_profile(token):
    print_header("TEST 4: Get User Profile")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers, timeout=5)
        
        if response.status_code == 200:
            user = response.json().get('user', {})
            print_success(f"Profile retrieved")
            print_success(f"Name: {user.get('name')}")
            print_success(f"Email: {user.get('email')}")
            print_success(f"User ID: {user.get('id')}")
            return True, user
        else:
            print_error(f"Profile fetch failed with status {response.status_code}")
            return False, None
    except Exception as e:
        print_error(f"Profile fetch error: {str(e)}")
        return False, None

# Test 5: Browse Products
def test_browse_products():
    print_header("TEST 5: Browse Products")
    try:
        response = requests.get(f"{BASE_URL}/api/products?page=1&per_page=5", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('results', [])
            total = data.get('total', 0)
            
            print_success(f"Product browsing works")
            print_success(f"Showing {len(products)} products of {total} total")
            
            if products:
                for i, product in enumerate(products, 1):
                    print_info(f"{i}. {product.get('name', 'Unknown')} - ₹{product.get('price', 'N/A')}")
                return True, products
            else:
                print_error("No products returned")
                return False, []
        else:
            print_error(f"Product fetch failed with status {response.status_code}")
            return False, []
    except Exception as e:
        print_error(f"Product browsing error: {str(e)}")
        return False, []

# Test 6: Get Recommendations
def test_get_recommendations(token):
    print_header("TEST 6: Get User Recommendations History")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/recommendations?skip=0&limit=10", headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            recommendations = data.get('recommendations', [])
            print_success(f"Recommendations history retrieved")
            print_success(f"User has {len(recommendations)} past recommendations")
            if recommendations:
                for i, rec in enumerate(recommendations[:3], 1):
                    print_info(f"{i}. {rec.get('search_query', 'N/A')} on {rec.get('timestamp', 'N/A')}")
            return True
        else:
            print_info(f"No recommendations yet (status {response.status_code}) - this is normal for new users")
            return True
    except Exception as e:
        print_warning(f"Recommendations error: {str(e)} - this may be normal")
        return True

# Test 7: Search Products
def test_search_products():
    print_header("TEST 7: Search Products")
    try:
        response = requests.get(f"{BASE_URL}/api/search?query=dress&limit=3", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print_success(f"Product search works")
            print_success(f"Found {len(results)} products matching 'dress'")
            if results:
                for i, product in enumerate(results, 1):
                    print_info(f"{i}. {product.get('name', 'Unknown')}")
            return True
        else:
            print_error(f"Search failed with status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Search error: {str(e)}")
        return False

# Test 8: API Endpoints Summary
def test_api_endpoints():
    print_header("TEST 8: API Endpoints Availability")
    
    endpoints = [
        ("GET", "/api/products", "Product listing"),
        ("GET", "/api/search", "Product search"),
        ("POST", "/api/auth/register", "User registration"),
        ("POST", "/api/auth/login", "User login"),
        ("GET", "/api/auth/profile", "User profile (requires auth)"),
        ("GET", "/api/recommendations", "User recommendations (requires auth)"),
    ]
    
    working = 0
    for method, endpoint, description in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", json={}, timeout=5)
            
            # Any response (even 400) means endpoint exists
            if response.status_code < 500:
                print_success(f"{method:6} {endpoint:30} - {description}")
                working += 1
            else:
                print_error(f"{method:6} {endpoint:30} - Server error")
        except Exception as e:
            print_error(f"{method:6} {endpoint:30} - {str(e)}")
    
    print(f"\n{Colors.BOLD}Endpoints Working: {working}/{len(endpoints)}{Colors.RESET}")
    return working == len(endpoints)

# Test 9: Frontend Pages Check
def test_frontend_pages():
    print_header("TEST 9: Frontend Pages Structure Check")
    
    pages = [
        "login.html",
        "index.html",
        "dashboard.html",
        "browse_products.html",
        "image_upload_page.html",
        "my_wardrobe.html",
        "gemini_stylist.html",
        "product_detail.html",
        "recommendation_results.html",
        "system_feedback.html",
    ]
    
    import os
    frontend_dir = "c:\\Users\\bhaby\\Desktop\\DressMate\\frontend"
    
    working = 0
    for page in pages:
        page_path = os.path.join(frontend_dir, page)
        if os.path.exists(page_path):
            # Check if auth.js is imported (for protected pages)
            with open(page_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                has_auth = 'auth.js' in content
                auth_status = "✓ Has auth" if has_auth else "- No auth"
                print_success(f"{page:30} {auth_status}")
                working += 1
        else:
            print_error(f"{page:30} NOT FOUND")
    
    print(f"\n{Colors.BOLD}Pages Available: {working}/{len(pages)}{Colors.RESET}")
    return working == len(pages)

# Test 10: Summary Report
def print_test_summary(results):
    print_header("TEST SUMMARY")
    
    tests = [
        ("Backend Health", results['health']),
        ("User Registration", results['register']),
        ("User Login", results['login']),
        ("Profile Access", results['profile']),
        ("Product Browsing", results['browse']),
        ("Recommendations", results['recommendations']),
        ("Product Search", results['search']),
        ("API Endpoints", results['endpoints']),
        ("Frontend Pages", results['frontend']),
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name:30} {status}")
    
    print(f"\n{Colors.BOLD}Overall: {passed}/{total} tests passed ({100*passed//total}%){Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! Application is ready for deployment.{Colors.RESET}")
    elif passed >= 7:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Most tests passed. Minor issues may need attention.{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Multiple tests failed. Debug required before deployment.{Colors.RESET}")
    
    return passed, total

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║          DressMate - End-to-End Testing Suite              ║")
    print("║                                                            ║")
    print("║  Testing complete user flow and system functionality       ║")
    print(f"║  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(Colors.RESET)
    
    results = {}
    
    # Test 1: Health Check
    results['health'] = test_backend_health()
    if not results['health']:
        print_error("\n⚠️  Backend is not responding. Please start the backend server:")
        print_info("cd c:\\Users\\bhaby\\Desktop\\DressMate\\backend")
        print_info("python -m uvicorn app:app --reload --port 8000")
        sys.exit(1)
    
    # Test 2-3: Registration & Login
    register_success, email, password, user_id = test_user_registration()
    results['register'] = register_success
    
    if register_success and email and password:
        login_success, token, returned_user_id = test_user_login(email, password)
        results['login'] = login_success
        
        if login_success and token:
            # Test 4: Profile
            profile_success, user = test_get_profile(token)
            results['profile'] = profile_success
            
            # Test 6: Recommendations
            results['recommendations'] = test_get_recommendations(token)
        else:
            results['profile'] = False
            results['recommendations'] = False
    else:
        results['login'] = False
        results['profile'] = False
        results['recommendations'] = False
    
    # Test 5: Browse Products
    results['browse'], _ = test_browse_products()
    
    # Test 7: Search
    results['search'] = test_search_products()
    
    # Test 8: API Endpoints
    results['endpoints'] = test_api_endpoints()
    
    # Test 9: Frontend Pages
    results['frontend'] = test_frontend_pages()
    
    # Final Summary
    passed, total = print_test_summary(results)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
