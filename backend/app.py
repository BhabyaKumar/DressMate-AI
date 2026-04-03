"""
FashionAI Backend - FastAPI Server with MongoDB
===============================================
Integrates all backend modules into a REST API using MongoDB for data persistence.

Setup:
  pip install fastapi uvicorn python-multipart scikit-learn numpy pandas
              pillow opencv-python-headless tensorflow pymongo python-dotenv

Run:
  python -m uvicorn app:app --reload --port 8000

Then open the frontend HTML files. The API base URL is http://localhost:8000
"""

import os
import io
import uuid
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import numpy as np
import cv2
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# MongoDB imports
from database import (
    connect_to_mongodb,
    close_mongodb,
    get_all_products,
    get_product_by_id,
    search_products,
)

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ── lazy-load heavy assets ─────────────────────────────────────────────────
_resnet     = None


def get_resnet():
    """Lazy-load ResNet50 only when needed (heavy import)."""
    global _resnet
    if _resnet is None:
        from tensorflow.keras.applications import ResNet50
        _resnet = ResNet50(weights="imagenet", include_top=False, pooling="avg")
    return _resnet


# ── helper utilities ───────────────────────────────────────────────────────

def extract_features_from_array(img_array: np.ndarray) -> np.ndarray:
    """Extract ResNet50 features from an RGB numpy array (H×W×3)."""
    from tensorflow.keras.applications.resnet50 import preprocess_input
    img = Image.fromarray(img_array).resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)
    arr = preprocess_input(arr)
    model = get_resnet()
    features = model.predict(arr, verbose=0)
    return features.flatten()


def find_similar_items_mongo(query_vector: np.ndarray, top_k: int = 8) -> List[tuple]:
    """
    Find similar items by computing cosine similarity with all embeddings in MongoDB.
    Returns list of (product_dict, similarity_score) tuples.
    """
    products = get_all_products(limit=50000)
    
    similarities = []
    for product in products:
        if "embedding" not in product:
            continue
        
        try:
            embedding = np.array(product["embedding"])
            score = cosine_similarity(
                query_vector.reshape(1, -1),
                embedding.reshape(1, -1)
            )[0][0]
            similarities.append((product, float(score)))
        except Exception:
            continue
    
    # Sort by similarity and return top-k
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]


def detect_product_type(text: str) -> str:
    text = str(text).lower()
    mapping = {
        "kurta": ["kurta", "kurti"],
        "dress": ["dress", "gown"],
        "shirt": ["shirt"],
        "tshirt": ["tshirt", "t-shirt"],
        "jeans": ["jeans"],
        "top": ["top"],
        "saree": ["saree"],
        "skirt": ["skirt"],
        "jacket": ["jacket"],
        "leggings": ["leggings"],
        "shorts": ["shorts"],
        "pants": ["trousers", "pants"],
    }
    for ptype, keywords in mapping.items():
        if any(k in text for k in keywords):
            return ptype
    return "other"


def detect_skin_tone_from_array(img_rgb: np.ndarray) -> str:
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    gray  = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        # fallback: use centre crop of image
        h, w = img_rgb.shape[:2]
        crop = img_rgb[h//4: 3*h//4, w//4: 3*w//4]
        brightness = np.mean(crop)
    else:
        x, y, w, h = faces[0]
        face = img_rgb[y:y+h, x:x+w]
        brightness = np.mean(face)

    if brightness > 200:
        return "Fair"
    elif brightness > 140:
        return "Medium"
    else:
        return "Dark"


def get_dominant_color_name(img_rgb: np.ndarray) -> str:
    pixels = img_rgb.reshape(-1, 3)
    if len(pixels) > 5000:
        idx = np.random.choice(len(pixels), 5000, replace=False)
        pixels = pixels[idx]
    kmeans = KMeans(n_clusters=3, n_init=10, random_state=42)
    kmeans.fit(pixels)
    dominant = kmeans.cluster_centers_[np.argmax(np.bincount(kmeans.labels_))]
    r, g, b = dominant
    if r > 150 and g < 100 and b < 100: return "red"
    if g > 150 and r < 120:             return "green"
    if b > 150 and r < 120:             return "blue"
    if r > 150 and g > 150 and b < 100: return "yellow"
    if r < 80  and g < 80  and b < 80:  return "black"
    if r > 200 and g > 200 and b > 200: return "white"
    if r > 150 and g > 100 and b < 100: return "orange"
    if r > 150 and b > 150 and g < 100: return "purple"
    if r > 180 and g > 130 and b > 100: return "peach"
    return "other"


def product_to_dict(product: dict, similarity: float = 1.0) -> dict:
    """Convert a MongoDB product document to API response format."""
    from bson.objectid import ObjectId
    
    # Extract ID
    product_id = str(product.get("_id", ""))
    
    image_url = str(product.get("image_url", product.get("image_path", "")))

    if image_url and not image_url.startswith("http"):
        # Convert any local path like "Images\foo.jpg" or "Images/foo.jpg"
        # to a URL the browser can fetch: http://localhost:8000/images/foo.jpg
        filename = Path(image_url.replace("\\", "/")).name
        image_url = f"/images/{filename}"

    return {
        "id":           product_id,
        "name":         str(product.get("name", "Fashion Item")),
        "brand":        str(product.get("brand", "")),
        "price":        str(product.get("price", "")),
        "colour":       str(product.get("colour", "")),
        "product_type": str(product.get("product_type", "")),
        "description":  str(product.get("description", "")),
        "image_url":    image_url,
        "rating":       float(product.get("rating", 4.0) or 4.0),
        "cluster":      int(product.get("cluster", 0) or 0),
        "similarity":   round(float(similarity), 4),
    }


# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="FashionAI API",
    description="Backend for the AI Fashion Recommendation Frontend (MongoDB Version)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # in production restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve local Images folder as static files ──────────────────────────────
for _img_dir in ["Images", "images", "data/Images", "data/images"]:
    _img_path = BASE_DIR / _img_dir
    if _img_path.exists():
        app.mount("/images", StaticFiles(directory=str(_img_path)), name="images")
        print(f"✅ Serving images from: {_img_path}")
        break


# ── Startup / Shutdown events ──────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    """Initialize MongoDB connection on app startup."""
    print("🚀 Starting FashionAI Backend...")
    if connect_to_mongodb():
        print("✅ MongoDB ready, app started successfully!")
    else:
        print("⚠️  WARNING: MongoDB connection failed. Some features may not work.")


@app.on_event("shutdown")
def shutdown_event():
    """Close MongoDB connection on app shutdown."""
    print("🛑 Shutting down FashionAI Backend...")
    close_mongodb()


# ── endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "FashionAI API (MongoDB) is running"}


@app.get("/health")
def health():
    """Quick liveness check used by the frontend."""
    return {"status": "healthy"}


# ── 1. Image-based recommendation (core feature) ───────────────────────────
@app.post("/api/recommend/image")
async def recommend_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(8, ge=1, le=50),
):
    """
    Upload an image → get similar fashion items.
    Uses ResNet50 feature extraction and cosine similarity search in MongoDB.
    """
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)

        # Analysis
        skin_tone = detect_skin_tone_from_array(img_arr)
        color     = get_dominant_color_name(img_arr)

        # Feature extraction + similarity search
        features = extract_features_from_array(img_arr)
        similar_items = find_similar_items_mongo(features, top_k)

        products = [product_to_dict(prod, score) for prod, score in similar_items]

        return {
            "status":    "success",
            "skin_tone": skin_tone,
            "color":     color,
            "results":   products,
            "total":     len(products),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 2. Text-based recommendation ───────────────────────────────────────────
@app.get("/api/recommend/text")
def recommend_by_text(
    product_type: str = Query(..., description="e.g. dress, kurta, shirt"),
    color:        str = Query("", description="e.g. red, blue, black"),
    top_k:        int = Query(8, ge=1, le=50),
):
    """
    Filter by product_type & color, return similar items.
    Used by the browse page and search bar.
    """
    try:
        # Search products by type
        query = {"product_type": product_type.lower()}
        products = search_products(query, limit=100)

        if not products:
            return {"status": "success", "results": [], "total": 0}

        # If color filter specified, apply it
        if color:
            products = [p for p in products 
                       if p.get("colour", "").lower() == color.lower()]

        if not products:
            return {"status": "success", "results": [], "total": 0}

        # Find similar items to first result
        first_product = products[0]
        if "embedding" in first_product:
            embedding = np.array(first_product["embedding"])
            similar_items = find_similar_items_mongo(embedding, top_k + 1)
            
            # Filter out the query product itself
            filtered = [
                (prod, score) for prod, score in similar_items
                if str(prod.get("_id")) != str(first_product.get("_id"))
            ]
            results = [product_to_dict(prod, score) for prod, score in filtered[:top_k]]
        else:
            results = [product_to_dict(p) for p in products[:top_k]]

        return {"status": "success", "results": results, "total": len(results)}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 3. Product catalogue (browse page) ─────────────────────────────────────
@app.get("/api/products")
def list_products(
    product_type: Optional[str] = Query(None),
    color:        Optional[str] = Query(None),
    brand:        Optional[str] = Query(None),
    sort:         str           = Query("relevance", enum=["relevance", "price_asc", "price_desc", "rating"]),
    page:         int           = Query(1, ge=1),
    per_page:     int           = Query(20, ge=1, le=100),
):
    """Paginated product listing for browse_products.html."""
    try:
        # Build MongoDB query
        query = {}
        
        if product_type:
            query["product_type"] = product_type.lower()
        if color:
            query["colour"] = color.lower()
        if brand:
            query["brand"] = {"$regex": brand, "$options": "i"}

        # Get all matching products
        all_products = search_products(query, limit=50000)
        total = len(all_products)

        # Sort
        if sort == "price_asc":
            all_products.sort(
                key=lambda x: float(x.get("price", 0) or 0),
                reverse=False
            )
        elif sort == "price_desc":
            all_products.sort(
                key=lambda x: float(x.get("price", 0) or 0),
                reverse=True
            )
        elif sort == "rating":
            all_products.sort(
                key=lambda x: float(x.get("rating", 0) or 0),
                reverse=True
            )

        # Paginate
        start = (page - 1) * per_page
        page_products = all_products[start: start + per_page]

        products = [product_to_dict(p) for p in page_products]
        pages = (total + per_page - 1) // per_page

        return {
            "status":   "success",
            "results":  products,
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "pages":    pages,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 4. Single product detail ────────────────────────────────────────────────
@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    """Return one product + similar items. Used by product_detail.html."""
    try:
        product = get_product_by_id(product_id)

        if product is None:
            raise HTTPException(404, f"Product {product_id} not found")

        product_dict = product_to_dict(product)

        # Find similar items
        if "embedding" in product:
            embedding = np.array(product["embedding"])
            similar_items = find_similar_items_mongo(embedding, 6)
            
            # Filter out the product itself
            similar = [
                product_to_dict(prod, score) 
                for prod, score in similar_items
                if str(prod.get("_id")) != str(product.get("_id"))
            ][:5]
        else:
            similar = []

        return {
            "status": "success",
            "product": product_dict,
            "similar": similar
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 5. Skin-tone analysis only ──────────────────────────────────────────────
@app.post("/api/analyze/skin-tone")
async def analyze_skin_tone(file: UploadFile = File(...)):
    """Detect skin tone from uploaded photo."""
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)
        tone     = detect_skin_tone_from_array(img_arr)
        color    = get_dominant_color_name(img_arr)
        return {"status": "success", "skin_tone": tone, "dominant_color": color}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 6. Product-type detection from text ────────────────────────────────────
@app.get("/api/detect/product-type")
def detect_type(text: str = Query(...)):
    return {"status": "success", "product_type": detect_product_type(text)}


# ── 7. Dataset stats (dashboard / debug) ───────────────────────────────────
@app.get("/api/stats")
def get_stats():
    try:
        products = get_all_products(limit=50000)
        
        # Count statistics
        product_types = {}
        colors = {}
        brands = set()
        clusters = set()
        embedding_dim = 0

        for prod in products:
            ptype = prod.get("product_type", "unknown")
            product_types[ptype] = product_types.get(ptype, 0) + 1
            
            color = prod.get("colour", "unknown")
            colors[color] = colors.get(color, 0) + 1
            
            if prod.get("brand"):
                brands.add(prod.get("brand"))
            
            if prod.get("cluster"):
                clusters.add(prod.get("cluster"))
            
            if "embedding" in prod and embedding_dim == 0:
                embedding_dim = len(prod["embedding"])

        return {
            "status":         "success",
            "total_products": len(products),
            "embedding_dim":  embedding_dim,
            "product_types":  product_types,
            "colors":         colors,
            "brands":         len(brands),
            "clusters":       len(clusters),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))
