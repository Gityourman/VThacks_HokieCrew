# 🏆 VThacks Campus Life Intelligence Hub - Project Plan

**Team:** HokieCrew  
**Challenge:** Deloitte × Databricks - Campus Life Intelligence Hub  
**Prize Targets:** 
* 🎧 Best Use of ElevenLabs (voice AI)
* 🤖 Best Use of Gemini API (AI understanding)
* 🐅 Best Use of Tiger Data (real-time & time-series)

---

## 🎯 Multi-AI Architecture

```
┌─────────────────────────────────────────────────────────┐
│          Student Voice/Text Query                       │
└─────────────────────────┬───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│               Databricks App (Flask)                    │
│  🎤 ElevenLabs: Voice input/output                      │
│  🧠 Gemini Pro: Intent classification & enhancement     │
│  💬 Chat UI: Text + voice interface                     │
└─────────────────────────┬───────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│          4 Feature Modules (Python functions)           │
│  1. Easy Bus Helper      3. Health Helper               │
│  2. Food Info-Giver      4. Interest & Identity         │
└──────┬──────────────────────────────────────────┬───────┘
       ↓                                          ↓
┌──────────────────────┐              ┌──────────────────────┐
│   Tiger Data         │              │ Databricks           │
│   (Timescale)        │              │ Delta Lake           │
│                      │              │                      │
│  REAL-TIME:          │              │ HISTORICAL:          │
│  • Bus GPS (10s)     │              │ • Route schedules    │
│  • Gym occupancy     │              │ • All stops/routes   │
│  • ETA predictions   │              │ • Menus & dining     │
│  • Query metrics     │              │ • Health resources   │
│  • Last N min data   │              │ • Events & clubs     │
└──────────────────────┘              └──────────────────────┘
         ↓                                       ↓
         └───────────────┬───────────────────────┘
                         ↓
              Combined Response
              (real-time + context)
```

**Key Innovation:** Dual-database architecture
* **Tiger Data** = "What's happening RIGHT NOW?" (sub-second queries)
* **Delta Lake** = "What do we know overall?" (comprehensive data)

---

## ✅ Feature 1: Easy Bus Helper (COMPLETE)

**Owner:** Julian  
**Status:** ✅ Done  
**Notebook:** `Bus_Transit_Helper`

**What it does:**
* Natural language bus route recommendations
* Real-time bus tracking simulation with GPS + ETAs
* 14 routes, 20 destinations, live vehicle positions

**Delta Tables:**
* `workspace.vthacks.bt_routes_full` - 14 routes with stops, schedules, GPS
* `workspace.vthacks.bt_destinations_full` - 20 destinations mapped to routes
* `workspace.vthacks.bt_vehicle_positions` - Live vehicle positions

**Functions to export to App:**
* `recommend_bus_route(query: str) -> list[dict]`
* `recommend_with_live_tracking(query: str) -> dict`

---

## 🚧 Feature 2: Food Info-Giver (IN PROGRESS)

**Owner:** Julian's teammate (built with assistance)
**Status:** 🚧 Notebook created — running & testing
**Notebook:** `Food_Info_Giver` (ID: 4490156058017710)

**Data Sources:**
* VT Daily Menus: https://foodpro.students.vt.edu/menus/
* Dining Plans: https://dining.vt.edu/plans_overview/find_your_plan.html
* Local restaurants (scrape Google Maps or Yelp)

**What it needs:**
1. Scrape VT dining hall menus (breakfast, lunch, dinner)
2. Extract dietary info (vegetarian, vegan, gluten-free, allergens)
3. Add local restaurant data with budgets ($, $$, $$$)
4. Store in Delta tables:
   * `workspace.vthacks.food_menus` - Daily dining hall menus
   * `workspace.vthacks.dining_halls` - Locations, hours, meal plans
   * `workspace.vthacks.restaurants` - Local restaurants with filters

**Functions to build:**
* `recommend_food(query: str, dietary_restrictions: list, budget: str) -> list[dict]`

**Template notebook:** See below for starter template

---

## 🚧 Feature 3: Health Helper (IN PROGRESS) - PRIORITY 1

**Owner:** Teammate 2  
**Status:** 🚧 Not started  
**Notebook:** `Health_Helper` (to be created)

**Focus:** Physical + Mental Health (drop Professional/Career for MVP)

**Data Sources:**
* Gym occupancy: https://connect.recsports.vt.edu/facilityoccupancy (might be JSON API!)
* Gym offerings: https://recsports.vt.edu/facilities.html
* Mental health: https://well-being.vt.edu/mental-health.html
* Schiffert Health Center: https://healthcenter.vt.edu/

**Tables:**
* `workspace.vthacks.gym_info` - Facilities, hours, current occupancy
* `workspace.vthacks.health_resources` - Mental health + Schiffert services

**Functions to build:**
* `find_health_resources(query: str) -> list[dict]`
* `get_gym_occupancy() -> dict`

**Test Queries:**
* "When is McComas least crowded?"
* "I need to talk to a counselor"
* "What time does the climbing wall close?"

**Template notebook:** Clone Feature_Template

---

## ✅ Feature 5: Professical Helper (COMPLETE)

**Owner:** Julian's teammate (built with assistance)
**Status:** ✅ Notebook created
**Notebook:** `Professical_Helper` (ID: 4490156058017716)

**Data Sources:**
* VT Office of Undergraduate Research: https://www.research.undergraduate.vt.edu/index.html
* VT Career and Professional Development: https://career.vt.edu/
* Handshake (referenced): http://vt.joinhandshake.com

**What it does:**
* Research opportunity recommendations (fellowships, REUs, summer programs, grants)
* Career resource matching (resume help, interview prep, coaching, Handshake)
* Upcoming career fair and event discovery
* Career pathway exploration by industry (12+ career communities)

**Delta Tables (in workspace.default):**
* `workspace.default.research_opportunities` — Research programs and fellowships at VT
* `workspace.default.career_resources` — Career services, programs, and tools
* `workspace.default.career_events` — Upcoming career fairs and info sessions
* `workspace.default.career_pathways` — Industry-specific career community info

**Functions to export to App:**
* `recommend_professional(query: str) -> list[dict]`
* `recommend_research(query: str, field: str = None) -> list[dict]`
* `recommend_career(query: str, type: str = None) -> list[dict]`
* `recommend_career_pathway(query: str) -> list[dict]`

---

## 🚧 Feature 4: Interest & Identity (IN PROGRESS)

**Owner:** Julian  
**Status:** 🚧 Notebook created — running & testing  
**Notebook:** `Interest_Identity_Helper` (ID: 4490156058017713)

**Data Sources:**
* Events: https://gobblerconnect.vt.edu/events
* Clubs: https://gobblerconnect.vt.edu/organizations
* Cultural centers: https://www.ccc.vt.edu/

**Tables:**
* `workspace.vthacks.campus_events` - GobblerConnect events with dates, categories
* `workspace.vthacks.student_clubs` - Clubs with interests, DEI focus
* `workspace.vthacks.cultural_centers` - Cultural & community centers

**Functions to build:**
* `find_events(query: str, interests: list) -> list[dict]`
* `find_clubs(interests: list, dei_focus: bool) -> list[dict]`

**Template notebook:** See below for starter template

---

## 🎤 AI Integration: ElevenLabs + Gemini

### ElevenLabs Voice (Prize Target)
**Prize:** Best Use of ElevenLabs - https://mlh.link/elevenlabs

**What we'll build:**
1. **Voice Input** - Student talks to the app
   * Use ElevenLabs speech-to-text API
   * Convert voice → text query
   * Route to appropriate feature (bus, food, health, etc.)

2. **Voice Output** - App responds with voice
   * Take text response from feature functions
   * Use ElevenLabs TTS API to generate audio
   * Play audio response in browser

**Implementation (in Databricks App):**
```python
import elevenlabs

# Voice input
def transcribe_voice(audio_file):
    # ElevenLabs speech-to-text
    text = elevenlabs.transcribe(audio_file)
    return text

# Voice output
def speak_response(text_response):
    # ElevenLabs TTS
    audio = elevenlabs.generate(
        text=text_response,
        voice="Bella",  # Choose voice
        model="eleven_monolingual_v1"
    )
    return audio

# Combined workflow
audio_input = record_audio()  # Frontend captures mic
text_query = transcribe_voice(audio_input)
response = recommend_bus_route(text_query)  # Or any feature
audio_output = speak_response(response)
play_audio(audio_output)  # Frontend plays audio
```

**API Key:** Get from https://elevenlabs.io/sign-up (free tier available)

### Gemini AI Understanding (NEW!)
**Why add Gemini:** Makes query understanding WAY smarter

**What Gemini does:**
1. **Intent Classification** - Understands what the student really needs
   - "I need food but I'm allergic to peanuts" → Food feature + extract allergy
   - "What's the best time to gym before my 2pm class?" → Health + time reasoning

2. **Response Enhancement** - Makes responses conversational
   - Technical output → Natural, friendly student language
   - Adds context and helpful suggestions

3. **Complex Query Handling** - Handles multi-part questions
   - "I'm at Squires, need to grab lunch, then get to the gym" → Multi-step plan

**Implementation:**
```python
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Classify intent
response = model.generate_content(f"Classify this query: {user_query}")
# Route to appropriate feature
# Enhance response to be conversational
```

**API Key:** Get from https://aistudio.google.com/app/apikey (free tier: 60 requests/min)

**Benefits:**
* ✅ True AI understanding (not just keyword matching)
* ✅ Complements ElevenLabs (Gemini = brain, ElevenLabs = voice)
* ✅ Handles complex, multi-part queries
* ✅ More natural, conversational responses
* ✅ Free tier is generous for hackathon demo

---

## 📋 Work Distribution (3-Person Team)

| Teammate | Feature | Notebook | Est. Time | Priority |
|----------|---------|----------|-----------|----------|
| Julian | Bus Helper + App + Voice | `Bus_Transit_Helper` + App | ✅ Done + 3-4 hrs | P0 |
| Teammate 1 | Food Info-Giver | `Food_Info_Giver` | 2-3 hours | P1 |
| Teammate 2 | Health Helper | `Health_Helper` (Health focus) | 2-3 hours | P1 |
| Julian | Interest & Identity | `Interest_Identity_Helper` | ✅ Built + testing | P2 |

---

## 🚀 Deployment Timeline

### Phase 1: Core MVP (Hours 1-5) - GET THIS WORKING FIRST
* **Julian:** Build Databricks App scaffold + ElevenLabs voice integration
* **Teammate 1:** Food Info-Giver notebook (VT dining menus + dietary filters)
* **Teammate 2:** Health Helper notebook (gym occupancy + mental health resources)
* **Goal:** 3 features (Bus, Food, Health) working with voice input/output

### Phase 2: Polish & Test (Hours 5-7)
* Import all 3 feature functions into the App
* Test voice demo end-to-end (speak → answer → hear response)
* Fix bugs, deploy to Databricks Apps
* Set up Genie space as backup demo

### Phase 3: Stretch Goal - Add Feature 4 (Hours 7-10, if ahead of schedule)
* **One teammate:** Build Interest & Identity notebook
* **Julian:** Add 3 lines to App routing (takes 15 min)
* **Result:** 4 features if time permits, but 3 is a strong submission

---

## ⚠️ Critical Path Decision

**Do NOT start Feature 4 until:**
1. ✅ All 3 core features (Bus, Food, Health) are done
2. ✅ Voice integration works end-to-end
3. ✅ App is deployed and tested
4. ✅ You have 2+ hours remaining

**Why:** 3 polished features with working voice > 4 half-finished features

---

## 🛠️ Development Guidelines

### For Teammates Building Features 2-4:

1. **Clone the Bus Helper pattern:**
   * Step 1: Web scraping / data collection
   * Step 2: Create Delta tables in `workspace.vthacks`
   * Step 3: Build recommendation functions
   * Step 4: Test with example queries

2. **Delta table naming:**
   * Use `workspace.vthacks.<feature_name>`
   * Example: `workspace.vthacks.food_menus`

3. **Function signatures:**
   * Input: Natural language query string
   * Output: List of dicts with results + metadata
   * Keep functions simple - App will handle voice

4. **Don't worry about:**
   * Voice integration (handled in App)
   * UI (handled in App)
   * Just focus on data + logic

5. **Communication:**
   * Comment your code
   * Test your functions with print statements
   * When done, ping Julian to integrate into App

---

## 📊 Judging Criteria Mapping

| Criterion | Our Solution |
|-----------|--------------|  
| **Realism & Innovation** | 4 features covering transit, food, health, events + voice AI + Gemini intelligence |
| **Technical Execution** | Databricks Delta Lake + PySpark + Unity Catalog + Multi-AI integration |
| **Content** | 14 routes, real VT dining data, real health/events data |
| **Presentation** | Voice-enabled chat app (ElevenLabs + Gemini) |

---

## 🎯 Success Metrics

**MVP (Minimum Viable Product for Demo):**
* ✅ Feature 1 (Bus) working
* ✅ Feature 2 (Food) working
* ✅ Feature 3 (Health) working
* ✅ Databricks App deployed
* ✅ ElevenLabs voice input + output on all features
* ✅ End-to-end voice demo: speak → get answer → hear response

**Stretch Goals (if time permits):**
* Feature 4 (Interest & Identity) added
* Genie space set up as backup
* Polished UI with maps/charts

**Winning Formula:**
* 3 polished features with voice > 4 broken features
* Working demo > fancy UI that crashes
* Real scraped data > hardcoded samples

---

## 📞 Resources & Links

* **Bus data:** https://ridebt.org/routes-schedules
* **Food menus:** https://foodpro.students.vt.edu/menus/
* **Gym occupancy:** https://connect.recsports.vt.edu/facilityoccupancy
* **Events:** https://gobblerconnect.vt.edu/events
* **ElevenLabs API:** https://mlh.link/elevenlabs
* **Gemini API:** https://aistudio.google.com/app/apikey
* **Databricks docs:** https://docs.databricks.com/

---

## 📝 Notebook Templates

### How to use templates:
1. Create a new notebook with the feature name
2. Copy the template code from below
3. Replace placeholder URLs and data with real scraped data
4. Test your functions
5. Tell Julian when ready to integrate

### Template code examples are in separate files:
* `Food_Info_Giver_Template.py`
* `Student_Helper_Template.py`  
* `Interest_Identity_Template.py`

---

**Questions? Ask in the team chat or ping Julian!**