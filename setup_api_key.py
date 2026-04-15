#!/usr/bin/env python3
"""
DressMate API Key Setup Script
==============================
This script helps you configure your Gemini API key.
"""

import os
import sys

print("\n" + "="*60)
print("  DressMate AI Stylist - API Key Configuration")
print("="*60 + "\n")

# Check current status
env_path = ".env"
current_key = None

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                current_key = line.split("=", 1)[1].strip()
                break

if current_key and current_key != "YOUR_GEMINI_API_KEY":
    print(f"✓ API Key already configured: {current_key[:20]}...")
    update = input("\nDo you want to update it? (y/n): ").strip().lower()
    if update != 'y':
        print("Keeping current key.")
        sys.exit(0)
else:
    print("⚠ API Key not configured yet.\n")
    print("Get your free Gemini API key:")
    print("  1. Go to: https://ai.google.dev/")
    print("  2. Click 'Get API Key' button")
    print("  3. Sign in with Google")
    print("  4. Copy the generated key\n")

api_key = input("Enter your Gemini API key: ").strip()

if not api_key:
    print("\n✗ Error: No API key provided")
    sys.exit(1)

if not api_key.startswith("AIzaSy"):
    print("\n⚠ Warning: API key should start with 'AIzaSy'")
    confirm = input("Continue anyway? (y/n): ").strip().lower()
    if confirm != 'y':
        sys.exit(1)

# Read existing .env content
other_content = []
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("GEMINI_API_KEY="):
                other_content.append(line)

# Write updated .env
with open(env_path, "w", encoding="utf-8") as f:
    f.write(f"GEMINI_API_KEY={api_key}\n\n")
    f.writelines(other_content)

print("\n✓ API key updated successfully!")
print(f"  Key: {api_key[:20]}...")
print("\nNext steps:")
print("  1. Stop your backend server (Ctrl+C if running)")
print("  2. Restart it: python -m uvicorn app:app --reload --port 8000")
print("  3. Refresh http://localhost:8000/gemini_stylist.html")
print("  4. Try sending a message to the AI Stylist\n")
