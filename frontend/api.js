const API_BASE = "http://localhost:8000";

function normalizeId(value) {
  return String(value ?? "");
}

function resolveImageUrl(imageUrl) {
  if (!imageUrl) return "https://placehold.co/400x500?text=No+Image";
  if (imageUrl.startsWith("http")) return imageUrl;
  if (imageUrl.startsWith("/images/")) return API_BASE + imageUrl;
  const filename = imageUrl.replace(/\\/g, "/").split("/").pop();
  return API_BASE + "/images/" + filename;
}

function encodeProductPayload(product) {
  try {
    return btoa(unescape(encodeURIComponent(JSON.stringify(product))));
  } catch (error) {
    console.warn("Unable to encode product payload:", error);
    return "";
  }
}

function decodeProductPayload(encodedProduct) {
  try {
    return JSON.parse(decodeURIComponent(escape(atob(encodedProduct))));
  } catch (error) {
    console.warn("Unable to decode product payload:", error);
    return null;
  }
}

const API = {
  async health() {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  },

  async recommendByImage(file, topK = 8) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/api/recommend/image?top_k=${topK}`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async recommendByText(productType, color = "", topK = 8) {
    const params = new URLSearchParams({ product_type: productType, top_k: topK });
    if (color) params.append("color", color);
    const response = await fetch(`${API_BASE}/api/recommend/text?${params}`);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async listProducts({ productType, color, brand, sort = "relevance", page = 1, perPage = 20 } = {}) {
    const params = new URLSearchParams({ sort, page, per_page: perPage });
    if (productType) params.append("product_type", productType);
    if (color) params.append("color", color);
    if (brand) params.append("brand", brand);
    const response = await fetch(`${API_BASE}/api/products?${params}`);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async getProduct(id) {
    const response = await fetch(`${API_BASE}/api/products/${encodeURIComponent(normalizeId(id))}`);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async getProductsByIds(ids = []) {
    const cleaned = ids.map(normalizeId).filter(Boolean);
    if (!cleaned.length) return { status: "success", results: [], total: 0 };
    const params = new URLSearchParams({ ids: cleaned.join(",") });
    const response = await fetch(`${API_BASE}/api/batch-products?${params}`);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async analyzeSkinTone(file) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/api/analyze/skin-tone`, { method: "POST", body: formData });
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async analyzeBodyShape(file) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/api/analyze/body-shape`, { method: "POST", body: formData });
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async getColorRecommendations({ skinTone = "", bodyShape = "" } = {}) {
    const params = new URLSearchParams();
    if (skinTone) params.append("skin_tone", skinTone);
    if (bodyShape) params.append("body_shape", bodyShape);
    const response = await fetch(`${API_BASE}/api/style-match/colors?${params}`, { method: "POST" });
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async styleMatch({ file = null, skinTone = "", bodyShape = "", dressTypes = [], color = "", topK = 8, token = "" } = {}) {
    const params = new URLSearchParams({ top_k: String(topK) });
    if (skinTone) params.append("skin_tone", skinTone);
    if (bodyShape) params.append("body_shape", bodyShape);
    if (dressTypes.length) params.append("dress_types", dressTypes.join(","));
    if (color) params.append("color", color);

    const options = {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    };

    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      options.body = formData;
    }

    const response = await fetch(`${API_BASE}/api/style-match?${params}`, options);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Server error ${response.status}`);
    }
    return response.json();
  },

  async getStats() {
    const response = await fetch(`${API_BASE}/api/stats`);
    return response.json();
  },

  async getWardrobe(token = "") {
    const options = {};
    if (token) {
      options.headers = { Authorization: `Bearer ${token}` };
    }
    const response = await fetch(`${API_BASE}/api/wardrobe`, options);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async addToWardrobe(productId, token = "") {
    const params = new URLSearchParams({ product_id: normalizeId(productId) });
    const options = {
      method: "POST",
    };
    if (token) {
      options.headers = { Authorization: `Bearer ${token}` };
    }
    const response = await fetch(`${API_BASE}/api/wardrobe?${params}`, options);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },

  async removeFromWardrobe(productId, token = "") {
    const options = {
      method: "DELETE",
    };
    if (token) {
      options.headers = { Authorization: `Bearer ${token}` };
    }
    const response = await fetch(`${API_BASE}/api/wardrobe/${encodeURIComponent(normalizeId(productId))}`, options);
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    return response.json();
  },
};

function renderProductCard(product, { onclick = null, showSimilarity = false } = {}) {
  const id = normalizeId(product.id);
  const imageUrl = resolveImageUrl(product.image_url || "");
  const name = product.name || "Fashion Item";
  const brand = product.brand || "";
  const price = product.price || "";
  const colour = product.colour || "";
  const rating = product.rating ? Number(product.rating).toFixed(1) : "4.0";
  let simPct = null;
  if (showSimilarity && product.similarity != null) {
    // Handle both decimal (0-1) and percentage (0-100) scales
    let pct = product.similarity > 1 ? product.similarity : product.similarity * 100;
    // Clamp to 0-100 range
    pct = Math.max(0, Math.min(100, pct));
    simPct = Math.round(pct);
  }
  const encodedProduct = encodeProductPayload(product);
  const clickAttr = onclick
    ? `onclick='${onclick}(${JSON.stringify(id)})'`
    : `onclick='openProductDetail(${JSON.stringify(id)}, ${JSON.stringify(encodedProduct)})'`;

  return `
    <div class="product-card bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition-all cursor-pointer border border-slate-100 group" ${clickAttr}>
      <div class="relative overflow-hidden aspect-[3/4] bg-slate-50">
        <img src="${imageUrl}" alt="${name}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" onerror="this.src='https://placehold.co/400x500?text=No+Image'"/>
        ${simPct !== null ? `<span class="absolute top-2 right-2 bg-primary text-white text-xs font-bold px-2 py-1 rounded-full">${simPct}% match</span>` : ""}
        <button onclick="event.stopPropagation(); toggleFav(this, ${JSON.stringify(id)})" class="absolute top-2 left-2 p-2 bg-white/80 rounded-full shadow hover:bg-white transition">
          <span class="material-symbols-outlined text-slate-400 fav-icon" style="font-size:18px">favorite_border</span>
        </button>
      </div>
      <div class="p-3">
        ${brand ? `<p class="text-xs text-primary font-semibold uppercase tracking-wide">${brand}</p>` : ""}
        <p class="text-sm font-semibold text-slate-800 line-clamp-2 mt-0.5">${name}</p>
        <div class="flex items-center justify-between mt-1">
          <span class="text-sm font-bold text-slate-900">${price ? "Rs. " + price : ""}</span>
          <span class="text-xs text-slate-500 flex items-center gap-0.5">
            <span class="material-symbols-outlined" style="font-size:14px;color:#f59e0b">star</span>
            ${rating}
          </span>
        </div>
        ${colour ? `<p class="text-xs text-slate-400 mt-0.5 capitalize">${colour}</p>` : ""}
      </div>
    </div>`;
}

function openProductDetail(id, encodedProduct = "") {
  try {
    if (encodedProduct) {
      const decodedProduct = decodeProductPayload(encodedProduct);
      if (decodedProduct) {
        sessionStorage.setItem("dressmate_selected_product", JSON.stringify(decodedProduct));
      }
    }
    window.location = `product_detail.html?id=${encodeURIComponent(normalizeId(id))}`;
  } catch (error) {
    console.warn("Unable to cache selected product:", error);
    window.location = `product_detail.html?id=${encodeURIComponent(normalizeId(id))}`;
  }
}

function toggleFav(btn, id) {
  const normalizedId = normalizeId(id);
  const saved = JSON.parse(localStorage.getItem("fashionai_favs") || "[]").map(normalizeId);
  const icon = btn.querySelector(".fav-icon");

  if (saved.includes(normalizedId)) {
    const next = saved.filter((item) => item !== normalizedId);
    localStorage.setItem("fashionai_favs", JSON.stringify(next));
    icon.textContent = "favorite_border";
    icon.classList.remove("text-red-500");
    icon.classList.add("text-slate-400");
    return;
  }

  saved.push(normalizedId);
  localStorage.setItem("fashionai_favs", JSON.stringify(saved));
  icon.textContent = "favorite";
  icon.classList.remove("text-slate-400");
  icon.classList.add("text-red-500");
}

function showError(container, msg) {
  container.innerHTML = `
    <div class="col-span-full flex flex-col items-center justify-center py-20 text-center">
      <span class="material-symbols-outlined text-5xl text-red-400 mb-3">error</span>
      <p class="text-slate-600 font-medium">${msg}</p>
      <p class="text-slate-400 text-sm mt-1">Make sure the backend is running on <code class="bg-slate-100 px-1 rounded">${API_BASE}</code></p>
    </div>`;
}

function showSkeleton(container, count = 8) {
  container.innerHTML = Array.from({ length: count }, () => `
    <div class="bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100 animate-pulse">
      <div class="aspect-[3/4] bg-slate-200"></div>
      <div class="p-3 space-y-2">
        <div class="h-3 bg-slate-200 rounded w-1/2"></div>
        <div class="h-4 bg-slate-200 rounded w-3/4"></div>
        <div class="h-3 bg-slate-200 rounded w-1/3"></div>
      </div>
    </div>`).join("");
}
