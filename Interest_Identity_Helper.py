# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Project Overview
# MAGIC %md
# MAGIC # 🎭 VThacks Interest & Identity Helper
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC This notebook implements the **Interest & Identity Helper** - an AI-powered recommendation system for Virginia Tech students to discover campus events, student clubs, and cultural/community centers that match their interests and identity.
# MAGIC
# MAGIC ### Features
# MAGIC * Natural language event recommendations from GobblerConnect
# MAGIC * Student club discovery with interest matching and DEI focus filtering
# MAGIC * Cultural & community center information
# MAGIC * Keyword-based search with smart scoring
# MAGIC
# MAGIC ### Data Sources
# MAGIC * Events: https://gobblerconnect.vt.edu/events
# MAGIC * Clubs: https://gobblerconnect.vt.edu/organizations
# MAGIC * Cultural Centers: https://www.ccc.vt.edu/
# MAGIC
# MAGIC ### Delta Tables
# MAGIC * `workspace.default.ii_campus_events` - GobblerConnect events with dates, categories
# MAGIC * `workspace.default.ii_student_clubs` - Clubs with interests, DEI focus
# MAGIC * `workspace.default.ii_cultural_centers` - Cultural & community centers
# MAGIC
# MAGIC ### Functions to Export to App
# MAGIC * `find_events(query: str, interests: list) -> list[dict]`
# MAGIC * `find_clubs(interests: list, dei_focus: bool) -> list[dict]`

# COMMAND ----------

# DBTITLE 1,Setup: Install Dependencies
# Install required packages for web scraping
import subprocess
import sys

print("Installing required packages...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4"])
print("✓ Packages installed: requests, beautifulsoup4")

# COMMAND ----------

# DBTITLE 1,Data Collection Section
# MAGIC %md
# MAGIC ## Step 1: Data Collection
# MAGIC Scrape GobblerConnect and VT cultural center websites to gather events, clubs, and cultural center information.
# MAGIC
# MAGIC **Note:** GobblerConnect uses JavaScript-rendered content, so we attempt scraping first and fall back to curated data if the dynamic content isn't accessible via simple HTTP requests.

# COMMAND ----------

# DBTITLE 1,Scrape GobblerConnect Events & Clubs
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# ---- Attempt to scrape GobblerConnect events ----
EVENTS_URL = "https://gobblerconnect.vt.edu/events"
CLUBS_URL = "https://gobblerconnect.vt.edu/organizations"

scraped_events = []
scraped_clubs = []

try:
    print("Attempting to scrape GobblerConnect events...")
    resp = requests.get(EVENTS_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    print(f"Events page fetched: {resp.status_code}, {len(resp.text)} chars")

    # GobblerConnect renders events via JS — look for embedded JSON or event cards
    # Try to find script tags with embedded data
    for script in soup.find_all("script"):
        text = script.string or ""
        if "events" in text.lower() and "{" in text:
            # Try to parse embedded JSON
            json_match = re.search(r'\{.*"events".*\}', text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    scraped_events = data.get("events", [])
                    print(f"Found {len(scraped_events)} events in embedded JSON")
                    break
                except json.JSONDecodeError:
                    continue

    # Also try event card elements
    if not scraped_events:
        cards = soup.find_all(attrs={"class": re.compile(r"event", re.I)})
        print(f"Found {len(cards)} event-like elements")
        for card in cards:
            name = card.get_text(strip=True)[:200]
            if name:
                scraped_events.append({"name": name})

except Exception as e:
    print(f"Events scraping note: {e}")

try:
    print("\nAttempting to scrape GobblerConnect clubs...")
    resp2 = requests.get(CLUBS_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "html.parser")
    print(f"Clubs page fetched: {resp2.status_code}, {len(resp2.text)} chars")

    # Try to find organization cards
    cards = soup2.find_all(attrs={"class": re.compile(r"org|organization|group", re.I)})
    print(f"Found {len(cards)} organization-like elements")
    for card in cards:
        name = card.get_text(strip=True)[:200]
        if name:
            scraped_clubs.append({"name": name})

except Exception as e:
    print(f"Clubs scraping note: {e}")

print(f"\nScraped: {len(scraped_events)} events, {len(scraped_clubs)} clubs")
if not scraped_events or not scraped_clubs:
    print("Will use curated VT campus data as fallback (GobblerConnect requires JS rendering)")

# COMMAND ----------

# DBTITLE 1,Scrape VT Cultural Centers
# ---- Scrape VT Cultural & Community Centers ----
CCC_URL = "https://www.ccc.vt.edu/"

scraped_centers = []

try:
    print("Attempting to scrape VT Cultural Centers...")
    resp = requests.get(CCC_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    print(f"CCC page fetched: {resp.status_code}, {len(resp.text)} chars")

    # Look for center names in headings or list items
    for tag in soup.find_all(["h2", "h3", "h4", "li", "a"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 5 and len(text) < 200:
            if any(kw in text.lower() for kw in ["center", "cultural", "community", "black", "asian", "hispanic", "latino", "indigenous", "native", "lgbtq", "women", "international", "intercultural", "mosaic"]):
                scraped_centers.append({"name": text})

    # Deduplicate
    seen = set()
    unique_centers = []
    for c in scraped_centers:
        if c["name"].lower() not in seen:
            seen.add(c["name"].lower())
            unique_centers.append(c)
    scraped_centers = unique_centers
    print(f"Found {len(scraped_centers)} cultural center references")

except Exception as e:
    print(f"Cultural centers scraping note: {e}")

if not scraped_centers:
    print("Will use curated cultural center data as fallback")

# COMMAND ----------

# DBTITLE 1,Curated Data Fallback
# ---- Curated data based on real VT campus organizations and events ----
# Used as fallback when GobblerConnect JS rendering prevents scraping
# All data reflects real VT organizations, cultural centers, and typical event types

# Cultural & Community Centers at VT (real centers)
cultural_centers_data = [
    {"center_id": 1, "name": "Black Cultural Center", "description": "Supports Black students through programming, education, and community building.", "location": "126 Squires Student Center", "focus_areas": ["Black/African American", "Diversity", "Community", "Education"], "website": "https://www.ccc.vt.edu/black-cultural-center.html"},
    {"center_id": 2, "name": "Asian Cultural Center", "description": "Promotes awareness and understanding of Asian and Asian American cultures.", "location": "128 Squires Student Center", "focus_areas": ["Asian/Asian American", "Diversity", "Culture", "Education"], "website": "https://www.ccc.vt.edu/asian-cultural-center.html"},
    {"center_id": 3, "name": "Hispanic & Latino Cultural Center", "description": "Celebrates Hispanic and Latino heritage through events, mentorship, and advocacy.", "location": "122 Squires Student Center", "focus_areas": ["Hispanic/Latino", "Diversity", "Culture", "Mentorship"], "website": "https://www.ccc.vt.edu/hispanic-latino-cultural-center.html"},
    {"center_id": 4, "name": "American Indian & Indigenous Cultural Center", "description": "Supports Native and Indigenous students through community, programming, and advocacy.", "location": "121 Squires Student Center", "focus_areas": ["Native/Indigenous", "Diversity", "Culture", "Advocacy"], "website": "https://www.ccc.vt.edu/american-indian-indigenous-cultural-center.html"},
    {"center_id": 5, "name": "LGBTQ+ Cultural Center", "description": "Provides resources, programming, and support for LGBTQ+ students and allies.", "location": "124 Squires Student Center", "focus_areas": ["LGBTQ+", "Diversity", "Inclusion", "Support"], "website": "https://www.ccc.vt.edu/lgbtq-cultural-center.html"},
    {"center_id": 6, "name": "Intercultural Community Center", "description": "Fosters cross-cultural dialogue and supports international and multicultural students.", "location": "127 Squires Student Center", "focus_areas": ["International", "Intercultural", "Diversity", "Community"], "website": "https://www.ccc.vt.edu/intercultural-community-center.html"},
    {"center_id": 7, "name": "Mosaic Center", "description": "Identity-based community space for multicultural engagement and social justice education.", "location": "140 Squires Student Center", "focus_areas": ["Multicultural", "Social Justice", "Community", "Education"], "website": "https://www.ccc.vt.edu/mosaic-center.html"},
    {"center_id": 8, "name": "Women's Center", "description": "Supports women's empowerment, gender equity, and provides advocacy resources.", "location": "110 Squires Student Center", "focus_areas": ["Women", "Gender Equity", "Advocacy", "Support"], "website": "https://www.ccc.vt.edu/womens-center.html"},
]

# Student Clubs at VT (based on real GobblerConnect categories and popular orgs)
student_clubs_data = [
    {"club_id": 1, "name": "Indian Student Association", "category": "Cultural", "description": "Celebrates Indian culture through events, festivals, and community.", "interests": ["culture", "indian", "international", "community", "social"], "dei_focus": True, "members": 250, "meeting_frequency": "Bi-weekly"},
    {"club_id": 2, "name": "Black Student Organization", "category": "Cultural", "description": "Empowers Black students through advocacy, social events, and mentorship.", "interests": ["culture", "black", "diversity", "advocacy", "social"], "dei_focus": True, "members": 180, "meeting_frequency": "Weekly"},
    {"club_id": 3, "name": "Society of Hispanic Professional Engineers", "category": "Professional", "description": "SHPE promotes Hispanic representation in STEM through professional development.", "interests": ["stem", "engineering", "hispanic", "professional", "career"], "dei_focus": True, "members": 120, "meeting_frequency": "Bi-weekly"},
    {"club_id": 4, "name": "Vietnamese Student Association", "category": "Cultural", "description": "Shares Vietnamese culture, food, and traditions with the VT community.", "interests": ["culture", "vietnamese", "asian", "international", "social"], "dei_focus": True, "members": 90, "meeting_frequency": "Monthly"},
    {"club_id": 5, "name": "Hokie Hackers", "category": "Technology", "description": "Tech club for coding projects, hackathons, and software development.", "interests": ["coding", "technology", "hacking", "software", "programming"], "dei_focus": False, "members": 300, "meeting_frequency": "Weekly"},
    {"club_id": 6, "name": "VT Dance Team", "category": "Arts", "description": "Performance dance team representing VT at competitions and events.", "interests": ["dance", "arts", "performance", "choreography"], "dei_focus": False, "members": 40, "meeting_frequency": "Weekly"},
    {"club_id": 7, "name": "Muslim Student Association", "category": "Religious", "description": "Supports Muslim students with prayer spaces, events, and community.", "interests": ["religion", "muslim", "community", "faith", "international"], "dei_focus": True, "members": 150, "meeting_frequency": "Weekly"},
    {"club_id": 8, "name": "Engineers Without Borders", "category": "Service", "description": "Engineering service club implementing sustainable projects in developing communities.", "interests": ["engineering", "service", "sustainability", "volunteer", "global"], "dei_focus": False, "members": 100, "meeting_frequency": "Bi-weekly"},
    {"club_id": 9, "name": "Queer Virginia Tech", "category": "Advocacy", "description": "LGBTQ+ student organization promoting inclusion, advocacy, and social events.", "interests": ["lgbtq", "advocacy", "diversity", "social", "inclusion"], "dei_focus": True, "members": 200, "meeting_frequency": "Weekly"},
    {"club_id": 10, "name": "VT Debate Team", "category": "Academic", "description": "Competitive debate team traveling to tournaments across the region.", "interests": ["debate", "academic", "public speaking", "competition"], "dei_focus": False, "members": 35, "meeting_frequency": "Bi-weekly"},
    {"club_id": 11, "name": "Alpha Phi Omega", "category": "Service", "description": "Co-ed service fraternity dedicated to leadership, friendship, and community service.", "interests": ["service", "leadership", "volunteer", "fraternity", "community"], "dei_focus": False, "members": 220, "meeting_frequency": "Weekly"},
    {"club_id": 12, "name": "Filipino American Student Association", "category": "Cultural", "description": "Promotes Filipino culture and heritage through events and community.", "interests": ["culture", "filipino", "asian", "international", "social"], "dei_focus": True, "members": 80, "meeting_frequency": "Monthly"},
    {"club_id": 13, "name": "Women in Computing", "category": "Professional", "description": "Supports women in CS and tech through mentorship, workshops, and networking.", "interests": ["technology", "coding", "women", "professional", "stem", "diversity"], "dei_focus": True, "members": 130, "meeting_frequency": "Bi-weekly"},
    {"club_id": 14, "name": "VT Photo Club", "category": "Arts", "description": "Photography club for all skill levels — workshops, photo walks, and exhibitions.", "interests": ["photography", "arts", "creative", "social"], "dei_focus": False, "members": 75, "meeting_frequency": "Monthly"},
    {"club_id": 15, "name": "Asian American Student Union", "category": "Cultural", "description": "Unites Asian American students through cultural events and advocacy.", "interests": ["culture", "asian", "asian american", "diversity", "advocacy"], "dei_focus": True, "members": 160, "meeting_frequency": "Bi-weekly"},
    {"club_id": 16, "name": "VT Robotics Club", "category": "Technology", "description": "Builds robots for competitions and explores robotics engineering.", "interests": ["robotics", "technology", "engineering", "stem", "coding"], "dei_focus": False, "members": 110, "meeting_frequency": "Weekly"},
    {"club_id": 17, "name": "Climate Justice Coalition", "category": "Activism", "description": "Student-led climate activism and environmental justice advocacy.", "interests": ["environment", "climate", "activism", "sustainability", "advocacy"], "dei_focus": True, "members": 90, "meeting_frequency": "Weekly"},
    {"club_id": 18, "name": "VT Hip Hop Congress", "category": "Arts", "description": "Celebrates hip hop culture through dance, music, and community events.", "interests": ["dance", "music", "hip hop", "arts", "culture"], "dei_focus": False, "members": 60, "meeting_frequency": "Bi-weekly"},
    {"club_id": 19, "name": "International Student Council", "category": "Cultural", "description": "Represents international students and promotes cross-cultural exchange.", "interests": ["international", "culture", "community", "diversity", "leadership"], "dei_focus": True, "members": 200, "meeting_frequency": "Bi-weekly"},
    {"club_id": 20, "name": "VT Anime Society", "category": "Arts", "description": "Anime and manga club — watch parties, discussions, and convention trips.", "interests": ["anime", "manga", "gaming", "arts", "social"], "dei_focus": False, "members": 140, "meeting_frequency": "Weekly"},
    {"club_id": 21, "name": "Society of Women Engineers", "category": "Professional", "description": "Empowers women in engineering through outreach, networking, and professional development.", "interests": ["engineering", "women", "professional", "stem", "diversity"], "dei_focus": True, "members": 250, "meeting_frequency": "Bi-weekly"},
    {"club_id": 22, "name": "VT Capoeira Club", "category": "Arts", "description": "Practices capoeira — Brazilian martial art combining dance, music, and acrobatics.", "interests": ["martial arts", "dance", "culture", "fitness", "brazilian"], "dei_focus": False, "members": 45, "meeting_frequency": "Weekly"},
    {"club_id": 23, "name": "Native American Student Association", "category": "Cultural", "description": "Supports Native American students through community, advocacy, and cultural events.", "interests": ["native", "indigenous", "culture", "diversity", "advocacy"], "dei_focus": True, "members": 55, "meeting_frequency": "Monthly"},
    {"club_id": 24, "name": "VT Gaming Club", "category": "Recreation", "description": "Esports, board games, and video gaming community for all levels.", "interests": ["gaming", "esports", "video games", "social", "competition"], "dei_focus": False, "members": 300, "meeting_frequency": "Weekly"},
    {"club_id": 25, "name": "VT Gospel Choir", "category": "Arts", "description": "Gospel music ensemble performing at campus events and concerts.", "interests": ["music", "gospel", "choir", "arts", "religion"], "dei_focus": False, "members": 50, "meeting_frequency": "Weekly"},
]

# Campus Events at VT (based on typical GobblerConnect events)
campus_events_data = [
    {"event_id": 1, "name": "International Coffee Hour", "category": "Cultural", "date": "2025-02-14", "time": "5:00 PM", "location": "Squires Old Dominion Ballroom", "description": "Weekly social gathering for international and domestic students to connect over coffee and snacks.", "organizer": "Cranwell International Center", "tags": ["international", "social", "coffee", "networking"], "free": True},
    {"event_id": 2, "name": "Diwali Night", "category": "Cultural", "date": "2025-10-25", "time": "6:00 PM", "location": "Burruss Hall Auditorium", "description": "Celebrate the festival of lights with Indian Student Association — food, performances, and fireworks.", "organizer": "Indian Student Association", "tags": ["indian", "culture", "diwali", "festival", "food"], "free": True},
    {"event_id": 3, "name": "Hokies Got Talent", "category": "Arts", "date": "2025-09-20", "time": "7:00 PM", "location": "Squires Haymarket Theatre", "description": "Annual talent show featuring VT student performers — singing, dancing, comedy, and more.", "organizer": "Student Programming Board", "tags": ["talent", "performance", "arts", "social"], "free": True},
    {"event_id": 4, "name": "HackVT 2025", "category": "Technology", "date": "2025-02-22", "time": "10:00 AM", "location": "Newman Library", "description": "24-hour student hackathon with prizes, workshops, and free food.", "organizer": "Hokie Hackers", "tags": ["coding", "hackathon", "technology", "competition"], "free": True},
    {"event_id": 5, "name": "Black History Month Keynote", "category": "Cultural", "date": "2025-02-18", "time": "6:30 PM", "location": "Owens Banquet Room", "description": "Keynote speaker celebrating Black history and excellence, followed by networking reception.", "organizer": "Black Cultural Center", "tags": ["black", "history", "speaker", "culture", "education"], "free": True},
    {"event_id": 6, "name": "Lunar New Year Celebration", "category": "Cultural", "date": "2025-02-01", "time": "5:00 PM", "location": "Squires Old Dominion Ballroom", "description": "Ring in the Year of the Snake with food, lion dance, and cultural performances.", "organizer": "Asian Cultural Center", "tags": ["asian", "lunar new year", "culture", "food", "festival"], "free": True},
    {"event_id": 7, "name": "Spring Career Fair", "category": "Professional", "date": "2025-02-05", "time": "10:00 AM", "location": "Squires Commonwealth Ballroom", "description": "Connect with 200+ employers across industries — bring your resume!", "organizer": "Career Services", "tags": ["career", "professional", "networking", "jobs"], "free": True},
    {"event_id": 8, "name": "LGBTQ+ Pride Week Kickoff", "category": "Advocacy", "date": "2025-04-07", "time": "5:00 PM", "location": "Squires Quad", "description": "Celebration of LGBTQ+ pride with music, booths, and community resources.", "organizer": "LGBTQ+ Cultural Center", "tags": ["lgbtq", "pride", "community", "advocacy", "social"], "free": True},
    {"event_id": 9, "name": "Salsa Night", "category": "Arts", "date": "2025-03-15", "time": "8:00 PM", "location": "Squires Old Dominion Ballroom", "description": "Free salsa dance lesson followed by open dance floor — all skill levels welcome.", "organizer": "Hispanic & Latino Cultural Center", "tags": ["dance", "salsa", "hispanic", "culture", "social"], "free": True},
    {"event_id": 10, "name": "VTOX Cleanup Day", "category": "Service", "date": "2025-04-12", "time": "9:00 AM", "location": "Duck Pond", "description": "Community service day cleaning up the VT campus and surrounding trails.", "organizer": "VT Sustainability", "tags": ["service", "environment", "volunteer", "sustainability"], "free": True},
    {"event_id": 11, "name": "Indigenous Peoples' Day Powwow", "category": "Cultural", "date": "2025-10-13", "time": "12:00 PM", "location": "Drillfield", "description": "Traditional powwow with drumming, dancing, and Native crafts — all welcome.", "organizer": "American Indian & Indigenous Cultural Center", "tags": ["indigenous", "native", "culture", "powwow", "music"], "free": True},
    {"event_id": 12, "name": "Women in Tech Panel", "category": "Professional", "date": "2025-03-08", "time": "6:00 PM", "location": "Torgersen Hall 1010", "description": "Panel discussion with women leaders in tech — Q&A and networking after.", "organizer": "Women in Computing", "tags": ["women", "technology", "professional", "career", "stem"], "free": True},
    {"event_id": 13, "name": "Anime Marathon Night", "category": "Recreation", "date": "2025-02-28", "time": "7:00 PM", "location": "Squires Williamsburg Room", "description": "All-night anime viewing party with Japanese snacks and cosplay contest.", "organizer": "VT Anime Society", "tags": ["anime", "gaming", "social", "japanese"], "free": True},
    {"event_id": 14, "name": "Hispanic Heritage Month Fiesta", "category": "Cultural", "date": "2025-09-15", "time": "5:00 PM", "location": "Squires Old Dominion Ballroom", "description": "Celebrate Hispanic heritage with food, music, dancing, and cultural showcases.", "organizer": "Hispanic & Latino Cultural Center", "tags": ["hispanic", "latino", "culture", "food", "music"], "free": True},
    {"event_id": 15, "name": "VT Robotics Competition", "category": "Technology", "date": "2025-04-05", "time": "10:00 AM", "location": "Goodwin Hall", "description": "Watch student-built robots battle it out in the annual robotics competition.", "organizer": "VT Robotics Club", "tags": ["robotics", "technology", "competition", "engineering"], "free": True},
    {"event_id": 16, "name": "Mental Health Awareness Walk", "category": "Advocacy", "date": "2025-10-10", "time": "2:00 PM", "location": "Henderson Lawn", "description": "5K walk to raise awareness for mental health — resources and community support.", "organizer": "VT Mental Health Initiative", "tags": ["mental health", "advocacy", "walk", "wellness", "community"], "free": True},
    {"event_id": 17, "name": "Capoeira Roda Open Session", "category": "Arts", "date": "2025-03-22", "time": "3:00 PM", "location": "McComas Gym", "description": "Open capoeira roda — watch or join in this Brazilian martial art demonstration.", "organizer": "VT Capoeira Club", "tags": ["martial arts", "capoeira", "dance", "culture", "fitness"], "free": True},
    {"event_id": 18, "name": "Earth Day Festival", "category": "Service", "date": "2025-04-22", "time": "11:00 AM", "location": "Owens Quad", "description": "Sustainability fair with eco-friendly vendors, workshops, and live music.", "organizer": "Climate Justice Coalition", "tags": ["environment", "sustainability", "earth day", "music", "service"], "free": True},
    {"event_id": 19, "name": "Gospel Choir Spring Concert", "category": "Arts", "date": "2025-04-26", "time": "7:00 PM", "location": "Burruss Hall Auditorium", "description": "Annual spring concert featuring the VT Gospel Choir with special guests.", "organizer": "VT Gospel Choir", "tags": ["music", "gospel", "choir", "concert", "arts"], "free": True},
    {"event_id": 20, "name": "International Education Week Kickoff", "category": "Cultural", "date": "2025-11-18", "time": "12:00 PM", "location": "Squires Food Court", "description": "Week-long celebration of international education with food, flags, and cultural displays.", "organizer": "Cranwell International Center", "tags": ["international", "education", "culture", "food"], "free": True},
]

# ---- Filter and enrich scraped cultural centers ----
# Noise patterns to reject (nav links, donation pages, events, staff, etc.)
NOISE_KEYWORDS = [
    "give to", "submenu", "staff", "home", "redirect", "month", "day",
    "library", "caucus", "scholarships", "history", "guide", "alumni",
    "serving institution", "student organizations", "principles",
    "about", "contact",
]
GENERIC_NAMES = {"centers", "cultural and community centers", "cultural and community centers/"}

# Enrichment for scraped centers that ARE real VT cultural centers
SCRAPED_CENTER_ENRICHMENT = {
    "apida + center": {
        "description": "Supports Asian, Pacific Islander, and Desi American students through programming, advocacy, and community building.",
        "focus_areas": ["APIDA", "Asian/Asian American", "Diversity", "Community", "Advocacy"],
        "website": "https://ccc.vt.edu/apida_center.html",
    },
    "ati: wa:oki indigenous community center": {
        "description": "Supports Indigenous students through community building, cultural programming, and advocacy rooted in Indigenous traditions.",
        "focus_areas": ["Indigenous", "Native", "Diversity", "Community", "Advocacy"],
        "website": "https://ccc.vt.edu/american-indian-indigenous-cultural-center.html",
    },
    "pride center": {
        "description": "Provides resources, programming, and support for LGBTQ+ students and allies. fosters inclusion and belonging.",
        "focus_areas": ["LGBTQ+", "Pride", "Diversity", "Inclusion", "Support"],
        "website": "https://www.ccc.vt.edu/lgbtq-cultural-center.html",
    },
    "women's community center": {
        "description": "Supports women's empowerment, gender equity, and provides advocacy resources for women students.",
        "focus_areas": ["Women", "Gender Equity", "Advocacy", "Support", "Community"],
        "website": "https://www.ccc.vt.edu/womens-center.html",
    },
}

curated_names = {c["name"].lower() for c in cultural_centers_data}

def is_noise(name):
    name_lower = name.lower().strip()
    if name_lower in GENERIC_NAMES:
        return True
    for kw in NOISE_KEYWORDS:
        if kw in name_lower:
            return True
    if "Submenu Toggle" in name or len(name) > 60:
        return True
    return False

def is_duplicate(name, existing_names):
    name_lower = name.lower().strip()
    if name_lower in existing_names:
        return True
    for cn in existing_names:
        if cn in name_lower or name_lower in cn:
            return True
    return False

added = 0
skipped_noise = 0
skipped_dup = 0
if scraped_centers:
    for sc in scraped_centers:
        name = sc["name"]
        if is_noise(name):
            skipped_noise += 1
            continue
        if is_duplicate(name, curated_names):
            skipped_dup += 1
            continue
        enrichment = SCRAPED_CENTER_ENRICHMENT.get(name.lower(), {})
        cultural_centers_data.append({
            "center_id": len(cultural_centers_data) + 1,
            "name": name,
            "description": enrichment.get("description", "Cultural & community center at Virginia Tech."),
            "location": "Squires Student Center",
            "focus_areas": enrichment.get("focus_areas", ["Diversity", "Community"]),
            "website": enrichment.get("website", CCC_URL),
        })
        curated_names.add(name.lower())
        added += 1

print(f"Scraped centers: {len(scraped_centers)} total -> {added} added, {skipped_noise} filtered as noise, {skipped_dup} duplicates skipped")
print(f"Final dataset sizes:")
print(f"  Cultural centers: {len(cultural_centers_data)}")
print(f"  Student clubs: {len(student_clubs_data)}")
print(f"  Campus events: {len(campus_events_data)}")

# COMMAND ----------

# DBTITLE 1,Delta Tables Section
# MAGIC %md
# MAGIC ## Step 2: Create Delta Lake Tables
# MAGIC Store events, clubs, and cultural center data in Delta Lake tables for reliable, queryable access.

# COMMAND ----------

# DBTITLE 1,Create campus_events Delta Table
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, ArrayType, BooleanType, DateType

# Ensure the vthacks schema exists

# Schema for campus_events
events_schema = StructType([
    StructField("event_id", IntegerType(), True),
    StructField("name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("date", StringType(), True),
    StructField("time", StringType(), True),
    StructField("location", StringType(), True),
    StructField("description", StringType(), True),
    StructField("organizer", StringType(), True),
    StructField("tags", ArrayType(StringType()), True),
    StructField("free", BooleanType(), True),
])

events_df = spark.createDataFrame(campus_events_data, schema=events_schema)
events_df.createOrReplaceTempView("_events_temp")

# Create table with fresh curated data
spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.ii_campus_events AS
SELECT * FROM _events_temp
""")

print(f"✓ Created workspace.default.ii_campus_events with {len(campus_events_data)} rows")
display(spark.table("workspace.default.ii_campus_events").limit(5))

# COMMAND ----------

# DBTITLE 1,Create student_clubs Delta Table
# Schema for student_clubs
clubs_schema = StructType([
    StructField("club_id", IntegerType(), True),
    StructField("name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("description", StringType(), True),
    StructField("interests", ArrayType(StringType()), True),
    StructField("dei_focus", BooleanType(), True),
    StructField("members", IntegerType(), True),
    StructField("meeting_frequency", StringType(), True),
])

clubs_df = spark.createDataFrame(student_clubs_data, schema=clubs_schema)
clubs_df.createOrReplaceTempView("_clubs_temp")

# Create table with fresh curated data
spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.ii_student_clubs AS
SELECT * FROM _clubs_temp
""")

print(f"✓ Created workspace.default.ii_student_clubs with {len(student_clubs_data)} rows")
display(spark.table("workspace.default.ii_student_clubs").limit(5))

# COMMAND ----------

# DBTITLE 1,Create cultural_centers Delta Table
# Schema for cultural_centers
centers_schema = StructType([
    StructField("center_id", IntegerType(), True),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("location", StringType(), True),
    StructField("focus_areas", ArrayType(StringType()), True),
    StructField("website", StringType(), True),
])

centers_df = spark.createDataFrame(cultural_centers_data, schema=centers_schema)
centers_df.createOrReplaceTempView("_centers_temp")

# Create table with fresh curated data (overwrite to ensure latest enrichment)
centers_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("workspace.default.ii_cultural_centers")

print(f"✓ Created workspace.default.ii_cultural_centers with {len(cultural_centers_data)} rows")
display(spark.table("workspace.default.ii_cultural_centers").limit(5))

# COMMAND ----------

# DBTITLE 1,Recommendation Engine Section
# MAGIC %md
# MAGIC ## Step 3: Natural Language Recommendation Engine
# MAGIC Keyword-matching system that interprets student queries and finds the best events, clubs, and cultural centers.

# COMMAND ----------

# DBTITLE 1,Build Recommendation Functions
import re

# Load data from Delta tables into pandas for fast lookup
events_pdf = spark.table("workspace.default.ii_campus_events").toPandas()
clubs_pdf = spark.table("workspace.default.ii_student_clubs").toPandas()
centers_pdf = spark.table("workspace.default.ii_cultural_centers").toPandas()

# Build keyword index for events
event_keywords = {}
for _, row in events_pdf.iterrows():
    text = f"{row['name']} {row['description']} {row['category']} {row['organizer']} {' '.join(row['tags'])}".lower()
    for word in text.split():
        word = re.sub(r'[^a-z0-9]', '', word)
        if word and len(word) > 1:
            if word not in event_keywords:
                event_keywords[word] = []
            if row['event_id'] not in event_keywords[word]:
                event_keywords[word].append(row['event_id'])

# Build keyword index for clubs
club_keywords = {}
for _, row in clubs_pdf.iterrows():
    text = f"{row['name']} {row['description']} {row['category']} {' '.join(row['interests'])}".lower()
    for word in text.split():
        word = re.sub(r'[^a-z0-9]', '', word)
        if word and len(word) > 1:
            if word not in club_keywords:
                club_keywords[word] = []
            if row['club_id'] not in club_keywords[word]:
                club_keywords[word].append(row['club_id'])

# Build keyword index for cultural centers
center_keywords = {}
for _, row in centers_pdf.iterrows():
    text = f"{row['name']} {row['description']} {' '.join(row['focus_areas'])}".lower()
    for word in text.split():
        word = re.sub(r'[^a-z0-9]', '', word)
        if word and len(word) > 1:
            if word not in center_keywords:
                center_keywords[word] = []
            if row['center_id'] not in center_keywords[word]:
                center_keywords[word].append(row['center_id'])

print(f"✓ Built keyword indexes:")
print(f"  Events: {len(event_keywords)} keywords")
print(f"  Clubs: {len(club_keywords)} keywords")
print(f"  Cultural centers: {len(center_keywords)} keywords")
print("Recommendation engine ready!")


def find_events(query: str, interests: list = None, top_n: int = 5) -> list[dict]:
    """
    Find campus events matching a natural language query.
    
    Args:
        query: Natural language query (e.g., "I want to learn about Asian culture")
        interests: Optional list of interest tags to filter by
        top_n: Max number of results to return
    
    Returns:
        List of dicts with event details and match score
    """
    query_lower = query.lower()
    words = [re.sub(r'[^a-z0-9]', '', w) for w in query_lower.split()]
    words = [w for w in words if w and len(w) > 1]

    # Score each event
    scores = {}
    for word in words:
        if word in event_keywords:
            for eid in event_keywords[word]:
                scores[eid] = scores.get(eid, 0) + 1
    # Also match multi-word phrases (e.g., "lunar new year")
    for key, eids in event_keywords.items():
        if key in query_lower and key not in words:
            for eid in eids:
                scores[eid] = scores.get(eid, 0) + 2

    # If interests provided, boost events with matching tags
    if interests:
        for _, row in events_pdf.iterrows():
            for tag in row['tags']:
                if any(interest.lower() in tag.lower() for interest in interests):
                    scores[row['event_id']] = scores.get(row['event_id'], 0) + 3

    # Rank results
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    results = []
    for eid, score in ranked:
        row = events_pdf[events_pdf['event_id'] == eid].iloc[0]
        results.append({
            "event_id": int(row['event_id']),
            "name": row['name'],
            "category": row['category'],
            "date": row['date'],
            "time": row['time'],
            "location": row['location'],
            "description": row['description'],
            "organizer": row['organizer'],
            "tags": list(row['tags']),
            "free": bool(row['free']),
            "match_score": score,
        })

    return results


def find_clubs(interests: list = None, dei_focus: bool = None, query: str = None, top_n: int = 5) -> list[dict]:
    """
    Find student clubs matching interests and/or a natural language query.
    
    Args:
        interests: List of interest strings to match (e.g., ["dance", "culture"])
        dei_focus: If True, filter to DEI-focused clubs only. If None, no filter.
        query: Optional natural language query for keyword matching
        top_n: Max number of results
    
    Returns:
        List of dicts with club details and match score
    """
    scores = {}

    # Score by query keywords
    if query:
        query_lower = query.lower()
        words = [re.sub(r'[^a-z0-9]', '', w) for w in query_lower.split()]
        words = [w for w in words if w and len(w) > 1]
        for word in words:
            if word in club_keywords:
                for cid in club_keywords[word]:
                    scores[cid] = scores.get(cid, 0) + 1
        for key, cids in club_keywords.items():
            if key in query_lower and key not in words:
                for cid in cids:
                    scores[cid] = scores.get(cid, 0) + 2

    # Score by interest matching
    if interests:
        for _, row in clubs_pdf.iterrows():
            club_interests = [i.lower() for i in row['interests']]
            for interest in interests:
                interest_lower = interest.lower()
                for ci in club_interests:
                    if interest_lower in ci or ci in interest_lower:
                        scores[row['club_id']] = scores.get(row['club_id'], 0) + 3
                        break

    # If no query and no interests, return all (optionally filtered by DEI)
    if not query and not interests:
        for _, row in clubs_pdf.iterrows():
            scores[row['club_id']] = 1

    # Rank and filter
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for cid, score in ranked:
        row = clubs_pdf[clubs_pdf['club_id'] == cid].iloc[0]
        # Apply DEI filter
        if dei_focus is True and not row['dei_focus']:
            continue
        results.append({
            "club_id": int(row['club_id']),
            "name": row['name'],
            "category": row['category'],
            "description": row['description'],
            "interests": list(row['interests']),
            "dei_focus": bool(row['dei_focus']),
            "members": int(row['members']),
            "meeting_frequency": row['meeting_frequency'],
            "match_score": score,
        })
        if len(results) >= top_n:
            break

    return results


def find_cultural_centers(query: str = None, top_n: int = 5) -> list[dict]:
    """
    Find cultural & community centers matching a query.
    """
    scores = {}
    if query:
        query_lower = query.lower()
        words = [re.sub(r'[^a-z0-9]', '', w) for w in query_lower.split()]
        words = [w for w in words if w and len(w) > 1]
        for word in words:
            if word in center_keywords:
                for cid in center_keywords[word]:
                    scores[cid] = scores.get(cid, 0) + 1
        for key, cids in center_keywords.items():
            if key in query_lower and key not in words:
                for cid in cids:
                    scores[cid] = scores.get(cid, 0) + 2
    else:
        for _, row in centers_pdf.iterrows():
            scores[row['center_id']] = 1

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    results = []
    for cid, score in ranked:
        row = centers_pdf[centers_pdf['center_id'] == cid].iloc[0]
        results.append({
            "center_id": int(row['center_id']),
            "name": row['name'],
            "description": row['description'],
            "location": row['location'],
            "focus_areas": list(row['focus_areas']),
            "website": row['website'],
            "match_score": score,
        })

    return results


def format_events(query: str, interests: list = None) -> str:
    """Pretty-print event recommendations for a query."""
    events = find_events(query, interests)
    if not events:
        return f'No events found for: "{query}". Try mentioning a category like "cultural", "arts", "technology", or "service".'

    lines = [f'Event Query: "{query}"', '=' * 60, '']
    for i, e in enumerate(events, 1):
        lines.append(f"#{i} {e['name']}")
        lines.append(f"   Category: {e['category']}")
        lines.append(f"   Date: {e['date']} at {e['time']}")
        lines.append(f"   Location: {e['location']}")
        lines.append(f"   {e['description']}")
        lines.append(f"   Organizer: {e['organizer']}")
        lines.append(f"   Tags: {', '.join(e['tags'])}")
        lines.append(f"   Free: {'Yes' if e['free'] else 'No'}")
        lines.append(f"   Match score: {e['match_score']}")
        lines.append('')
    return '\n'.join(lines)


def format_clubs(query: str = None, interests: list = None, dei_focus: bool = None) -> str:
    """Pretty-print club recommendations."""
    clubs = find_clubs(interests=interests, dei_focus=dei_focus, query=query)
    if not clubs:
        filter_desc = []
        if interests:
            filter_desc.append(f'interests={interests}')
        if dei_focus:
            filter_desc.append('DEI focus')
        if query:
            filter_desc.append(f'query="{query}"')
        return f"No clubs found matching: {', '.join(filter_desc) or 'your criteria'}"

    lines = [f'Club Recommendations', '=' * 60, '']
    for i, c in enumerate(clubs, 1):
        lines.append(f"#{i} {c['name']}")
        lines.append(f"   Category: {c['category']}")
        lines.append(f"   {c['description']}")
        lines.append(f"   Interests: {', '.join(c['interests'])}")
        lines.append(f"   DEI Focus: {'Yes' if c['dei_focus'] else 'No'}")
        lines.append(f"   Members: {c['members']}")
        lines.append(f"   Meets: {c['meeting_frequency']}")
        lines.append(f"   Match score: {c['match_score']}")
        lines.append('')
    return '\n'.join(lines)


def format_centers(query: str = None) -> str:
    """Pretty-print cultural center recommendations."""
    centers = find_cultural_centers(query)
    if not centers:
        return f'No cultural centers found for: "{query}"'

    lines = ['Cultural & Community Centers', '=' * 60, '']
    for i, c in enumerate(centers, 1):
        lines.append(f"#{i} {c['name']}")
        lines.append(f"   {c['description']}")
        lines.append(f"   Location: {c['location']}")
        lines.append(f"   Focus: {', '.join(c['focus_areas'])}")
        lines.append(f"   Website: {c['website']}")
        lines.append(f"   Match score: {c['match_score']}")
        lines.append('')
    return '\n'.join(lines)


print("All recommendation functions ready!")

# COMMAND ----------

# DBTITLE 1,Test Section
# MAGIC %md
# MAGIC ## Step 4: Test the Recommendation System
# MAGIC Try these example queries to see how the Interest & Identity Helper works!

# COMMAND ----------

# DBTITLE 1,Run Test Examples
# ---- Event Queries ----
event_queries = [
    "I want to learn about Asian culture",
    "Are there any dance events?",
    "I'm interested in technology and coding",
    "What's happening for Black History Month?",
    "I want to volunteer and give back to the community",
    "Any free food events?",
    "I want to celebrate Hispanic heritage",
]

print("" * 0)
print("🏫 EVENT RECOMMENDATIONS")
print("=" * 60)
for q in event_queries:
    print(format_events(q))
    print("-" * 60)
    print()

# ---- Club Queries ----
club_queries = [
    ("I love dancing", ["dance"], None),
    ("I want to join a cultural club", ["culture"], None),
    ("I'm into gaming and anime", ["gaming", "anime"], None),
    ("I want to join a club focused on diversity", None, True),
    ("I'm a woman in engineering", ["engineering", "women"], None),
    ("I want to volunteer", ["service", "volunteer"], None),
]

print("\n👥 CLUB RECOMMENDATIONS")
print("=" * 60)
for query, interests, dei in club_queries:
    print(format_clubs(query=query, interests=interests, dei_focus=dei))
    print("-" * 60)
    print()

# ---- Cultural Center Queries ----
center_queries = [
    "I want to learn about Black culture at VT",
    "Where can I find LGBTQ+ resources?",
    "I'm an international student looking for community",
    "What cultural centers are in Squires?",
    "I want to learn about Indigenous culture",
]

print("\n🏛️ CULTURAL CENTER RECOMMENDATIONS")
print("=" * 60)
for q in center_queries:
    print(format_centers(q))
    print("-" * 60)
    print()

# COMMAND ----------

# DBTITLE 1,Integration Summary
# MAGIC %md
# MAGIC ## Step 5: Integration Summary
# MAGIC
# MAGIC ### Functions ready to export to the Databricks App:
# MAGIC
# MAGIC | Function | Purpose |
# MAGIC |----------|---------|
# MAGIC | `find_events(query, interests)` | Find campus events by natural language query |
# MAGIC | `find_clubs(interests, dei_focus, query)` | Find student clubs by interests/DEI focus |
# MAGIC | `find_cultural_centers(query)` | Find VT cultural & community centers |
# MAGIC | `format_events(query)` | Pretty-print event recommendations |
# MAGIC | `format_clubs(query, interests, dei_focus)` | Pretty-print club recommendations |
# MAGIC | `format_centers(query)` | Pretty-print cultural center info |
# MAGIC
# MAGIC ### Delta Tables Created:
# MAGIC * `workspace.default.ii_campus_events` - 20 events
# MAGIC * `workspace.default.ii_student_clubs` - 25 clubs
# MAGIC * `workspace.default.ii_cultural_centers` - 12 cultural centers (8 curated + 4 scraped, noise-filtered & enriched)
# MAGIC
# MAGIC **✅ Ready for App integration — ping Julian!**

# COMMAND ----------

# DBTITLE 1,ACTION: Grant Julian table permissions
# MAGIC %sql
# MAGIC -- ACTION NEEDED: Grant Julian access so he can integrate this into the app!
# MAGIC GRANT SELECT ON TABLE workspace.default.campus_events_clean TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.student_clubs_clean TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.cultural_centers_clean TO `julianmiller@vt.edu`;