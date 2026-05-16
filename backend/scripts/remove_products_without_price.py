"""
Script to remove products without price from MongoDB
====================================================
Identifies and removes all products that don't have a valid price in the database.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import connect_to_mongodb, close_mongodb
from database import config as db_config
from dotenv import load_dotenv

load_dotenv()


def remove_products_without_price():
    """Remove products that don't have a price or have empty/null price."""
    
    if not connect_to_mongodb():
        print("[error] Failed to connect to MongoDB")
        return False
    
    try:
        # Get the database instance
        db = db_config.db
        
        # Find products without price
        # This will match: missing price field, null, empty string, 0, or other falsy values
        products_without_price = list(db.products.find({
            "$or": [
                {"price": {"$exists": False}},
                {"price": None},
                {"price": ""},
                {"price": 0},
            ]
        }))
        
        if not products_without_price:
            print("[info] No products found without price. Database is clean!")
            return True
        
        print(f"\n[info] Found {len(products_without_price)} products without valid price:")
        print("-" * 80)
        
        for product in products_without_price:
            product_id = product.get("_id", "unknown")
            name = product.get("name", "Unknown Product")
            price = product.get("price", "MISSING")
            print(f"  ID: {product_id}")
            print(f"  Name: {name}")
            print(f"  Price: {price}")
            print()
        
        # Confirm deletion
        response = input(f"\n[?] Delete these {len(products_without_price)} products? (yes/no): ")
        
        if response.lower() != "yes":
            print("[info] Deletion cancelled.")
            return False
        
        # Delete the products
        result = db.products.delete_many({
            "$or": [
                {"price": {"$exists": False}},
                {"price": None},
                {"price": ""},
                {"price": 0},
            ]
        })
        
        print(f"\n[ok] Successfully deleted {result.deleted_count} products without price")
        
        # Show remaining count
        remaining = db.products.count_documents({})
        print(f"[info] Total products remaining in database: {remaining}")
        
        return True
        
        return True
        
    except Exception as e:
        print(f"[error] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        close_mongodb()


if __name__ == "__main__":
    success = remove_products_without_price()
    sys.exit(0 if success else 1)
