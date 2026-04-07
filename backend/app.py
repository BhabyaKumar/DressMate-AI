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
from sklearn.cluster import KMeans
from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# MongoDB imports
from database import (
    connect_to_mongodb,
    close_mongodb,
    get_all_products,
    get_product_by_id,
    get_products_by_ids,
    search_products,
    insert_recommendation,
    insert_user_interaction,
    normalize_user_id,
    update_user,
    get_user_recommendations,
)

# Authentication imports
from auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserProfile,
    register_user,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    update_user_preferences,
)

# ── lazy-load heavy assets ─────────────────────────────────────────────────
_resnet = None


def get_resnet():
    """Lazy-load TensorFlow ResNet50 only when needed."""
    global _resnet
    if _resnet is None:
        from tensorflow.keras.applications import ResNet50
        _resnet = ResNet50(weights="imagenet", include_top=False, pooling="avg")
    return _resnet

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ── helper utilities ───────────────────────────────────────────────────────

def extract_features_from_array(img_array: np.ndarray) -> np.ndarray:
    """Extract ResNet50 features from an RGB numpy array (H×W×3)."""
    from tensorflow.keras.applications.resnet50 import preprocess_input

    img = Image.fromarray(img_array).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = np.expand_dims(arr, axis=0)
    arr = preprocess_input(arr)

    model = get_resnet()
    features = model.predict(arr, verbose=0)
    return features.flatten().astype(np.float32)


def find_similar_items_mongo(query_vector: np.ndarray, top_k: int = 8) -> List[tuple]:
    """
    Find similar items by computing cosine similarity with all embeddings in MongoDB.
    Returns list of (product_dict, similarity_score) tuples.
    """
    products = get_all_products(limit=50000)

    query_vector = np.asarray(query_vector, dtype=np.float32).reshape(-1)
    query_norm = np.linalg.norm(query_vector)
    if query_norm == 0:
        return []

    similarities: List[tuple] = []
    batch_products: List[dict] = []
    batch_embeddings: List[np.ndarray] = []
    batch_size = 2048

    def flush_batch() -> None:
        nonlocal batch_products, batch_embeddings, similarities
        if not batch_products:
            return

        embedding_matrix = np.stack(batch_embeddings).astype(np.float32)
        embedding_norms = np.linalg.norm(embedding_matrix, axis=1)
        valid_mask = embedding_norms > 0
        if np.any(valid_mask):
            normalized_embeddings = embedding_matrix[valid_mask] / embedding_norms[valid_mask, None]
            scores = normalized_embeddings @ (query_vector / query_norm)
            for product, score in zip(np.array(batch_products, dtype=object)[valid_mask], scores):
                similarities.append((product, float(score)))

        batch_products = []
        batch_embeddings = []

    for product in products:
        embedding = product.get("embedding")
        if embedding is None:
            continue

        try:
            embedding_array = np.asarray(embedding, dtype=np.float32).reshape(-1)
        except Exception:
            continue

        if embedding_array.shape[0] != query_vector.shape[0]:
            continue

        batch_products.append(product)
        batch_embeddings.append(embedding_array)

        if len(batch_products) >= batch_size:
            flush_batch()

    flush_batch()

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


class RecommendationFeedback(BaseModel):
    """Feedback payload used to learn user preferences over time."""
    product_id: str
    action: str  # click | like | dislike | save
    source: Optional[str] = "recommendation_results"


def _get_user_document(user_id: str) -> Optional[dict]:
    """Resolve user document for both ObjectId and numeric IDs."""
    from database import db
    from bson.objectid import ObjectId

    if db is None:
        return None

    try:
        return db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        try:
            return db.users.find_one({"_id": int(user_id)})
        except Exception:
            return None


def rerank_with_user_preferences(items: List[tuple], user_id: str) -> List[tuple]:
    """Re-rank candidate products using each user's own profile and interaction history."""
    from database import db

    if db is None or not items:
        return items

    user_doc = _get_user_document(user_id)
    preferred_colors = set(c.lower() for c in (user_doc or {}).get("preferred_colors", []))
    preferred_types = set(t.lower() for t in (user_doc or {}).get("preferred_types", []))

    interactions = list(db.user_interactions.find(
        {"user_id": normalize_user_id(user_id)}
    ).sort("created_at", -1).limit(300))

    liked_ids = {str(i.get("product_id")) for i in interactions if i.get("action") in ["like", "save", "click"]}
    disliked_ids = {str(i.get("product_id")) for i in interactions if i.get("action") == "dislike"}

    reranked: List[tuple] = []
    for product, base_score in items:
        score = float(base_score)
        product_id = str(product.get("_id", ""))
        product_type = str(product.get("product_type", "")).lower()
        product_color = str(product.get("colour", "")).lower()

        if product_type and product_type in preferred_types:
            score += 0.08
        if product_color and product_color in preferred_colors:
            score += 0.06
        if product_id in liked_ids:
            score += 0.12
        if product_id in disliked_ids:
            score -= 0.15

        reranked.append((product, score))

    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked


def learn_from_feedback(user_id: str, product_id: str, action: str) -> None:
    """Persist interaction and gradually update user preferences."""
    action = action.lower().strip()
    if action not in {"click", "like", "dislike", "save"}:
        return

    insert_user_interaction({
        "user_id": user_id,
        "product_id": product_id,
        "action": action,
        "created_at": datetime.utcnow(),
    })

    if action not in {"click", "like", "save"}:
        return

    product = get_product_by_id(product_id)
    if not product:
        return

    user_doc = _get_user_document(user_id)
    if not user_doc:
        return

    update_ops = {
        "$inc": {"interaction_count": 1},
    }

    color = str(product.get("colour", "")).strip().lower()
    ptype = str(product.get("product_type", "")).strip().lower()

    add_to_set = {}
    if color:
        add_to_set["preferred_colors"] = color
    if ptype:
        add_to_set["preferred_types"] = ptype

    if add_to_set:
        update_ops["$addToSet"] = add_to_set

    update_user(str(user_doc.get("_id")), update_ops)


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


# ── Authentication endpoints ───────────────────────────────────────────────

@app.post("/api/auth/register", response_model=TokenResponse)
def register(user_data: UserRegister):
    """
    Register a new user.
    Returns access token and user info on success.
    """
    try:
        user_id = register_user(user_data.email, user_data.password, user_data.name)
        token = create_access_token(user_id, user_data.email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
            "email": user_data.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/auth/login", response_model=TokenResponse)
def login(credentials: UserLogin):
    """
    Login user with email and password.
    Returns access token and user info on success.
    """
    try:
        user = authenticate_user(credentials.email, credentials.password)
        token = create_access_token(str(user["_id"]), credentials.email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user["_id"]),
            "email": credentials.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.get("/api/auth/profile", response_model=UserProfile)
def get_profile(current_user: dict = Depends(get_current_user)):
    """
    Get current user profile.
    Requires authentication token.
    """
    try:
        from database import db
        from bson.objectid import ObjectId
        
        user_id = current_user.get("user_id")
        try:
            user = db.users.find_one({"_id": ObjectId(user_id)})
        except:
            user = db.users.find_one({"_id": int(user_id)})
        
        if not user:
            raise HTTPException(404, "User not found")
        
        return {
            "user_id": str(user["_id"]),
            "email": user.get("email", ""),
            "name": user.get("name", "User"),
            "skin_tone": user.get("skin_tone"),
            "preferred_colors": user.get("preferred_colors", []),
            "preferred_types": user.get("preferred_types", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 1. Image-based recommendation (core feature) ───────────────────────────
@app.post("/api/recommend/image")
async def recommend_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(8, ge=1, le=50),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Upload an image → get similar fashion items.
    Uses ResNet50 feature extraction and cosine similarity search in MongoDB.
    Optional: Pass Authorization token to save to recommendation history.
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

        # Personalize ranking with this specific user's history/preferences.
        if current_user and current_user.get("user_id"):
            similar_items = rerank_with_user_preferences(similar_items, current_user.get("user_id"))

        products = [product_to_dict(prod, score) for prod, score in similar_items]

        # Save to user's recommendation history if authenticated
        if current_user:
            try:
                normalized_user_id = normalize_user_id(current_user.get("user_id"))
                insert_recommendation({
                    "user_id": normalized_user_id,
                    "type": "image",
                    "skin_tone": skin_tone,
                    "color": color,
                    "product_ids": [p["id"] for p in products],
                    "created_at": datetime.utcnow(),
                })
                update_user(normalized_user_id, {"$inc": {"recommendation_count": 1}})
            except:
                pass  # Silently fail if history save fails

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
    current_user: dict = Depends(get_current_user_optional),
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

            if current_user and current_user.get("user_id"):
                similar_items = rerank_with_user_preferences(similar_items, current_user.get("user_id"))
            
            # Filter out the query product itself
            filtered = [
                (prod, score) for prod, score in similar_items
                if str(prod.get("_id")) != str(first_product.get("_id"))
            ]
            results = [product_to_dict(prod, score) for prod, score in filtered[:top_k]]
        else:
            results = [product_to_dict(p) for p in products[:top_k]]

        if current_user and current_user.get("user_id"):
            try:
                normalized_user_id = normalize_user_id(current_user.get("user_id"))
                insert_recommendation({
                    "user_id": normalized_user_id,
                    "type": "text",
                    "query": {
                        "product_type": product_type.lower(),
                        "color": color.lower() if color else "",
                    },
                    "product_ids": [p["id"] for p in results],
                    "created_at": datetime.utcnow(),
                })
                update_user(normalized_user_id, {"$inc": {"recommendation_count": 1}})
            except Exception:
                pass

        return {"status": "success", "results": results, "total": len(results)}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 2.5. Product search endpoint ──────────────────────────────────────────
@app.get("/api/search")
def search_products_endpoint(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
):
    """Search products by name, brand, or description."""
    try:
        # Build MongoDB filter for text search across multiple fields
        search_filter = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"brand": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"colour": {"$regex": query, "$options": "i"}}
            ]
        }
        products = search_products(search_filter, limit=limit)
        
        if not products:
            return {"status": "success", "results": [], "total": 0}
        
        # Convert to dict format with similarity if available
        results = [product_to_dict(p) for p in products]
        
        return {
            "status": "success",
            "results": results,
            "total": len(results),
            "query": query
        }
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


# ── 7. User recommendation history ────────────────────────────────────────
@app.get("/api/history")
def get_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Get user's recommendation history."""
    try:
        user_id = current_user.get("user_id")
        recommendations = get_user_recommendations(user_id, limit)
        return {
            "status": "success",
            "total": len(recommendations),
            "history": [
                {
                    "id": str(rec.get("_id", "")),
                    "type": rec.get("type", ""),
                    "created_at": str(rec.get("created_at", "")),
                    "details": {
                        "skin_tone": rec.get("skin_tone"),
                        "color": rec.get("color"),
                        "product_ids": rec.get("product_ids", []),
                    }
                }
                for rec in recommendations
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/recommend/feedback")
def submit_feedback(
    payload: RecommendationFeedback,
    current_user: dict = Depends(get_current_user),
):
    """Capture user feedback so future recommendations improve per user."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(401, "Unauthorized")

        learn_from_feedback(user_id, payload.product_id, payload.action)

        return {
            "status": "success",
            "message": "Feedback recorded",
            "action": payload.action.lower().strip(),
            "product_id": payload.product_id,
            "source": payload.source,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 8. AI Chat with Gemini ────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(
    message: str = Query(..., description="User message"),
    current_user: dict = Depends(get_current_user),
):
    """
    Chat with AI stylist powered by Gemini.
    Requires authentication token.
    """
    try:
        # Get user profile for context
        from database import db
        from bson.objectid import ObjectId
        
        user_id = current_user.get("user_id")
        try:
            user = db.users.find_one({"_id": ObjectId(user_id)})
        except:
            user = db.users.find_one({"_id": int(user_id)})
        
        # Import Gemini API
        import google.generativeai as genai
        
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(
                400,
                "Gemini API key not configured. Set GEMINI_API_KEY in .env"
            )
        genai.configure(api_key=api_key)
        
        # Build context from user profile
        context = f"""You are a professional fashion stylist AI assistant. You help users find perfect outfits and fashion advice.

User Profile:
- Name: {user.get('name', 'User') if user else 'User'}
- Skin Tone: {user.get('skin_tone', 'Unknown') if user else 'Unknown'}
- Preferred Colors: {', '.join(user.get('preferred_colors', [])) if user else 'Not set'}
- Preferred Types: {', '.join(user.get('preferred_types', [])) if user else 'Not set'}

Be helpful, professional, and personalized. Provide fashion recommendations based on their profile."""
        
        # Create model and generate response
        model = genai.GenerativeModel('gemini-pro')
        full_prompt = context + "\n\nUser: " + message
        response = model.generate_content(full_prompt)
        
        return {
            "status": "success",
            "message": message,
            "response": response.text,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Chat error: {str(e)}")


# ── 9. Dataset stats (dashboard / debug) ───────────────────────────────────
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
