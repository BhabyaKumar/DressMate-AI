#!/usr/bin/env python3
"""
Smoke Test for DressMate Backend
Verifies all major modules can be imported and basic functionality works
"""

import sys
from pathlib import Path
import traceback

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    """Test if all major modules can be imported"""
    print("=" * 60)
    print("🔍 SMOKE TEST: DressMate Backend Reorganization")
    print("=" * 60)
    print()
    
    tests_passed = 0
    tests_failed = 0
    
    # Test imports
    imports_to_test = [
        ("app", "Main FastAPI application"),
        ("database.config", "MongoDB configuration"),
        ("auth.auth", "Authentication module"),
        ("ml.clustering", "ML clustering module"),
        ("ml.embedding_generator", "Embedding generator"),
        ("ml.product_classifier", "Product classifier"),
        ("ml.preprocessing", "Data preprocessing"),
        ("vision.feature_extractor", "ResNet feature extractor"),
        ("vision.skin_tone_detector", "Skin tone detector"),
        ("vision.body_shape_detector", "Body shape detector"),
        ("recommender.ranking", "Recommendation ranking"),
        ("recommender.similarity", "Similarity module"),
        ("utils.visualizer", "Utils visualizer"),
    ]
    
    print("📦 Testing module imports:")
    print("-" * 60)
    
    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name:<35} - {description}")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ {module_name:<35} - {description}")
            print(f"     Error: {str(e)[:60]}")
            tests_failed += 1
            traceback.print_exc()
    
    print()
    print("=" * 60)
    print(f"📊 Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    
    if tests_failed == 0:
        print("✅ All smoke tests PASSED! Backend is properly organized.")
        return True
    else:
        print(f"❌ {tests_failed} test(s) FAILED. Check errors above.")
        return False

def test_specific_functions():
    """Test key functions work"""
    print()
    print("🔧 Testing specific functions:")
    print("-" * 60)
    
    try:
        from ml.product_classifier import detect_product_type
        result = detect_product_type("blue kurta")
        if result == "kurta":
            print(f"  ✅ Product classifier: '{result}' (expected: 'kurta')")
            return True
        else:
            print(f"  ⚠️  Product classifier: '{result}' (expected: 'kurta')")
            return False
    except Exception as e:
        print(f"  ❌ Product classifier error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    func_test = test_specific_functions()
    
    print()
    if success and func_test:
        print("🎉 SMOKE TEST COMPLETE - ALL SYSTEMS GO!")
        sys.exit(0)
    else:
        print("⚠️  SMOKE TEST FOUND ISSUES - CHECK ABOVE")
        sys.exit(1)
