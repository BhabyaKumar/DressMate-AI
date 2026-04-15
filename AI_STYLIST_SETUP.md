# 🎨 DressMate AI Stylist Setup Guide
**Date**: April 14, 2026

---

## 📋 Overview

The AI Stylist feature uses **Google Gemini API** to power conversational fashion recommendations. The system is fully integrated and ready to use once you add your API key.

---

## 🔑 Step 1: Get Your Gemini API Key

### 1.1 Create a Free Account at Google AI Studio
- Visit: **https://ai.google.dev/**
- Click **"Get API Key"** button (top right)
- Sign in with your Google account

### 1.2 Create or Select a Project
- Choose "Create new API key" 
- Select a project (create a new one if needed)
- Copy the generated API key

### 1.3 Example API Key Format
```
AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 📁 Step 2: Add API Key to .env File

### Location:
```
c:\Users\bhaby\Desktop\DressMate\.env
```

### Content:
```env
GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**⚠️ IMPORTANT**: Replace `AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` with your actual API key from Step 1.2

---

## 💾 Step 3: Install Required Dependencies

Open terminal in the `backend` directory and run:

```bash
pip install google-generativeai python-dotenv
```

**Full requirements (if starting fresh):**
```bash
pip install fastapi uvicorn python-multipart scikit-learn numpy pandas \
            pillow opencv-python-headless tensorflow pymongo \
            python-dotenv google-generativeai
```

---

## ▶️ Step 4: Start the Backend Server

```bash
cd c:\Users\bhaby\Desktop\DressMate\backend
python -m uvicorn app:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
[ok] MongoDB ready, app started successfully!
```

---

## 🌐 Step 5: Test the AI Stylist

### Open the application:
```
http://localhost:8000/gemini_stylist.html
```

### Test the chat:
1. Type a fashion question in the input box
2. Examples:
   - "What colors suit my skin tone?"
   - "How do I style a dress for a formal event?"
   - "What accessories match a blue shirt?"

3. Click **Send** or press Enter
4. The AI should respond with personalized fashion advice

---

## 🏗️ Architecture Overview

### Frontend (`frontend/gemini_stylist.html`)
```
User Input
    ↓
HTML Chat Interface
    ↓
JavaScript (sendMessage function)
    ↓
AUTH.chat(message) → Backend API
    ↓
Display Response
```

### Backend (`backend/app.py`)
```
POST /api/chat?message=...
    ↓
Validate authentication
    ↓
Get user profile from MongoDB
    ↓
Build system prompt with user context
    ↓
Call Gemini API
    ↓
Return response
```

---

## 🔄 API Endpoint Details

### Endpoint: `POST /api/chat`

**Request:**
```javascript
// Called from frontend via AUTH.chat()
POST http://localhost:8000/api/chat?message=What%20colors%20suit%20me?

Headers: {
  Authorization: Bearer <JWT_TOKEN>
}
```

**Response:**
```json
{
  "status": "success",
  "message": "What colors suit me?",
  "response": "Based on fashion styling principles, here are colors that would complement you..."
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "Gemini API key not configured. Add GEMINI_API_KEY to your .env file"
}
```

---

## 🎯 Features Implemented

### ✅ Completed
- [x] Frontend chat interface with real-time messaging
- [x] Backend API integration with Gemini
- [x] User authentication (JWT tokens)
- [x] Personalized responses based on user profile
- [x] Loading states and error handling
- [x] Image upload support (users can upload outfit photos)
- [x] User profile context (skin tone, preferred colors, styles)

### 📋 Frontend Features

1. **Chat Messages** - Display user and AI messages in conversation format
2. **Quick Replies** - Pre-defined buttons for common questions
3. **Image Upload** - Users can attach outfit photos
4. **Loading Indicator** - Shows "Thinking..." while waiting for response
5. **Error Messages** - Clear feedback if something goes wrong
6. **User Authentication** - Requires login to access

### 🧠 Backend Features

1. **API Key Management** - Secure environment variable handling
2. **User Context** - Personalizes responses based on profile:
   - User name
   - Skin tone
   - Preferred colors
   - Preferred style types
3. **Error Handling** - Comprehensive error messages
4. **Rate Limiting Ready** - Structure supports future rate limiting
5. **Logging** - Detailed error logs for debugging

---

## 🔧 Configuration Details

### System Prompt (Located in backend/app.py)

The system prompt sets the personality and behavior:

```python
system_prompt = f"""You are DressMate, a professional AI fashion stylist assistant. 
You help users find perfect outfits, provide fashion advice, and make personalized 
recommendations based on their style profile.

[User Profile Context]

Instructions:
- Be friendly, professional, and personalized
- Provide specific, actionable fashion recommendations
- Consider the user's skin tone and body shape in suggestions
- Suggest colors, styles, and fabrics that complement their profile
- Ask clarifying questions if needed
- Keep responses concise (2-3 sentences max)
- Use fashion terminology confidently
- Be encouraging and positive about fashion choices
"""
```

### Model Configuration

- **Model**: `gemini-1.5-flash` (faster, lower cost)
- **Temperature**: 0.7 (balanced creativity and consistency)
- **Top P**: 0.9 (diverse but focused responses)

---

## 🐛 Troubleshooting

### Issue: "Gemini API key not configured"
**Solution:**
1. Check `.env` file exists in `backend/` directory
2. Verify `GEMINI_API_KEY=...` is set correctly
3. Restart the backend server
4. Check the .env file hasn't been added to `.gitignore` (it should be!)

### Issue: "Gemini SDK not installed"
**Solution:**
```bash
pip install google-generativeai
```

### Issue: Chat returns empty response
**Solution:**
1. Check Gemini API quota (free tier has limits)
2. Verify API key is valid on https://ai.google.dev/
3. Check backend logs for detailed error message

### Issue: "Unauthorized" error when sending message
**Solution:**
1. User is not logged in
2. JWT token has expired
3. Token is invalid
4. Log out and log back in

### Issue: No response from server
**Solution:**
1. Check backend is running: `http://localhost:8000/health`
2. Check MongoDB is connected (see startup logs)
3. Verify port 8000 is available
4. Check firewall settings

---

## 📊 Usage Limits

### Free Tier (Google Gemini API)
- **Rate**: 60 requests per minute
- **Daily Quota**: Generous (varies by quota type)
- **Cost**: Free for development

### Upgrade for production:
Visit: https://ai.google.dev/pricing

---

## 🎓 How It Works (Technical Details)

### 1. User sends message
```javascript
// frontend/gemini_stylist.html → sendMessage()
const response = await AUTH.chat("What colors suit me?");
```

### 2. Frontend calls backend
```javascript
// frontend/auth.js → AUTH.chat()
await AUTH.call(`/api/chat?message=${encodeURIComponent(message)}`, 
  { method: "POST" }
);
```

### 3. Backend validates & retrieves context
```python
# backend/app.py → /api/chat endpoint
user = db.users.find_one({"_id": ObjectId(user_id)})
# Builds personalized context from user profile
```

### 4. Backend calls Gemini API
```python
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')
response = model.generate_content([system_prompt, "\n\nUser message: " + message])
```

### 5. Response sent to frontend
```json
{
  "status": "success",
  "response": "..."
}
```

### 6. Frontend displays message
```javascript
addAIMessage(response.response);
```

---

## 📚 File Structure

```
DressMate/
├── .env                          ← PUT YOUR API KEY HERE
├── backend/
│   ├── app.py                    ← Chat endpoint with Gemini integration
│   ├── auth/
│   │   └── auth.py              ← JWT token management
│   └── database/
│       └── config.py            ← MongoDB user profiles
└── frontend/
    ├── gemini_stylist.html      ← Chat UI
    └── auth.js                  ← AUTH.chat() function
```

---

## 🚀 Next Steps (Optional Enhancements)

- [ ] Add chat history persistence
- [ ] Implement conversation memory (context from previous messages)
- [ ] Add image analysis ("analyze this outfit")
- [ ] Product recommendations from Gemini suggestions
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Generate outfit combinations
- [ ] Virtual try-on with Gemini vision API

---

## ✅ Verification Checklist

- [ ] .env file created with `GEMINI_API_KEY` set
- [ ] `google-generativeai` package installed
- [ ] Backend server running on port 8000
- [ ] MongoDB connection successful
- [ ] Can navigate to `http://localhost:8000/gemini_stylist.html`
- [ ] Can log in with credentials
- [ ] Can send a message and receive response
- [ ] Loading state shows while processing
- [ ] Error messages display if API fails

---

## 📞 Support & Resources

- **Google Gemini API Docs**: https://ai.google.dev/docs
- **Google Generative AI Python SDK**: https://github.com/google/generative-ai-python
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **DressMate GitHub**: (your repo URL)

---

## 📝 Notes

1. Your API key is stored locally in `.env` - **DO NOT commit to git**
2. The `.env` file is in `.gitignore` for security
3. Free tier API keys work great for development
4. Each chat message costs tokens from your quota
5. Gemini API is rate-limited (check current limits on Google AI Studio)

---

**Setup Complete! 🎉 Your AI Stylist is ready to help users find perfect outfits.**

For issues or questions, check the troubleshooting section above or review the backend logs.

**Last Updated**: April 14, 2026  
**Version**: 1.0
