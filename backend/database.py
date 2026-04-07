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
from bson.objectid import ObjectId

load_dotenv()

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dressmate")

# Global client and database instances
client: Optional[MongoClient] = None
db = None


def normalize_user_id(user_id) -> str:
    """Normalize user IDs to strings for consistent storage and querying."""
    return str(user_id)


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
        print(f"✓ Connected to MongoDB: {DATABASE_NAME}")
        initialize_collections()
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        print("  Make sure MongoDB is running on localhost:27017")
        print("  Or update MONGODB_URL in your .env file")
        return False


def close_mongodb():
    """Close MongoDB connection. Call this during application shutdown."""
    global client
    if client:
        client.close()
        print("✓ MongoDB connection closed")


def initialize_collections():
    """Create collections and indexes if they don't exist."""
    global db
    
    if db is None:
        return
    
    # Create products collection with indexes
    if "products" not in db.list_collection_names():
        db.create_collection("products")
        print("✓ Created 'products' collection")
    
    # Create indexes on products
    db.products.create_index([("name", ASCENDING)])
    db.products.create_index([("product_type", ASCENDING)])
    db.products.create_index([("colour", ASCENDING)])
    db.products.create_index([("cluster", ASCENDING)])
    db.products.create_index([("rating", DESCENDING)])
    
    # Create users collection
    if "users" not in db.list_collection_names():
        db.create_collection("users")
        print("✓ Created 'users' collection")
    
    db.users.create_index([("email", ASCENDING)], unique=True)
    
    # Create recommendations collection
    if "recommendations" not in db.list_collection_names():
        db.create_collection("recommendations")
        print("✓ Created 'recommendations' collection")
    
    db.recommendations.create_index([("user_id", ASCENDING)])
    db.recommendations.create_index([("created_at", DESCENDING)])

    # Create user_interactions collection
    if "user_interactions" not in db.list_collection_names():
        db.create_collection("user_interactions")
        print("✓ Created 'user_interactions' collection")

    db.user_interactions.create_index([("user_id", ASCENDING)])
    db.user_interactions.create_index([("product_id", ASCENDING)])
    db.user_interactions.create_index([("action", ASCENDING)])
    db.user_interactions.create_index([("created_at", DESCENDING)])


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
    """Get multiple products by their IDs."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")

    object_ids = []
    numeric_ids = []

    for pid in product_ids:
        pid = str(pid)
        if ObjectId.is_valid(pid):
            object_ids.append(ObjectId(pid))
            continue
        try:
            numeric_ids.append(int(pid))
        except Exception:
            continue

    query_parts = []
    if object_ids:
        query_parts.append({"_id": {"$in": object_ids}})
    if numeric_ids:
        query_parts.append({"_id": {"$in": numeric_ids}})

    if not query_parts:
        return []

    query = query_parts[0] if len(query_parts) == 1 else {"$or": query_parts}
    return list(db.products.find(query))


def search_products(query: Dict, limit: int = 50) -> List[Dict]:
    """Search products with flexible query filters."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    return list(db.products.find(query).limit(limit))


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

    # Accept either plain fields (wrapped with $set) or full Mongo operators.
    has_operator = any(str(k).startswith("$") for k in update_data.keys())
    final_update = update_data if has_operator else {"$set": update_data}

    try:
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            final_update
        )
        return result.modified_count > 0
    except Exception:
        result = db.users.update_one(
            {"_id": int(user_id)},
            final_update
        )
        return result.modified_count > 0


# ─────────────────────────────────────────────────────────────────────────
# Recommendation Operations
# ─────────────────────────────────────────────────────────────────────────

def insert_recommendation(recommendation_data: Dict) -> str:
    """Insert a recommendation record."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    if "user_id" in recommendation_data:
        recommendation_data["user_id"] = normalize_user_id(recommendation_data["user_id"])
    result = db.recommendations.insert_one(recommendation_data)
    return str(result.inserted_id)


def get_user_recommendations(user_id: str, limit: int = 50) -> List[Dict]:
    """Get recommendations for a specific user."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")
    return list(db.recommendations.find(
        {"user_id": normalize_user_id(user_id)}
    ).sort("created_at", -1).limit(limit))


def insert_user_interaction(interaction_data: Dict) -> str:
    """Insert a user interaction event (like, dislike, click, save)."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")

    if "user_id" in interaction_data:
        interaction_data["user_id"] = normalize_user_id(interaction_data["user_id"])
    if "product_id" in interaction_data:
        interaction_data["product_id"] = str(interaction_data["product_id"])

    result = db.user_interactions.insert_one(interaction_data)
    return str(result.inserted_id)


def get_user_interactions(user_id: str, limit: int = 200) -> List[Dict]:
    """Get recent interactions for a specific user."""
    if db is None:
        raise RuntimeError("Not connected to MongoDB")

    return list(db.user_interactions.find(
        {"user_id": normalize_user_id(user_id)}
    ).sort("created_at", -1).limit(limit))
