"""
FashionAI Backend - FastAPI Server with MongoDB
===============================================
Integrates all backend modules into a REST API using MongoDB for data persistence.

Setup:
  pip install fastapi uvicorn python-multipart scikit-learn numpy pandas
              pillow opencv-python-headless tensorflow pymongo python-dotenv
              google-generativeai

Configuration:
  1. Create a .env file in the backend directory with:
     GEMINI_API_KEY=your_api_key_here
  2. Get your free Gemini API key from: https://ai.google.dev/

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
from datetime import datetime, timedelta
from dotenv import load_dotenv
import hashlib
import json

import numpy as np
import cv2
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
from vision.skin_tone_detector import detect_skin_properties_from_array, recommend_colors
from vision.body_shape_detector import detect_body_shape
from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

# Load environment variables from .env file
load_dotenv()

# MongoDB imports
from database.config import (
    connect_to_mongodb,
    close_mongodb,
    get_all_products,
    get_product_by_id,
    search_products,
    insert_recommendation,
    get_user_recommendations,
)

# Authentication imports
from auth.auth import (
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
from mock_catalog import get_mock_products

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
FRONTEND_DIR = BASE_DIR.parent / "frontend"

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


def find_similar_items_mongo(query_vector: np.ndarray, top_k: int = 8, filter_product: dict = None) -> List[tuple]:
    """
    Find similar items by computing cosine similarity with embeddings in MongoDB.
    Optimized to filter by cluster/type first instead of scanning all products.
    Returns list of (product_dict, similarity_score) tuples.
    """
    # First, get all products but limit initially to 10k for performance
    products = safe_get_all_products(limit=10000)
    
    # If filter_product provided, further filter by matching type/cluster
    search_candidates = []
    if filter_product:
        filter_cluster = filter_product.get("cluster")
        filter_type = filter_product.get("product_type", "").lower()
        
        # First pass: exact cluster match + has embedding
        for product in products:
            if "embedding" not in product:
                continue
            if product.get("cluster") == filter_cluster:
                search_candidates.append(product)
        
        # If cluster match insufficient, add same product_type matches
        if len(search_candidates) < top_k * 3:
            for product in products:
                if "embedding" not in product:
                    continue
                if product.get("product_type", "").lower() == filter_type and product not in search_candidates:
                    search_candidates.append(product)
        
        # Fill remaining with any product with embedding
        if len(search_candidates) < top_k * 3:
            for product in products:
                if "embedding" in product and product not in search_candidates:
                    search_candidates.append(product)
    else:
        search_candidates = [p for p in products if "embedding" in p]
    
    # Limit search space to top 5000 candidates for performance
    search_candidates = search_candidates[:5000]
    
    # Compute similarities using vectorized operations for speed
    similarities = []
    query_reshaped = query_vector.reshape(1, -1)
    
    for product in search_candidates:
        try:
            embedding = np.array(product["embedding"])
            score = cosine_similarity(query_reshaped, embedding.reshape(1, -1))[0][0]
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
    """
    Enhanced skin tone detection using LAB color space.
    Delegates to skin_tone module for improved accuracy.
    """
    result = detect_skin_properties_from_array(img_rgb)
    tone = result.get("tone", "medium")

    # Map to title case for API consistency
    return tone.capitalize()  # "fair", "medium", "dark" -> "Fair", "Medium", "Dark"


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
        "style_tags":   list(product.get("style_tags", [])),
    }


def safe_get_all_products(limit: int = 50000) -> List[dict]:
    try:
        products = get_all_products(limit=limit)
    except Exception:
        products = []
    return products or get_mock_products()[:limit]


def safe_search_products(query: dict, limit: int = 50) -> List[dict]:
    try:
        products = search_products(query, limit=limit)
    except Exception:
        products = []

    if products:
        return products

    catalog = safe_get_all_products(limit=50000)
    results = []

    def matches(product: dict, current_query: dict) -> bool:
        for key, value in current_query.items():
            if key == "$or":
                return any(matches(product, sub_query) for sub_query in value)

            product_value = str(product.get(key, ""))
            if isinstance(value, dict):
                if "$regex" in value:
                    if value["$regex"].lower() not in product_value.lower():
                        return False
                else:
                    return False
            else:
                if product_value.lower() != str(value).lower():
                    return False
        return True

    for product in catalog:
        if matches(product, query):
            results.append(product)
            if len(results) >= limit:
                break
    return results


def safe_get_product_by_id(product_id: str) -> Optional[dict]:
    try:
        product = get_product_by_id(product_id)
    except Exception:
        product = None
    if product:
        return product
    for item in safe_get_all_products(limit=50000):
        if str(item.get("_id")) == str(product_id):
            return item
    return None


STYLE_TYPE_MAP = {
    "casual": {"dress", "top", "shirt", "jeans", "tshirt", "jacket"},
    "formal": {"dress", "shirt", "jacket", "saree"},
    "ethnic": {"kurta", "saree"},
    "kurta": {"kurta"},
    "streetwear": {"jeans", "jacket", "tshirt", "shirt"},
    "minimalist": {"shirt", "top", "jacket", "jeans"},
    "boho": {"dress", "top", "skirt"},
    "activewear": {"tshirt", "leggings", "shorts"},
    "party": {"dress", "saree", "skirt"},
}


def normalize_skin_tone(tone: Optional[str]) -> str:
    value = str(tone or "").strip().lower()
    # Map all variants to the 3 detector-supported values
    aliases = {
        "fair": "fair",
        "light": "fair",      # Light maps to Fair
        "medium": "medium",
        "warm": "medium",      # Warm maps to Medium (undertone, not tone)
        "tan": "medium",       # Tan maps to Medium
        "deep": "deep",
        "dark": "deep",
    }
    return aliases.get(value, value or "medium")


def normalize_body_shape_value(body_shape: Optional[str]) -> str:
    value = str(body_shape or "").strip().lower().replace("_", " ")
    aliases = {
        "inverted triangle": "inverted triangle",
        "triangle": "inverted triangle",
        "hourglass": "hourglass",
        "pear": "pear",
        "apple": "apple",
        "rectangle": "rectangle",
        "athletic": "rectangle",
    }
    return aliases.get(value, value)


def normalize_style_types(dress_types: List[str]) -> List[str]:
    normalized = []
    for item in dress_types:
        value = str(item).strip().lower()
        if value:
            normalized.append(value)
    return normalized


def score_style_match(product: dict, skin_tone: str, body_shape: str, dress_types: List[str], selected_color: Optional[str] = None) -> float:
    """
    Score a product against user preferences.
    Properly weights skin tone, body shape, and dress type.

    Parameters:
    - product: Product dict from database
    - skin_tone: Normalized skin tone (fair, medium, deep)
    - body_shape: Normalized body shape
    - dress_types: List of normalized dress type preferences
    - selected_color: Optional user-selected color name (e.g., "gold")
    """
    score = 0.0
    product_type = str(product.get("product_type", "")).lower()
    product_color = str(product.get("colour", "")).lower()
    style_tags = [str(tag).lower() for tag in product.get("style_tags", [])]

    # Base score from rating (0-1)
    base_rating_score = float(product.get("rating", 3.0) or 3.0) / 5.0
    score += base_rating_score * 1.5  # Rating contributes 0-1.5 points

    # ========== USER SELECTED COLOR BONUS ==========
    # Strong bonus if user selected a specific color
    if selected_color:
        selected_color_lower = selected_color.lower()
        # Exact or fuzzy match
        if selected_color_lower in product_color or product_color in selected_color_lower:
            score += 1.0  # Bonus for color match
        # If no match, no penalty (to preserve other good matches)

    # ========== SKIN TONE MATCHING ==========
    # Strategy: Match on color recommendations for detected skin tone
    # Even if product lacks explicit recommended_skin_tones field
    if skin_tone:
        # Get colors recommended for this skin tone
        skin_tone_normalized = normalize_skin_tone(skin_tone).lower()
        recommended_colors = recommend_colors(skin_tone_normalized, "neutral")
        recommended_colors_lower = [c.lower() for c in recommended_colors]

        # Check if product color is in recommended colors (fuzzy match)
        color_match = False
        for rec_color in recommended_colors_lower:
            if rec_color in product_color or product_color in rec_color:
                color_match = True
                break

        if color_match:
            score += 2.5  # Strong bonus for color match
        else:
            # Small penalty for color mismatch (not total rejection)
            score -= 0.5

    # ========== BODY SHAPE MATCHING ==========
    # For now, use a simple heuristic based on product type
    # (Better: would need body_shape to product_type mapping)
    if body_shape:
        body_shape_lower = str(body_shape).strip().lower()

        # Simple heuristic: certain shapes work better with certain types
        shape_type_map = {
            "hourglass": {"dress", "skirt", "saree"},      # Fitted styles highlight curves
            "apple": {"top", "jacket", "loose dress"},    # Draw attention to legs
            "pear": {"off-shoulder", "top", "jacket"},    # Balance upper/lower
            "rectangle": {"dress", "saree", "kurta"},     # Add curves with patterns
            "inverted triangle": {"a-line dress", "skirt", "pants"}, # Balance shoulders
        }

        if body_shape_lower in shape_type_map:
            recommended_types = shape_type_map[body_shape_lower]
            if product_type in recommended_types or any(t in style_tags for t in recommended_types):
                score += 1.5  # Bonus for body-shape-appropriate style
        else:
            score += 0.5  # Minimum bonus regardless

    # ========== DRESS TYPE MATCHING ==========
    # Strong weighting on user preferences
    if dress_types:
        for item in dress_types:
            item_lower = item.lower()
            if item_lower == product_type or item_lower in style_tags:
                score += 3.0  # Exact match
            elif product_type in STYLE_TYPE_MAP.get(item_lower, set()):
                score += 2.5  # Indirect match via STYLE_TYPE_MAP

    # Small bonus for name/description length (longer = more specific)
    score += 0.1 * min(len(str(product.get("name", ""))), 50)

    return round(score, 4)


# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="FashionAI API",
    description="Backend for the AI Fashion Recommendation Frontend (MongoDB Version)",
    version="2.0.0",
)

# ── Simple in-memory cache for chat responses ───────────────────────────────
_chat_cache = {}  # {cache_key: (response, timestamp)}
_CACHE_TTL = 3600  # 1 hour cache lifetime
_REQUEST_COUNTS = {}  # Track requests per user per day


def get_fallback_response(message: str, user: dict = None) -> str:
    """Provide intelligent fallback responses when API quota is exceeded."""
    message_lower = message.lower()

    # Extract user info for personalized responses
    skin_tone = user.get('skin_tone', '').lower() if user else ''
    preferred_colors = [c.lower() for c in (user.get('preferred_colors', []) if user else [])]

    # Fashion color recommendations based on skin tone
    color_recommendations = {
        'fair': ['jewel tones', 'deep reds', 'emerald green', 'sapphire blue', 'soft pastels'],
        'light': ['warm colors', 'peach', 'coral', 'gold', 'cream'],
        'medium': ['warm and cool tones', 'burnt orange', 'terracotta', 'navy', 'gold'],
        'warm': ['earth tones', 'olive', 'rust', 'chocolate', 'gold'],
        'tan': ['warm colors', 'bronze', 'copper', 'warm red', 'caramel'],
        'deep': ['jewel tones', 'rich purples', 'emerald', 'sapphire', 'gold', 'silver'],
        'dark': ['bold colors', 'bright jewel tones', 'metallics', 'deep purples'],
    }

    # Match user's skin tone
    recommended_colors_list = []
    for tone, colors in color_recommendations.items():
        if tone in skin_tone:
            recommended_colors_list = colors
            break

    # Intelligent responses based on keywords
    if any(word in message_lower for word in ['color', 'colour', 'tone', 'shade']):
        if recommended_colors_list:
            color_str = ', '.join(recommended_colors_list[:4])
            return f"**Based on your {skin_tone} skin tone**, these colors would look stunning:\n\n• {color_str}\n\n**Tips:** Jewel tones and metallics create beautiful contrast. Avoid colors that wash you out. Try on pieces to see what makes you feel confident!"
        else:
            return "**Color choice tips:** Look for colors that make your eyes pop and complement your natural undertones. Jewel tones, warm earth tones, and metallics are universally flattering. Try holding colors up to your face to test what works best!"

    elif any(word in message_lower for word in ['style', 'occasion', 'outfit', 'wear']):
        return "**Style suggestions:** The key to great outfits is balance! Pair comfortable basics with statement pieces. Consider your body shape, skin tone, and personal preference. **Pro tip:** Invest in quality basics (white shirt, jeans, neutral blazer) that you can mix and match!"

    elif any(word in message_lower for word in ['accessory', 'jewelry', 'bag', 'shoe']):
        return "**Accessory guide:** \n\n• **Jewelry:** Gold metallics are universally flattering. Choose simple pieces for casual, bold statement pieces for formal events.\n• **Bags:** Neutral colors (black, brown, tan) go with everything.\n• **Shoes:** Comfort matters! Choose styles that match the occasion and your outfit's vibe."

    elif any(word in message_lower for word in ['body shape', 'figure', 'fit', 'fits me']):
        return "**Body-shape styling tips:** Every body shape is beautiful! The goal is to wear what makes YOU feel confident:\n\n• **Fit:** Choose pieces that fit your natural curves.\n• **Proportions:** Balance volume - if wearing wide pants, try a fitted top.\n• **Length:** Experiment with different lengths to see what flatters you most.\n• **Confidence:** The best outfit is one you feel amazing in!"

    elif any(word in message_lower for word in ['formal', 'gala', 'wedding', 'event']):
        return "**Formal wear guide:**\n\n• **Dress code:** Always check the invitation for specific requirements.\n• **Colors:** Jewel tones and classic colors (black, navy, burgundy) are safe choices.\n• **Fit:** Ensure everything fits well and allows comfortable movement.\n• **Accessories:** Let your outfit be the star - keep jewelry elegant but not overwhelming.\n• **Confidence:** Stand tall and own your look!"

    else:
        # Generic helpful response
        return f"I'd love to help with your fashion question! Here are some general tips:\n\n**For better styling:**\n• Know your skin tone and which colors flatter you\n• Understand your body shape and what fits well\n• Invest in quality basics you can mix and match\n• Wear what makes you feel confident\n• Don't follow trends blindly - wear what suits YOU\n\n**Note:** Using offline mode (quota exceeded). Upgrade at https://ai.google.dev/pricing for unlimited AI assistance!"

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
        print(f"[ok] Serving images from: {_img_path}")
        break

# Serve frontend files under /frontend
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    print(f"[ok] Serving frontend from: {FRONTEND_DIR}")


# ── Startup / Shutdown events ──────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    """Initialize MongoDB connection on app startup."""
    print("[start] Starting FashionAI Backend...")
    if connect_to_mongodb():
        print("[ok] MongoDB ready, app started successfully!")
    else:
        print("[warn] MongoDB connection failed. Some features may not work.")


@app.on_event("shutdown")
def shutdown_event():
    """Close MongoDB connection on app shutdown."""
    print("[stop] Shutting down FashionAI Backend...")
    close_mongodb()


# ── endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "FashionAI API (MongoDB) is running",
        "frontend": "/frontend/login.html",
    }


@app.get("/{page_name}.html", include_in_schema=False)
def frontend_page_shortcut(page_name: str):
    """Support direct URLs like /login.html by redirecting to /frontend/login.html."""
    frontend_page = FRONTEND_DIR / f"{page_name}.html"
    if FRONTEND_DIR.exists() and frontend_page.exists():
        return RedirectResponse(url=f"/frontend/{page_name}.html")
    raise HTTPException(status_code=404, detail="Not Found")


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
        from database.config import db
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

        products = []
        try:
            features = extract_features_from_array(img_arr)
            similar_items = find_similar_items_mongo(features, top_k)
            products = [product_to_dict(prod, score) for prod, score in similar_items]
        except Exception:
            traceback.print_exc()

        if not products:
            fallback_products = safe_get_all_products(limit=top_k)
            products = [product_to_dict(prod, 1.0) for prod in fallback_products]

        # Save to user's recommendation history if authenticated
        if current_user:
            try:
                insert_recommendation({
                    "user_id": current_user.get("user_id"),
                    "type": "image",
                    "skin_tone": skin_tone,
                    "product_ids": [p["id"] for p in products],
                    "created_at": datetime.utcnow(),
                })
            except:
                pass  # Silently fail if history save fails

        return {
            "status":    "success",
            "skin_tone": skin_tone,
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
        products = safe_search_products(query, limit=100)

        if not products:
            return {"status": "success", "results": [], "total": 0}

        # If color filter specified, apply it
        if color:
            products = [p for p in products 
                       if p.get("colour", "").lower() == color.lower()]

        if not products:
            return {"status": "success", "results": [], "total": 0}

        # Find similar items to first result (with filter optimization)
        first_product = products[0]
        if "embedding" in first_product:
            embedding = np.array(first_product["embedding"])
            similar_items = find_similar_items_mongo(embedding, top_k + 1, filter_product=first_product)
            
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
        products = safe_search_products(search_filter, limit=limit)
        
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
        all_products = safe_search_products(query, limit=50000)
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
        product = safe_get_product_by_id(product_id)

        if product is None:
            raise HTTPException(404, f"Product {product_id} not found")

        product_dict = product_to_dict(product)

        # Find similar items (optimized with product filter)
        if "embedding" in product:
            embedding = np.array(product["embedding"])
            similar_items = find_similar_items_mongo(embedding, top_k=6, filter_product=product)
            
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
@app.get("/api/batch-products")
def get_products_batch(ids: str = Query(..., description="Comma-separated product ids")):
    try:
        requested_ids = [item.strip() for item in ids.split(",") if item.strip()]
        results = []
        for product_id in requested_ids:
            product = safe_get_product_by_id(product_id)
            if product:
                results.append(product_to_dict(product))
        return {"status": "success", "results": results, "total": len(results)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/analyze/skin-tone")
async def analyze_skin_tone(file: UploadFile = File(...)):
    """Detect skin tone and undertone from uploaded photo."""
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)
        # Get full skin properties (tone, undertone, brightness)
        properties = detect_skin_properties_from_array(img_arr)
        tone = properties.get("tone", "medium").capitalize()
        undertone = properties.get("undertone", "neutral").lower()
        return {"status": "success", "skin_tone": tone, "undertone": undertone}
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


# ── 8. AI Chat with Gemini ────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(
    message: str = Query(..., description="User message"),
    history: str = Query("", description="Previous chat history (JSON format)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Chat with AI stylist powered by Gemini.
    Supports multi-turn conversations with history.

    Request:
    POST /api/chat?message=Hello&history=[...]
    """
    try:
        # Get user profile for context
        from database.config import db
        from bson.objectid import ObjectId

        user_id = current_user.get("user_id")
        user = None

        try:
            user = db.users.find_one({"_id": ObjectId(user_id)})
        except:
            try:
                user = db.users.find_one({"_id": int(user_id)})
            except:
                user = None

        # Import Gemini API
        try:
            import google.generativeai as genai
        except ImportError:
            raise HTTPException(
                503,
                "Gemini SDK not installed. Run: pip install google-generativeai"
            )

        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY", "").strip()

        if not api_key or api_key == "YOUR_GEMINI_API_KEY":
            print("[error] GEMINI_API_KEY is not set or is placeholder")
            raise HTTPException(
                500,
                "Gemini API key not configured. Please:\n"
                "1. Run: python setup_api_key.py\n"
                "2. Paste your API key from https://ai.google.dev/\n"
                "3. Restart the backend server"
            )

        # Configure Gemini
        genai.configure(api_key=api_key)

        # Build personalized context from user profile
        user_context = "User Profile:\n"
        if user:
            user_context += f"- Name: {user.get('name', 'User')}\n"
            user_context += f"- Email: {user.get('email', 'N/A')}\n"
            skin_tone = user.get('skin_tone')
            if skin_tone:
                user_context += f"- Skin Tone: {skin_tone}\n"
            preferred_colors = user.get('preferred_colors', [])
            if preferred_colors:
                user_context += f"- Preferred Colors: {', '.join(preferred_colors)}\n"
            preferred_types = user.get('preferred_types', [])
            if preferred_types:
                user_context += f"- Preferred Types: {', '.join(preferred_types)}\n"
        else:
            user_context += "- Unknown user\n"

        system_prompt = f"""You are DressMate, a professional AI fashion stylist assistant. You help users find perfect outfits, provide fashion advice, and make personalized recommendations based on their style profile.

{user_context}

Instructions:
- Be friendly, professional, and personalized
- Provide specific, actionable fashion recommendations
- Consider the user's skin tone and body shape in suggestions
- Suggest colors, styles, and fabrics that complement their profile
- Ask clarifying questions if needed
- Provide complete, detailed responses
- Use fashion terminology confidently
- Be encouraging and positive about fashion choices
- Remember previous parts of the conversation for context"""

        # Build conversation history
        conversation = system_prompt + "\n\n"

        # Add previous messages if history provided
        if history:
            try:
                import json
                history_list = json.loads(history)
                for msg in history_list:
                    if msg.get('role') == 'user':
                        conversation += f"User: {msg.get('content', '')}\n\n"
                    elif msg.get('role') == 'assistant':
                        conversation += f"Assistant: {msg.get('content', '')}\n\n"
            except:
                pass  # If history parsing fails, continue without it

        # Add current user message
        conversation += f"User: {message}\n\nAssistant:"

        # Create model and generate response
        # Use gemini-2.0-flash-lite (higher free quota) as primary
        model_name = 'gemini-2.0-flash-lite'
        try:
            model = genai.GenerativeModel(model_name)
        except:
            try:
                model_name = 'gemini-2.0-flash'
                model = genai.GenerativeModel(model_name)
            except:
                model_name = 'gemini-2.5-flash'
                model = genai.GenerativeModel(model_name)

        response = model.generate_content(
            conversation,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=2000,  # Increased for full responses
            )
        )

        if not response or not response.text:
            raise HTTPException(500, "Gemini API returned empty response")

        return {
            "status": "success",
            "message": message,
            "response": response.text.strip(),
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"[error] Chat error: {error_msg}")
        traceback.print_exc()

        # Graceful fallback for quota exceeded
        if "quota" in error_msg.lower() or "429" in error_msg:
            print(f"[warn] API quota exceeded, using fallback mode")
            fallback_response = get_fallback_response(message, user if 'user' in locals() else None)
            return {
                "status": "success",
                "message": message,
                "response": fallback_response,
                "mode": "fallback",
                "notice": "⚠ Using offline mode (quota exceeded). Upgrade your plan at https://ai.google.dev/pricing",
            }

        raise HTTPException(500, f"Chat error: {error_msg}")


# ── 9. Dataset stats (dashboard / debug) ───────────────────────────────────
@app.get("/api/stats")
def get_stats():
    try:
        products = safe_get_all_products(limit=50000)
        
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


# ── 10. Body shape analysis from image ─────────────────────────────────────
@app.post("/api/analyze/body-shape")
async def analyze_body_shape(file: UploadFile = File(...)):
    """Detect body shape from uploaded photo."""
    try:
        contents = await file.read()
        img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
        img_arr  = np.array(img_pil)

        # Body shape detection (pass numpy array directly)
        body_shape = detect_body_shape(img_arr)

        # Map detected values to frontend display values
        body_shape_map = {
            "inverted_triangle": "Inverted Triangle",
            "athletic": "Athletic",
            "hourglass": "Hourglass",
            "pear": "Pear",
            "apple": "Apple",
            "rectangle": "Rectangle",
            "unknown": "unknown"
        }

        body_shape = body_shape_map.get(body_shape.lower(), body_shape.title())

        return {
            "status": "success",
            "body_shape": body_shape
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 11. Style Match - Combined analysis and recommendations ────────────────
@app.post("/api/style-match")
async def style_match(
    file: Optional[UploadFile] = File(None),
    skin_tone: Optional[str] = Query(None),
    body_shape: Optional[str] = Query(None),
    dress_types: Optional[str] = Query(None),  # comma-separated list
    color: Optional[str] = Query(None),  # NEW: user-selected color
    top_k: int = Query(8, ge=1, le=50),
    current_user: dict = Depends(get_current_user_optional),
):
    try:
        detected_skin_tone = None
        detected_body_shape = None

        if file:
            contents = await file.read()
            img_pil  = Image.open(io.BytesIO(contents)).convert("RGB")
            img_arr  = np.array(img_pil)

            result = detect_skin_properties_from_array(img_arr)
            detected_skin_tone = result.get("tone", "")
            detected_body_shape = detect_body_shape(img_arr)

        normalized_skin_tone = normalize_skin_tone(skin_tone or detected_skin_tone)
        normalized_body_shape = normalize_body_shape_value(body_shape or detected_body_shape)

        final_skin_tone = normalized_skin_tone.title()
        final_body_shape = normalized_body_shape.title()

        if not final_skin_tone or not final_body_shape:
            raise HTTPException(
                400,
                "Please provide skin tone and body shape (auto-detected from image or manually selected)"
            )

        selected_types = normalize_style_types((dress_types or "").split(","))
        catalog = safe_get_all_products(limit=50000)

        ranked_products = []
        for product in catalog:
            score = score_style_match(
                product,
                normalized_skin_tone,
                normalized_body_shape,
                selected_types,
                color,  # NEW: pass user-selected color
            )
            ranked_products.append((product, score))

        ranked_products.sort(
            key=lambda item: (-item[1], -float(item[0].get("rating", 0) or 0), str(item[0].get("_id"))),
        )

        recommendations = ranked_products[:top_k]
        results = [product_to_dict(prod, score) for prod, score in recommendations]

        if current_user:
            try:
                insert_recommendation({
                    "user_id": current_user.get("user_id"),
                    "type": "style_match",
                    "skin_tone": final_skin_tone,
                    "body_shape": final_body_shape,
                    "dress_types": selected_types,
                    "product_ids": [r["id"] for r in results],
                    "created_at": datetime.utcnow(),
                })
            except:
                pass

        return {
            "status": "success",
            "analysis": {
                "skin_tone": final_skin_tone,
                "body_shape": final_body_shape,
                "dress_types": selected_types,
            },
            "results": results,
            "total": len(results),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 11b. Get color recommendations based on skin tone ──────────────────────
@app.post("/api/style-match/colors")
async def get_color_recommendations(
    skin_tone: Optional[str] = Query(None),
    undertone: Optional[str] = Query(None),
    body_shape: Optional[str] = Query(None),
):
    """
    Get color recommendations based on skin tone and undertone.

    Parameters:
    - skin_tone: Fair, Medium, or Deep
    - undertone: warm, cool, or neutral (optional, defaults to neutral)
    - body_shape: (optional, reserved for future enhancement)

    Returns:
    {
      "status": "success",
      "skin_tone": "fair",
      "undertone": "warm",
      "colors": ["gold", "orange", "peach", ...],
      "total": 8
    }
    """
    try:
        if not skin_tone:
            raise HTTPException(400, "Please provide skin_tone parameter")

        # Normalize inputs
        normalized_tone = normalize_skin_tone(skin_tone).lower()
        normalized_undertone = str(undertone or "neutral").strip().lower()

        # Validate undertone
        valid_undertones = ["warm", "cool", "neutral"]
        if normalized_undertone not in valid_undertones:
            normalized_undertone = "neutral"

        # Get recommended colors from vision module
        colors = recommend_colors(normalized_tone, normalized_undertone)

        return {
            "status": "success",
            "skin_tone": normalized_tone,
            "undertone": normalized_undertone,
            "colors": colors,
            "total": len(colors),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


# ── 12. Wardrobe Management - Per-User Storage ────────────────────────────────
@app.get("/api/wardrobe")
def get_user_wardrobe(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's saved wardrobe items from database."""
    try:
        from database.config import db
        from bson.objectid import ObjectId

        user_id = current_user.get("user_id")

        # Find user's wardrobe document
        try:
            wardrobe = db.wardrobe.find_one({"user_id": ObjectId(user_id)})
        except:
            try:
                wardrobe = db.wardrobe.find_one({"user_id": int(user_id)})
            except:
                wardrobe = db.wardrobe.find_one({"user_id": user_id})

        if not wardrobe:
            return {
                "status": "success",
                "results": [],
                "total": 0
            }

        product_ids = wardrobe.get("product_ids", [])

        # Fetch the actual products
        products = []
        for pid in product_ids:
            product = safe_get_product_by_id(pid)
            if product:
                products.append(product_to_dict(product))

        return {
            "status": "success",
            "results": products,
            "total": len(products)
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.post("/api/wardrobe")
def add_to_wardrobe(
    product_id: str = Query(..., description="Product ID to add"),
    current_user: dict = Depends(get_current_user),
):
    """Add a product to user's wardrobe."""
    try:
        from database.config import db
        from bson.objectid import ObjectId

        user_id = current_user.get("user_id")

        # Verify product exists
        product = safe_get_product_by_id(product_id)
        if not product:
            raise HTTPException(404, f"Product {product_id} not found")

        # Convert user_id to ObjectId format for consistency
        try:
            user_obj_id = ObjectId(user_id)
        except:
            try:
                user_obj_id = int(user_id)
            except:
                user_obj_id = user_id

        # Find or create wardrobe document
        wardrobe = db.wardrobe.find_one({"user_id": user_obj_id})

        if not wardrobe:
            # Create new wardrobe
            db.wardrobe.insert_one({
                "user_id": user_obj_id,
                "product_ids": [product_id],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })
        else:
            # Add to existing wardrobe (avoid duplicates)
            product_ids = wardrobe.get("product_ids", [])
            if product_id not in product_ids:
                product_ids.append(product_id)
                db.wardrobe.update_one(
                    {"user_id": user_obj_id},
                    {
                        "$set": {
                            "product_ids": product_ids,
                            "updated_at": datetime.utcnow(),
                        }
                    }
                )

        return {
            "status": "success",
            "message": f"Added {product.get('name', 'Item')} to wardrobe",
            "product_id": product_id
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@app.delete("/api/wardrobe/{product_id}")
def remove_from_wardrobe(
    product_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a product from user's wardrobe."""
    try:
        from database.config import db
        from bson.objectid import ObjectId

        user_id = current_user.get("user_id")

        # Convert user_id to ObjectId format
        try:
            user_obj_id = ObjectId(user_id)
        except:
            try:
                user_obj_id = int(user_id)
            except:
                user_obj_id = user_id

        # Update wardrobe
        result = db.wardrobe.update_one(
            {"user_id": user_obj_id},
            {
                "$pull": {"product_ids": product_id},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        if result.matched_count == 0:
            raise HTTPException(404, "Wardrobe not found")

        return {
            "status": "success",
            "message": "Item removed from wardrobe",
            "product_id": product_id
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))

