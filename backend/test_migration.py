"""Test script to verify MongoDB migration was successful."""

from database import connect_to_mongodb, get_all_products

if connect_to_mongodb():
    products = get_all_products(limit=5)
    print(f"\n✓ Total products in database: {len(products)}")
    print(f"\nFirst product:")
    if products:
        p = products[0]
        print(f"  Name: {p.get('name')}")
        print(f"  Brand: {p.get('brand')}")
        print(f"  Type: {p.get('product_type')}")
        print(f"  Has embedding: {'embedding' in p}")
else:
    print("Failed to connect to MongoDB")
