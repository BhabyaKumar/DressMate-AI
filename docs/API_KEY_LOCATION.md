# 🔑 API KEY QUICK REFERENCE

## Where to Put Your Gemini API Key

### The File:
```
c:\Users\bhaby\Desktop\DressMate\.env
```

### What to Add:
```env
GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Replace `AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` with your actual API key.

---

## How to Get the API Key

1. Go to: **https://ai.google.dev/**
2. Click **"Get API Key"** (top right)
3. Sign in with Google
4. Copy the key shown
5. Paste it in the `.env` file above

---

## After Adding API Key

1. **Install the package:**
   ```bash
   pip install google-generativeai
   ```

2. **Restart backend server:**
   ```bash
   # Stop current server (Ctrl+C)
   # Then run:
   python -m uvicorn app:app --reload --port 8000
   ```

3. **Test it:**
   - Go to: `http://localhost:8000/gemini_stylist.html`
   - Log in
   - Try sending a message to the AI
   - You should get a response!

---

## Files Changed

- ✅ `.env` - Created with API key placeholder
- ✅ `frontend/gemini_stylist.html` - Updated to use real API
- ✅ `backend/app.py` - Enhanced chat endpoint with Gemini integration
- ✅ `AI_STYLIST_SETUP.md` - Full setup guide

---

## That's It! 

Your AI Stylist is now fully integrated. Just add your API key and you're done! 🚀
