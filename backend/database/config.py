"""
MongoDB Database Configuration and Helper Functions
====================================================
Manages connection to MongoDB and provides CRUD operations for products and users.
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
import os
from typing import List, Dict, Optional

load_dotenv()

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dressmate")

# Global client and database instances
client: Optional[MongoClient] = None
db = None


def connect_to_mongodb():
    """
    Establish connection to MongoDB.
    Call this during application startup.
    """
    global client, db
    try:
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        # Verify connection
        client.admin.command('ping')
        db = client[DATABASE_NAME]
        print(f"[ok] Connected to MongoDB: {DATABASE_NAME}")
        initialize_collections()
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[error] Failed to connect to MongoDB: {e}")
        print("  Make sure MongoDB is running on localhost:27017")
        print("  Or update MONGODB_URL in your .env file")
        return False


def close_mongodb():
    """Close MongoDB connection. Call this during application shutdown."""
    global client
    if client:
        client.close()
        print("[ok] MongoDB connection closed")


def initialize_collections():
    """Create collections and indexes if they don't exist."""
    global db
    
    if db is None:
        return
    
    # Create products collection with indexes
    if "products" not in db.list_collection_names():
        db.create_collection("products")
        print("[ok] Created 'products' collection")
    
    # Create indexes on products for commonly filtered/sorted fields
    # This significantly improves query performance
    db.products.create_index([("product_type", ASCENDING)])
    db.products.create_index([("colour", ASCENDING)])
    db.products.create_index([("brand", ASCENDING)])
    db.products.create_index([("cluster", ASCENDING)])
    db.products.create_index([("price", ASCENDING)])  # For price sorting
    db.products.create_index([("rating", DESCENDING)])  # For rating sorting
    
    # Compound indexes for common filter combinations
    db.products.create_index([("product_type", ASCENDING), ("colour", ASCENDING)])
    db.products.create_index([("product_type", ASCENDING), ("price", ASCENDING)])
    db.products.create_index([("product_type", ASCENDING), ("rating", DESCENDING)])
    
    # Text index for search functionality (if needed in future)
    # db.products.create_index([("name", "text"), ("description", "text"), ("brand", "text")])
    
    # Create users collection
    if "users" not in db.list_collection_names():
        db.create_collection("users")
        print("[ok] Created 'users' collection")
    
    db.users.create_index([("email", ASCENDING)], unique=True)
    
    # Create recommendations collection
    if "recommendations" not in db.list_collection_names():
        db.create_collection("recommendations")
        print("[ok] Created 'recommendations' collection")
    
    db.recommendations.create_index([("user_id", ASCENDING)])
    db.recommendations.create_index([("created_at", DESCENDING)])


# ─────────────────────────────────────────────────────────────────────────
# Product Operations
# ─────────────────────────────────────────────────────────────────────────

def insert_products(products_data: List[Dict]) -> List[str]:
    """Insert multiple products into the database."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    result = db.products.insert_many(products_data)
    return result.inserted_ids


def get_all_products(limit: int = 1000) -> List[Dict]:
    """Get all products from the database."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    products = list(db.products.find({}).limit(limit))
    return products


def get_product_by_id(product_id: str) -> Optional[Dict]:
    """Get a single product by ID."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    from bson.objectid import ObjectId
    try:
        return db.products.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return db.products.find_one({"_id": int(product_id)})


def get_products_by_ids(product_ids: List[str]) -> List[Dict]:
    """Get multiple products by IDs in a single batch query."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    from bson.objectid import ObjectId
    
    # Try to convert IDs to ObjectId format
    object_ids = []
    for pid in product_ids:
        try:
            object_ids.append(ObjectId(pid))
        except:
            try:
                object_ids.append(int(pid))
            except:
                object_ids.append(pid)
    
    # Query by IDs
    results = list(db.products.find({"_id": {"$in": object_ids}}))
    return results


def search_products(query: Dict, limit: int = 50, skip: int = 0, sort_field: str = None, sort_order: int = 1) -> List[Dict]:
    """Search products with flexible query filters, pagination, and sorting.
    
    Args:
        query: MongoDB query filter
        limit: Maximum number of results (default 50)
        skip: Number of results to skip for pagination (default 0)
        sort_field: Field to sort by (e.g., 'price', 'rating'). If None, no sorting applied.
        sort_order: 1 for ascending, -1 for descending (default 1)
    """
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    
    # Use aggregation pipeline for price sorting to convert string to number
    if sort_field == "price":
        pipeline = [
            {"$match": query},
            {
                "$addFields": {
                    "price_numeric": {
                        "$cond": [
                            {"$eq": ["$price", None]},
                            0,
                            {
                                "$convert": {
                                    "input": "$price",
                                    "to": "double",
                                    "onError": 0,
                                    "onNull": 0
                                }
                            }
                        ]
                    }
                }
            },
            {"$sort": {"price_numeric": sort_order}},
            {"$skip": skip},
            {"$limit": limit}
        ]
        results = list(db.products.aggregate(pipeline))
        return results
    else:
        # For non-price fields, use regular find + sort
        cursor = db.products.find(query).skip(skip).limit(limit)
        if sort_field:
            cursor = cursor.sort(sort_field, sort_order)
        return list(cursor)


def count_products(query: Dict = None) -> int:
    """Count products matching a query."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    if query is None:
        query = {}
    return db.products.count_documents(query)


def delete_all_products():
    """Delete all products (for migration/testing)."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    result = db.products.delete_many({})
    return result.deleted_count


# ─────────────────────────────────────────────────────────────────────────
# User Operations
# ─────────────────────────────────────────────────────────────────────────

def insert_user(user_data: Dict) -> str:
    """Insert a new user."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    result = db.users.insert_one(user_data)
    return str(result.inserted_id)


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    return db.users.find_one({"email": email})


def update_user(user_id: str, update_data: Dict) -> bool:
    """Update user information."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    from bson.objectid import ObjectId
    try:
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception:
        result = db.users.update_one(
            {"_id": int(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0


# ─────────────────────────────────────────────────────────────────────────
# Recommendation Operations
# ─────────────────────────────────────────────────────────────────────────

def insert_recommendation(recommendation_data: Dict) -> str:
    """Insert a recommendation record."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    result = db.recommendations.insert_one(recommendation_data)
    return str(result.inserted_id)


def get_user_recommendations(user_id: str, limit: int = 50) -> List[Dict]:
    """Get recommendations for a specific user."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    from bson.objectid import ObjectId
    try:
        return list(db.recommendations.find(
            {"user_id": ObjectId(user_id)}
        ).sort("created_at", -1).limit(limit))
    except Exception:
        return list(db.recommendations.find(
            {"user_id": int(user_id)}
        ).sort("created_at", -1).limit(limit))
