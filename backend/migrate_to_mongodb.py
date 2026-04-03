"""
MongoDB Migration Script
========================
Loads data from CSV and embeddings from NPY file into MongoDB.

Usage:
  python migrate_to_mongodb.py

This script:
1. Reads fashion_with_clusters.csv
2. Reads fashion_embeddings.npy
3. Combines them and inserts into MongoDB
4. Creates indexes
"""

import pandas as pd
import numpy as np
from pathlib import Path
from database import connect_to_mongodb, db, insert_products, delete_all_products
import sys


def migrate_csv_to_mongodb():
    """Load CSV data and embeddings into MongoDB."""
    
    # Paths
    base_dir = Path(__file__).parent
    csv_path = base_dir / "data" / "fashion_with_clusters.csv"
    emb_path = base_dir / "data" / "fashion_embeddings.npy"
    
    # Check if files exist
    if not csv_path.exists():
        print(f"✗ CSV file not found: {csv_path}")
        return False
    
    if not emb_path.exists():
        print(f"✗ Embeddings file not found: {emb_path}")
        return False
    
    print(f"📖 Reading CSV from {csv_path}")
    df = pd.read_csv(csv_path)
    df = df.fillna("")
    
    print(f"📊 Loading embeddings from {emb_path}")
    embeddings = np.load(emb_path)
    
    if len(df) != len(embeddings):
        print(f"✗ Mismatch: {len(df)} rows in CSV but {len(embeddings)} embeddings")
        return False
    
    print(f"✓ Loaded {len(df)} products with embeddings")
    
    # Combine data
    products = []
    for idx, (_, row) in enumerate(df.iterrows()):
        product = {
            "name": str(row.get("name", f"Product {idx}")),
            "brand": str(row.get("brand", "")),
            "price": str(row.get("price", row.get("selling_price", ""))),
            "colour": str(row.get("colour", row.get("image_color", ""))),
            "product_type": str(row.get("product_type", "")),
            "description": str(row.get("description", "")),
            "image_url": str(row.get("image_url", row.get("image_path", ""))),
            "rating": float(row.get("rating", 4.0) or 4.0),
            "cluster": int(row.get("cluster", 0) or 0),
            "embedding": embeddings[idx].tolist(),  # Convert numpy array to list
        }
        products.append(product)
    
    # Connect and insert
    if not connect_to_mongodb():
        return False
    
    print(f"\n🗑️  Clearing existing products...")
    deleted = delete_all_products()
    print(f"✓ Deleted {deleted} old products")
    
    print(f"\n💾 Inserting {len(products)} products into MongoDB...")
    try:
        inserted_ids = insert_products(products)
        print(f"✓ Successfully inserted {len(inserted_ids)} products")
        print(f"\nFirst 3 products inserted:")
        for prod in products[:3]:
            print(f"  - {prod['name']} ({prod['product_type']})")
        return True
    except Exception as e:
        print(f"✗ Error inserting products: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Migration - CSV to Database")
    print("=" * 60)
    
    success = migrate_csv_to_mongodb()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\nYou can now run your FastAPI app with:")
        print("  python -m uvicorn app:app --reload --port 8000")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
