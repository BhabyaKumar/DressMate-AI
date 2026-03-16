/**
 * FashionAI API Client
 * =====================
 * Shared across all frontend pages. Talks to the FastAPI backend at
 * http://localhost:8000  (change API_BASE if you deploy elsewhere).
 */

const API_BASE = "http://localhost:8000";

const API = {
  /* ── health ── */
  async health() {
    const r = await fetch(`${API_BASE}/health`);
    return r.json();
  },

  /* ── image upload → recommendations ── */
  async recommendByImage(file, topK = 8) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("top_k", topK);
    const r = await fetch(`${API_BASE}/api/recommend/image?top_k=${topK}`, {
      method: "POST",
      body: fd,
    });
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    return r.json();
  },

  /* ── text / filter → recommendations ── */
  async recommendByText(productType, color = "", topK = 8) {
    const params = new URLSearchParams({ product_type: productType, top_k: topK });
    if (color) params.append("color", color);
    const r = await fetch(`${API_BASE}/api/recommend/text?${params}`);
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    return r.json();
  },

  /* ── browse / catalogue ── */
  async listProducts({ productType, color, brand, sort = "relevance", page = 1, perPage = 20 } = {}) {
    const params = new URLSearchParams({ sort, page, per_page: perPage });
    if (productType) params.append("product_type", productType);
    if (color)       params.append("color", color);
    if (brand)       params.append("brand", brand);
    const r = await fetch(`${API_BASE}/api/products?${params}`);
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    return r.json();
  },

  /* ── single product + similar ── */
  async getProduct(id) {
    const r = await fetch(`${API_BASE}/api/products/${id}`);
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    return r.json();
  },

  /* ── skin tone from image ── */
  async analyzeSkinTone(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API_BASE}/api/analyze/skin-tone`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    return r.json();
  },

  /* ── dataset stats ── */
  async getStats() {
    const r = await fetch(`${API_BASE}/api/stats`);
    return r.json();
  },
};

/* ── shared product-card renderer ── */
function renderProductCard(p, { onclick = null, showSimilarity = false } = {}) {
  // Resolve image URL — handle http, /images/, and raw filenames
  let imgSrc = p.image_url || "";
  if (!imgSrc.startsWith("http")) {
    if (imgSrc.startsWith("/images/")) {
      imgSrc = API_BASE + imgSrc;
    } else if (imgSrc) {
      // raw filename or relative path like "Images\foo.jpg"
      const filename = imgSrc.replace(/\\/g, "/").split("/").pop();
      imgSrc = API_BASE + "/images/" + filename;
    } else {
      imgSrc = "https://placehold.co/400x500?text=No+Image";
    }
  }
  const name    = p.name    || "Fashion Item";
  const brand   = p.brand   || "";
  const price   = p.price   || "";
  const colour  = p.colour  || "";
  const rating  = p.rating  ? Number(p.rating).toFixed(1) : "4.0";
  const simPct  = showSimilarity ? Math.round((p.similarity || 0) * 100) : null;

  const clickAttr = onclick
    ? `onclick="${onclick}(${p.id})"`
    : `onclick="window.location='product_detail.html?id=${p.id}'"`;

  return `
    <div class="product-card bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg
                transition-all cursor-pointer border border-slate-100 group" ${clickAttr}>
      <div class="relative overflow-hidden aspect-[3/4] bg-slate-50">
        <img src="${imgSrc}" alt="${name}"
             class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
             onerror="this.src='https://placehold.co/400x500?text=No+Image'"/>
        ${simPct !== null
          ? `<span class="absolute top-2 right-2 bg-primary text-white text-xs font-bold
                         px-2 py-1 rounded-full">${simPct}% match</span>`
          : ""}
        <button onclick="event.stopPropagation(); toggleFav(this, ${p.id})"
                class="absolute top-2 left-2 p-2 bg-white/80 rounded-full shadow hover:bg-white transition">
          <span class="material-symbols-outlined text-slate-400 fav-icon" style="font-size:18px">favorite_border</span>
        </button>
      </div>
      <div class="p-3">
        ${brand ? `<p class="text-xs text-primary font-semibold uppercase tracking-wide">${brand}</p>` : ""}
        <p class="text-sm font-semibold text-slate-800 line-clamp-2 mt-0.5">${name}</p>
        <div class="flex items-center justify-between mt-1">
          <span class="text-sm font-bold text-slate-900">${price ? "₹" + price : ""}</span>
          <span class="text-xs text-slate-500 flex items-center gap-0.5">
            <span class="material-symbols-outlined" style="font-size:14px;color:#f59e0b">star</span>
            ${rating}
          </span>
        </div>
        ${colour ? `<p class="text-xs text-slate-400 mt-0.5 capitalize">${colour}</p>` : ""}
      </div>
    </div>`;
}

/* ── favourite toggle (localStorage) ── */
function toggleFav(btn, id) {
  const saved = JSON.parse(localStorage.getItem("fashionai_favs") || "[]");
  const icon  = btn.querySelector(".fav-icon");
  if (saved.includes(id)) {
    const next = saved.filter(x => x !== id);
    localStorage.setItem("fashionai_favs", JSON.stringify(next));
    icon.textContent = "favorite_border";
    icon.classList.remove("text-red-500");
    icon.classList.add("text-slate-400");
  } else {
    saved.push(id);
    localStorage.setItem("fashionai_favs", JSON.stringify(saved));
    icon.textContent = "favorite";
    icon.classList.remove("text-slate-400");
    icon.classList.add("text-red-500");
  }
}

/* ── error banner ── */
function showError(container, msg) {
  container.innerHTML = `
    <div class="col-span-full flex flex-col items-center justify-center py-20 text-center">
      <span class="material-symbols-outlined text-5xl text-red-400 mb-3">error</span>
      <p class="text-slate-600 font-medium">${msg}</p>
      <p class="text-slate-400 text-sm mt-1">Make sure the backend is running on
         <code class="bg-slate-100 px-1 rounded">${API_BASE}</code></p>
    </div>`;
}

/* ── loading skeleton ── */
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
