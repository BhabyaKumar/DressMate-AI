# DressMate Frontend Integration Guide

## Overview
This guide explains how to use the frontend authentication system, API wrappers, and page templates to build authenticated features.

---

## 1. Authentication System (auth.js)

The `auth.js` module provides a comprehensive authentication system with token management, API wrappers, and page protection utilities.

### Core Features
- **Token Management**: Save, retrieve, and clear JWT tokens
- **User Authentication**: Register and login with email/password
- **Protected API Calls**: Automatically inject Authorization headers
- **Page Protection**: Require authentication for specific pages
- **User Profile Display**: Show logged-in user information

### Quick Start

#### Import auth.js in your HTML
```html
<script src="auth.js"></script>
```

#### Check if User is Authenticated
```javascript
if (AUTH.isAuthenticated()) {
  console.log("User is logged in");
  const profile = AUTH.getProfile();
} else {
  console.log("User is not logged in");
}
```

#### Redirect to Login if Not Authenticated
```javascript
window.addEventListener('load', function() {
  if (!AUTH.isAuthenticated()) {
    window.location.href = '/login.html';
  }
});
```

---

## 2. API Wrapper Functions (AUTH object)

The `AUTH` object provides these functions:

### Authentication Endpoints

#### `AUTH.register(email, password, name)`
Register a new user and save their token.

```javascript
try {
  const result = await AUTH.register('user@example.com', 'password123', 'John Doe');
  console.log('Registration successful, token saved');
} catch (error) {
  console.error('Registration failed:', error.message);
}
```

#### `AUTH.login(email, password)`
Login with existing credentials and save token.

```javascript
try {
  const result = await AUTH.login('user@example.com', 'password123');
  console.log('Login successful');
  const profile = AUTH.getProfile();
  console.log('Logged in as:', profile.name);
} catch (error) {
  console.error('Login failed:', error.message);
}
```

#### `AUTH.getProfile()`
Get the current logged-in user's profile from localStorage.

```javascript
const profile = AUTH.getProfile();
console.log(profile.name, profile.email);
```

#### `AUTH.logout()`
Clear token and redirect to login page.

```javascript
AUTH.logout(); // Clears token and refreshes page to /login.html
```

### Protected Endpoint Calls

#### `AUTH.call(endpoint, options)`
Make an authenticated API call with automatic Authorization header.

```javascript
const response = await AUTH.call('/api/recommend/text', {
  method: 'GET',
  params: {
    product_type: 'dress',
    color: 'blue',
    top_k: 10
  }
});
console.log('Recommendations:', response.results);
```

#### `AUTH.uploadImage(file, count)`
Upload an image and get recommendations with automatic history saving.

```javascript
const file = document.getElementById('fileInput').files[0];
try {
  const result = await AUTH.uploadImage(file, 12);
  console.log('Upload successful, got', result.results.length, 'recommendations');
  // Result is automatically saved to user's history
} catch (error) {
  console.error('Upload failed:', error.message);
}
```

#### `AUTH.chat(message)`
Send a message to the AI Stylist.

```javascript
try {
  const response = await AUTH.chat('What should I wear to a summer beach party?');
  console.log('AI Response:', response.response);
} catch (error) {
  console.error('Chat failed:', error.message);
}
```

#### `AUTH.getHistory()`
Get user's recommendation history.

```javascript
try {
  const history = await AUTH.getHistory();
  console.log('Got', history.length, 'past recommendations');
  history.forEach(item => {
    console.log(item.type, '-', item.results.length, 'items');
  });
} catch (error) {
  console.error('History failed:', error.message);
}
```

### Utility Functions

#### `AUTH.isAuthenticated()`
Check if a user has a valid token.

```javascript
if (AUTH.isAuthenticated()) {
  console.log('User has valid token');
}
```

#### `AUTH.getToken()`
Get the stored JWT token (for debugging/manual API calls).

```javascript
const token = AUTH.getToken();
console.log('Current token:', token);
```

---

## 3. Page Templates

### login.html
**Purpose**: User registration and login page  
**Features**:
- Toggle between login and register forms
- Email and password validation
- Error and success alerts
- Demo account display
- Redirects to index.html on successful authentication

**Usage**: No modifications needed, ready to use

### index.html (Updated)
**Changes**:
- Added auth check - redirects to login if not authenticated
- User profile dropdown showing name, email, and logout button
- Initialize auth on page load

**Add to your pages**:
```html
<!-- At the top of the script section -->
<script src="auth.js"></script>
<script>
  window.addEventListener('load', function() {
    if (!AUTH.isAuthenticated()) {
      window.location.href = '/login.html';
    }
    const profile = AUTH.getProfile();
    // Display user info...
  });
</script>
```

### image_upload_page.html (Updated)
**Changes**:
- Requires authentication (redirects to login if not authenticated)
- Image uploads saved to user's recommendation history
- "Past Uploads" button shows recommendation history
- User profile dropdown in header

**Use AUTH.uploadImage instead of API.recommendByImage**:
```javascript
// Before (without auth):
const data = await API.recommendByImage(selectedFile, 12);

// After (with auth and history):
const data = await AUTH.uploadImage(selectedFile, 12);
```

### browse_products.html (Updated)
**Changes**:
- Optional authentication (can browse without logging in)
- Shows user profile if logged in, "Sign In" link otherwise
- Browsing available to both authenticated and non-authenticated users

No special code needed, already handles both cases.

### dashboard.html (New)
**Purpose**: User profile and recommendation history dashboard  
**Features**:
- Requires authentication
- Displays user profile information
- Shows statistics (total recommendations, saved items, uploads)
- Timeline view of recommendation history
- Click history items to view detailed results

**Usage**: Add link to navigation:
```html
<a href="dashboard.html">Dashboard</a>
```

---

## 4. Backend API Endpoints

### Authentication (Public)
- **POST /api/auth/register** - Create new user
- **POST /api/auth/login** - Authenticate user
- **GET /api/auth/profile** - Get current user profile (requires token)

### Recommendations (Require Token)
- **GET /api/recommend/text** - Text-based recommendations
- **POST /api/recommend/image** - Image-based recommendations with saved history
- **GET /api/history** - Get user's recommendation history
- **POST /api/chat** - AI Stylist chat

### Products (Public)
- **GET /api/products** - Browse all products
- **GET /api/products/{id}** - Get product details
- **GET /api/stats** - Get system statistics
- **GET /health** - API health check

---

## 5. Common Implementation Patterns

### Pattern 1: Require Authentication for a Page
```javascript
window.addEventListener('load', function() {
  if (!AUTH.isAuthenticated()) {
    window.location.href = '/login.html';
  }
  // Your page logic here...
});
```

### Pattern 2: Optional Authentication (Show Different UI)
```javascript
window.addEventListener('load', function() {
  if (AUTH.isAuthenticated()) {
    // Show authenticated UI
    const profile = AUTH.getProfile();
    document.getElementById('userWelcome').textContent = `Welcome, ${profile.name}!`;
  } else {
    // Show non-authenticated UI
    document.getElementById('userWelcome').textContent = 'Please sign in';
  }
});
```

### Pattern 3: Protected API Call with Error Handling
```javascript
async function loadUserRecommendations() {
  try {
    const history = await AUTH.getHistory();
    displayHistory(history);
  } catch (error) {
    if (error.message.includes('401')) {
      // Token expired, redirect to login
      window.location.href = '/login.html';
    } else {
      showError('Failed to load recommendations: ' + error.message);
    }
  }
}
```

### Pattern 4: Upload with History and Redirect
```javascript
async function handleImageUpload(file) {
  try {
    const results = await AUTH.uploadImage(file, 12);
    // Automatically saved to history
    sessionStorage.setItem('recommendation_results', JSON.stringify(results));
    window.location.href = 'system_feedback.html';
  } catch (error) {
    alert('Upload failed: ' + error.message);
  }
}
```

### Pattern 5: User Profile Dropdown
```html
<!-- HTML -->
<div id="userButton" onclick="toggleUserDropdown()">
  <img id="userAvatar" src="...">
</div>
<div id="userDropdown" class="hidden">
  <div id="userDropdownContent"></div>
  <button onclick="AUTH.logout()">Logout</button>
</div>

<!-- JavaScript -->
<script src="auth.js"></script>
<script>
  window.addEventListener('load', function() {
    if (AUTH.isAuthenticated()) {
      const profile = AUTH.getProfile();
      document.getElementById('userDropdownContent').innerHTML = `
        <p>${profile.name}</p>
        <p>${profile.email}</p>
      `;
    }
  });

  function toggleUserDropdown() {
    document.getElementById('userDropdown').classList.toggle('hidden');
  }
</script>
```

---

## 6. Environment Configuration

### Backend (.env file)
```
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=dressmate
JWT_SECRET=your-secret-key-here
PASSWORD_SALT=your-salt-here
GEMINI_API_KEY=your-api-key-here (optional)
```

### Frontend (No .env needed)
All frontend configuration is handled by auth.js and api.js based on the URLs they call.

---

## 7. Testing the Integration

### Test User Credentials
The login page displays demo credentials for testing:
- **Email**: demo@example.com (if available from previous registrations)
- **Password**: DemoPassword123!

### Test Registration Flow
1. Open `login.html`
2. Click "Create Account"
3. Fill in email, password, and name
4. Click "Register"
5. Should be redirected to `index.html`

### Test Image Upload
1. Navigate to `image_upload_page.html` (should require login)
2. Drag/drop or select an image
3. Click "Find Similar Items"
4. Should show recommendations from `system_feedback.html`
5. History should be saved

### Test Dashboard
1. Navigate to `dashboard.html`
2. Should show user profile and recommendation history
3. Click history items to view details

---

## 8. Troubleshooting

### "Not Found" errors
- Check API endpoint names match exactly (case-sensitive)
- Ensure backend is running on `localhost:8000`
- Check browser console for CORS errors

### "Unauthorized" (401) errors
- Token may have expired, user needs to log in again
- Check token is present in localStorage: `localStorage.getItem('auth_token')`
- Verify Authorization header is being sent: `Authorization: Bearer {token}`

### CORS errors
- Backend may not be running
- Check FastAPI server is started: `python -m uvicorn app:app --reload`
- Verify port is 8000

### Chat endpoint not working
- Requires GEMINI_API_KEY in `.env` file
- Check backend logs for API key errors
- This is optional for MVP, other features work without it

---

## 9. Next Steps

1. **Integrate remaining pages**:
   - my_wardrobe.html - Add auth
   - gemini_stylist.html - Use AUTH.chat()
   - product_detail.html - Add to cart with auth
   - recommendation_results.html - Use AUTH.uploadImage()

2. **Add features**:
   - Product favorites (save to user profile)
   - Skin tone detection and storage
   - Size/fit preferences
   - Share recommendations with friends
   - View product reviews

3. **Deployment**:
   - Set environment variables for production
   - Configure MongoDB Atlas (instead of local)
   - Deploy backend to cloud (Heroku, AWS, Google Cloud)
   - Deploy frontend to static hosting (Netlify, Vercel, GitHub Pages)

---

## 10. API Response Examples

### Register/Login Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Profile Response
```json
{
  "_id": "user_id_here",
  "name": "John Doe",
  "email": "john@example.com",
  "skin_tone": null,
  "preferences": {}
}
```

### Recommendations Response
```json
{
  "status": "success",
  "results": [
    {
      "_id": "product_id",
      "name": "Product Name",
      "price": 4999.0,
      "colour": "blue",
      "product_type": "dress",
      "similarity_score": 0.87
    }
  ],
  "total": 8
}
```

### History Response
```json
{
  "status": "success",
  "total": 3,
  "history": [
    {
      "id": "rec_id",
      "type": "image",
      "created_at": "2024-01-15 10:30:45",
      "details": {
        "skin_tone": null,
        "color": null,
        "product_ids": ["pid1", "pid2", ...]
      }
    }
  ]
}
```

---

## Support & Resources

- **Backend API Docs**: http://localhost:8000/docs (when running)
- **Frontend Files**: `/frontend/` directory
- **Backend Tests**: `/backend/test_e2e.py`
- **Configuration**: `backend/.env`

