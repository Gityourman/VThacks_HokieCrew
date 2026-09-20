# 🚀 VT Campus Life Assistant - Deployment Guide

## 📋 Prerequisites

1. ✅ Feature notebooks completed (Bus, Food, Health)
2. ✅ Delta tables populated with data
3. ✅ ElevenLabs API key from https://elevenlabs.io/sign-up

---

## 🔑 Step 1: Set Up API Keys (ElevenLabs + Gemini)

### Get Your API Keys:

**ElevenLabs (for voice):**
1. Go to https://elevenlabs.io/sign-up
2. Sign up (free tier: 10,000 chars/month)
3. Copy your API key from the dashboard

**Gemini (for AI understanding):**
1. Go to https://aistudio.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key" (free tier: 60 requests/min)
4. Copy your API key

### Option A: Using Databricks Secrets (Recommended)
```python
# Run in a Databricks notebook cell
dbutils.secrets.put(scope="vthacks", key="elevenlabs_api_key", string_value="YOUR_ELEVENLABS_KEY")
dbutils.secrets.put(scope="vthacks", key="gemini_api_key", string_value="YOUR_GEMINI_KEY")
```

### Option B: Hardcode in app.yaml (Quick Test)
Edit `app.yaml`:
```yaml
env:
  - name: ELEVENLABS_API_KEY
    value: "your-elevenlabs-key-here"  # Replace this
  - name: GEMINI_API_KEY
    value: "your-gemini-key-here"  # Replace this
```

---

## 📦 Step 2: Import Feature Functions

Before deploying, you need to import your feature functions into `app.py`.

### For Feature 1 (Bus Helper):

1. Open [Bus_Transit_Helper](#notebook-4490156058017681)
2. Find the `recommend_with_live_tracking()` function (Cell 17)
3. Copy it and the helper functions
4. In `app.py`, replace the `recommend_bus_route()` stub:

```python
# BEFORE (stub)
def recommend_bus_route(query: str) -> str:
    return f"Bus recommendation for: {query}\n\n[Feature 1: Bus Helper is ready - import the function from your notebook!]"

# AFTER (actual function)
def recommend_bus_route(query: str) -> str:
    # Load data from Delta tables
    routes_pdf = spark.table("workspace.vthacks.bt_routes_full").toPandas()
    vehicle_positions = spark.table("workspace.vthacks.bt_vehicle_positions").toPandas().to_dict('records')
    
    # Call your actual recommendation function
    result = recommend_with_live_tracking(query, routes_pdf, vehicle_positions)
    return result
```

### For Feature 2 (Food Info-Giver):

Once Teammate 1 finishes their notebook:
1. Get the `recommend_food()` function from their notebook
2. Replace the stub in `app.py`
3. Make sure it loads from `workspace.vthacks.food_menus` table

### For Feature 3 (Health Helper):

Once Teammate 2 finishes their notebook:
1. Get the `find_health_resources()` function from their notebook
2. Replace the stub in `app.py`
3. Make sure it loads from `workspace.vthacks.gym_info` and `workspace.vthacks.health_resources` tables

---

## 🚀 Step 3: Deploy the App

### Method 1: Databricks CLI (Recommended)

```bash
# Install Databricks CLI if not already installed
pip install databricks-cli

# Configure CLI (if not done)
databricks configure --token

# Deploy the app
databricks apps create vt-campus-life-assistant \
  --source-code-path /Workspace/Users/julianmiller@vt.edu/VThacks_HokieCrew/VThacks_HokieCrew
```

### Method 2: Databricks UI

1. Go to **Compute** → **Apps**
2. Click **Create App**
3. Name: `vt-campus-life-assistant`
4. Source code path: `/Workspace/Users/julianmiller@vt.edu/VThacks_HokieCrew/VThacks_HokieCrew`
5. Click **Create**

### Method 3: Quick Test (No Deployment)

Run locally in a notebook cell:
```python
%sh
cd /Workspace/Users/julianmiller@vt.edu/VThacks_HokieCrew/VThacks_HokieCrew
pip install flask elevenlabs
python app.py
```

Then open the URL shown in the output.

---

## 🧪 Step 4: Test the App

### Test Text Input
1. Open the deployed app URL
2. Type a query: "How do I get to Walmart?"
3. Click **Send**
4. Verify you get a bus route response

### Test Voice Input
1. Click the 🎤 microphone button
2. Allow microphone access
3. Speak: "Where can I eat vegetarian food?"
4. Click the mic button again to stop
5. Verify:
   - Your speech is transcribed correctly
   - You get a food recommendation
   - The response is read aloud

### Test All Features
- **Bus:** "How do I get to Kroger?"
- **Food:** "I have a peanut allergy, where can I eat?"
- **Health:** "When is the gym least crowded?"

---

## 🐛 Troubleshooting

### App Won't Start
- Check logs: `databricks apps logs vt-campus-life-assistant`
- Verify all dependencies are in `app.yaml`
- Ensure ElevenLabs API key is set

### Voice Not Working
- Check browser console for errors
- Verify ELEVENLABS_API_KEY is set correctly
- Test with text input first to isolate the issue

### Feature Responses Are Stubs
- You haven't imported the actual functions from notebooks yet
- Follow Step 2 above to replace stub functions

### Delta Tables Not Found
- Verify tables exist: `spark.sql("SHOW TABLES IN workspace.vthacks").show()`
- Check table names match exactly

---

## 📊 Demo Script for Judges

### Opening (30 seconds)
"Hi! We're Team HokieCrew, and we built the VT Campus Life Intelligence Hub - a voice-enabled AI assistant that unifies campus services for Virginia Tech students."

### Feature Demo (2 minutes)

**1. Voice Input Demo:**
- *Click mic, speak:* "How do I get to Walmart?"
- *Show:* Real-time transcription, bus route with live tracking, ETA
- *Highlight:* "Powered by ElevenLabs voice AI"

**2. Food Feature:**
- *Type:* "I'm vegetarian and on a budget"
- *Show:* Dining hall menus with dietary filters, budget-friendly options

**3. Health Feature:**
- *Voice:* "When should I go to the gym?"
- *Show:* Live gym occupancy, mental health resources

### Technical Highlights (1 minute)
- "Built on **Databricks Data Intelligence Platform**"
- "6 Delta Lake tables with real VT data"
- "Real-time bus tracking simulation"
- "**Multi-AI integration:** ElevenLabs for voice + Google Gemini for intelligence"
- "**ElevenLabs** handles speech-to-text and text-to-speech"
- "**Gemini AI** understands complex queries and provides conversational responses"
- "3 campus services unified in one AI-powered voice interface"

### Closing (30 seconds)
"Students can now navigate campus life hands-free while walking or biking. All data is queryable in Delta Lake, and the app scales on Databricks. Thank you!"

---

## 📞 Questions?

Refer back to [PROJECT_PLAN.md](#file-4490156058017697) for architecture details.

Good luck at VThacks! 🎉