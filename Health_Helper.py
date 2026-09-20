# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Feature Overview
# MAGIC %md
# MAGIC # 💪 Health Helper - VThacks Campus Life Intelligence Hub
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC Health Helper provides students with information about:
# MAGIC * **Gym/Fitness** - Live occupancy, hours, facilities (McComas, War Memorial, Esports, Bouldering Wall)
# MAGIC * **Mental Health** - Cook Counseling Center, Hokie Wellness, Dean of Students, crisis resources
# MAGIC * **Schiffert Health Center** - On-campus medical services, appointments, hours
# MAGIC
# MAGIC ## Data Sources
# MAGIC * Gym Occupancy (live): https://connect.recsports.vt.edu/facilityoccupancy
# MAGIC * Gym Facilities: https://recsports.vt.edu/facilities.html
# MAGIC * Mental Health: https://well-being.vt.edu/mental-health.html
# MAGIC * Schiffert Health Center: https://healthcenter.vt.edu/
# MAGIC
# MAGIC ## Tables to Create
# MAGIC * `workspace.default.gym_info` - Facilities, hours, live occupancy
# MAGIC * `workspace.default.health_resources` - Mental health + Schiffert services
# MAGIC
# MAGIC ## Functions to Export
# MAGIC * `find_health_resources(query: str) -> list[dict]`
# MAGIC * `get_gym_occupancy() -> dict`
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# Install packages needed for web scraping
import subprocess
import sys

print("Installing required packages...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4"])
print("✓ Packages installed: requests, beautifulsoup4")

# COMMAND ----------

# DBTITLE 1,Scrape Gym Occupancy (Live)
import requests
from bs4 import BeautifulSoup
import re
import json

# ============================================================================
# SCRAPE LIVE GYM OCCUPANCY FROM VT RecSports
# ============================================================================
# The occupancy page at connect.recsports.vt.edu/facilityoccupancy has
# occupancy-card divs with facility name, max occupancy, and current %.

OCCUPANCY_URL = "https://connect.recsports.vt.edu/facilityoccupancy"

response = requests.get(OCCUPANCY_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

print(f"Page fetched: {response.status_code}")

# Parse occupancy cards
cards = soup.find_all("div", class_="occupancy-card")
print(f"Found {len(cards)} occupancy cards")

occupancy_data = []
for card in cards:
    name_div = card.find("div", class_="occupancy-card-header-line-1")
    body_div = card.find("div", class_="occupancy-card-body")
    
    if not name_div or not body_div:
        continue
    
    name = name_div.get_text(strip=True)
    body_text = body_div.get_text(strip=True)
    
    max_match = re.search(r"Max Occupancy:\s*(\d+)", body_text)
    pct_match = re.search(r"Current Occupancy:\s*(\d+)%", body_text)
    
    max_occupancy = int(max_match.group(1)) if max_match else 0
    current_pct = int(pct_match.group(1)) if pct_match else 0
    current_count = int(max_occupancy * current_pct / 100) if max_occupancy else 0
    
    occupancy_data.append({
        "facility_name": name,
        "max_occupancy": max_occupancy,
        "current_occupancy_pct": current_pct,
        "current_occupancy_count": current_count,
    })
    print(f"  ✓ {name}: {current_pct}% ({current_count}/{max_occupancy})")

print(f"\n✓ Collected live occupancy for {len(occupancy_data)} facilities")

# COMMAND ----------

# DBTITLE 1,Build Gym Facility Data
# ============================================================================
# BUILD GYM FACILITY DATA
# ============================================================================
# Combine live occupancy with facility details (hours, amenities, location)

FACILITY_DETAILS = {
    "McComas Hall": {
        "location": "128 McComas Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 6:00am-12:00am, Sat-Sun 9:00am-12:00am",
        "amenities": "Weight room, cardio equipment, basketball courts, swimming pool, indoor track, group fitness studios",
        "phone": "540-231-9987",
        "description": "McComas Hall is VT's main fitness facility with a weight room, cardio area, pool, courts, and group fitness classes. It's the largest gym on campus.",
    },
    "WMH Service Desk": {
        "location": "War Memorial Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 6:00am-11:00pm, Sat-Sun 9:00am-11:00pm",
        "amenities": "Weight room, cardio equipment, basketball courts, racquetball courts, group fitness studios",
        "phone": "540-231-8714",
        "description": "War Memorial Hall (WMH) is VT's historic recreation facility with weights, cardio, courts, and fitness studios. Less crowded than McComas.",
    },
    "Esports": {
        "location": "212 Squires Student Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 2:00pm-11:00pm, Sat-Sun 12:00pm-11:00pm",
        "amenities": "Gaming PCs, consoles, streaming setup, gaming chairs",
        "phone": "540-231-5005",
        "description": "The VT Esports Center features high-end gaming PCs, consoles, and a streaming setup for casual and competitive gaming.",
    },
    "Bouldering Wall": {
        "location": "War Memorial Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 3:00pm-10:00pm, Sat-Sun 1:00pm-6:00pm",
        "amenities": "Bouldering wall, climbing shoes rental, crash pads",
        "phone": "540-231-8714",
        "description": "The Bouldering Wall in War Memorial Hall offers indoor climbing for all skill levels. Shoes available for rent.",
    },
}

# Merge occupancy data with facility details
gym_rows = []
for i, occ in enumerate(occupancy_data, 1):
    name = occ["facility_name"]
    details = FACILITY_DETAILS.get(name, {})
    
    pct = occ["current_occupancy_pct"]
    if pct < 30:
        crowd_level = "Not crowded"
    elif pct < 60:
        crowd_level = "Moderately busy"
    elif pct < 85:
        crowd_level = "Busy"
    else:
        crowd_level = "Very busy"
    
    row = {
        "id": i,
        "facility_name": name,
        "max_occupancy": occ["max_occupancy"],
        "current_occupancy_pct": occ["current_occupancy_pct"],
        "current_occupancy_count": occ["current_occupancy_count"],
        "crowd_level": crowd_level,
        "location": details.get("location", "Virginia Tech campus"),
        "hours": details.get("hours", "Call for hours"),
        "amenities": details.get("amenities", ""),
        "phone": details.get("phone", ""),
        "description": details.get("description", ""),
    }
    gym_rows.append(row)

# Add any facilities from FACILITY_DETAILS that weren't in the occupancy scrape
existing_names = {r["facility_name"] for r in gym_rows}
for name, details in FACILITY_DETAILS.items():
    if name not in existing_names:
        i = len(gym_rows) + 1
        gym_rows.append({
            "id": i,
            "facility_name": name,
            "max_occupancy": 0,
            "current_occupancy_pct": 0,
            "current_occupancy_count": 0,
            "crowd_level": "Unknown",
            "location": details.get("location", "Virginia Tech campus"),
            "hours": details.get("hours", "Call for hours"),
            "amenities": details.get("amenities", ""),
            "phone": details.get("phone", ""),
            "description": details.get("description", ""),
        })

print(f"✓ Built gym data for {len(gym_rows)} facilities:")
for row in gym_rows:
    print(f"  - {row['facility_name']}: {row['current_occupancy_pct']}% ({row['crowd_level']})")

# COMMAND ----------

# DBTITLE 1,Build Health Resources Data
# ============================================================================
# BUILD HEALTH RESOURCES DATA
# ============================================================================
# Mental health resources (from well-being.vt.edu) + Schiffert Health Center services

health_resources = [
    # --- MENTAL HEALTH ---
    {
        "category": "Mental Health",
        "name": "Cook Counseling Center",
        "description": "Free, confidential counseling services for VT students. Individual therapy, group counseling, crisis intervention, and psychiatric consultations. Walk-in hours available for urgent concerns.",
        "location": "240 McComas Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (walk-in crisis hours available)",
        "phone": "540-231-6557",
        "website": "https://well-being.vt.edu/index/Cook_Counseling_Center.html",
        "keywords": "counselor counseling therapy mental health depression anxiety stress crisis appointment",
    },
    {
        "category": "Mental Health",
        "name": "Hokie Wellness",
        "description": "Comprehensive wellness programs including mental health screenings, wellness coaching, stress management workshops, sleep hygiene education, and substance use resources. Offers online self-assessment tools.",
        "location": "141 McComas Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-2233",
        "website": "https://well-being.vt.edu/index/hokie_wellness.html",
        "keywords": "wellness stress sleep mental health self-care wellbeing coaching workshop",
    },
    {
        "category": "Mental Health",
        "name": "Dean of Students",
        "description": "Supports students in crisis, handles absences, medical withdrawals, and academic relief. Can help with personal, academic, or family emergencies. File a report of concern for a struggling friend.",
        "location": "154 Squires Student Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-3787",
        "website": "https://well-being.vt.edu/index/dos.html",
        "keywords": "dean students crisis emergency absence withdrawal academic relief report concern",
    },
    {
        "category": "Mental Health",
        "name": "VT Better Together - Mental Health Initiative",
        "description": "VT's mental health awareness initiative. Learn about mental health, help a friend in need, and find resources to get help. Includes online screening tools and crisis resources.",
        "location": "Online + Various Campus Locations",
        "hours": "24/7 online resources",
        "phone": "540-231-6557",
        "website": "https://well-being.vt.edu/mental-health.html",
        "keywords": "mental health awareness help friend learn get help better together screening",
    },
    {
        "category": "Mental Health",
        "name": "Services for Students with Disabilities (SSD)",
        "description": "Academic accommodations, assistive technology, and support services for students with disabilities including mental health conditions. Provides testing accommodations, note-taking services, and more.",
        "location": "141 Lavery Hall, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-3788",
        "website": "https://well-being.vt.edu/index/ssd.html",
        "keywords": "disability accommodation testing assistive technology accessibility special needs",
    },
    {
        "category": "Mental Health",
        "name": "VT Crisis Text Line",
        "description": "Text HOME to 741741 to connect with a trained crisis counselor 24/7. Free, confidential support for anyone in crisis.",
        "location": "Text-based (nationwide)",
        "hours": "24/7",
        "phone": "Text HOME to 741741",
        "website": "https://www.crisistextline.org",
        "keywords": "crisis text emergency suicide help hotline urgent immediate 24/7",
    },
    {
        "category": "Mental Health",
        "name": "988 Suicide & Crisis Lifeline",
        "description": "Call or text 988 for 24/7 free, confidential support for people in distress, prevention and crisis resources for you or your loved ones.",
        "location": "Phone/text (nationwide)",
        "hours": "24/7",
        "phone": "988",
        "website": "https://988lifeline.org",
        "keywords": "crisis suicide emergency hotline urgent immediate 988 help distress",
    },
    # --- SCHIFFERT HEALTH CENTER (Physical Health) ---
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Medical Clinic",
        "description": "Primary care services for VT students including treatment for illness, injury, and routine medical concerns. Staffed by 17 doctors, nurse practitioners, and physician assistants.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (call for current hours)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/primary_care.html",
        "keywords": "doctor medical clinic sick illness injury primary care appointment health center schiffert",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Gynecology Clinic",
        "description": "Women's health services including annual exams, birth control consultations, STI testing, and gynecological care. Confidential and available to all eligible students.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment required)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/womens_clinic.html",
        "keywords": "gynecology women birth control exam pelvic pap smear std testing",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Allergy and Immunization Clinic",
        "description": "Allergy shots, routine immunizations, flu vaccines, and travel immunizations. Mass vaccination clinics offered seasonally. Keep your immunizations up to date.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment preferred)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/allergy_immunization_clinic.html",
        "keywords": "allergy immunization vaccine flu shot vaccination allergy shot",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Pharmacy",
        "description": "Full-service pharmacy on campus. Fill prescriptions, get over-the-counter medications, and receive medication counseling. Conveniently located inside Schiffert Health Center.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:30am-5:00pm",
        "phone": "540-231-7166",
        "website": "https://healthcenter.vt.edu/ourservices/pharmacy.html",
        "keywords": "pharmacy prescription medication drugs over the counter refill",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Laboratory",
        "description": "On-site laboratory for blood work, urinalysis, and other diagnostic tests. Results available quickly without leaving campus.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/Laboratory.html",
        "keywords": "laboratory lab blood test urinalysis diagnostic lab work bloodwork",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Nutrition Services",
        "description": "Registered dietitians provide individual nutrition counseling, eating disorder support, and dietary guidance for students with food allergies or special dietary needs.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment required)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/nutrition_services.html",
        "keywords": "nutrition dietitian eating disorder food allergy diet counseling healthy eating",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - HIV/STI Testing",
        "description": "Confidential HIV and STI testing. Includes HIV (AIDS) testing, STI testing, and HPV vaccine information. Free or low-cost options available.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment preferred)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/HIV-STD_testing_info.html",
        "keywords": "hiv sti std testing aids sexual health vaccine hpv confidential",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Orthopedics",
        "description": "Orthopedic clinic for sports injuries, sprains, strains, and musculoskeletal concerns. On-campus treatment without needing to go off-site.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment required)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/orthopedics.html",
        "keywords": "orthopedics sports injury sprain strain fracture muscle bone joint physical",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Travel Clinic",
        "description": "Pre-travel consultations, travel immunizations, and travel health advice for students studying abroad or traveling internationally.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm (appointment required)",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices/travel_clinic.html",
        "keywords": "travel clinic immunization vaccine abroad international trip",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - X-Ray",
        "description": "On-site radiology services including X-rays for diagnostic imaging. Quick results available without leaving campus.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/ourservices.html",
        "keywords": "x-ray radiology imaging diagnostic scan bone fracture",
    },
    {
        "category": "Physical Health",
        "name": "Schiffert Health Center - Appointments",
        "description": "Schedule medical appointments online via the Healthy Hokies Portal. Same-day appointments often available for urgent concerns. All enrolled VT students who paid the health fee are eligible.",
        "location": "Schiffert Health Center, Blacksburg, VA 24061",
        "hours": "Mon-Fri 8:00am-5:00pm",
        "phone": "540-231-6444",
        "website": "https://healthcenter.vt.edu/appointments.html",
        "keywords": "appointment schedule book medical doctor health center healthy hokies portal",
    },
    # --- EMERGENCY ---
    {
        "category": "Emergency",
        "name": "VT Rescue Squad",
        "description": "Student-run emergency medical services providing 24/7 emergency medical response on campus. Call 911 for emergencies.",
        "location": "Campus-wide",
        "hours": "24/7",
        "phone": "911",
        "website": "https://www.vt.edu",
        "keywords": "emergency 911 rescue ambulance medical urgent immediate help",
    },
    {
        "category": "Emergency",
        "name": "Virginia Tech Police",
        "description": "Campus police for emergencies, safety concerns, and escort services. Call 911 for emergencies or 540-231-6411 for non-emergencies.",
        "location": "330 Sterrett Drive, Blacksburg, VA 24060",
        "hours": "24/7",
        "phone": "540-231-6411 (non-emergency), 911 (emergency)",
        "website": "https://www.police.vt.edu",
        "keywords": "police safety security escort emergency 911 crime help",
    },
]

for i, resource in enumerate(health_resources, 1):
    resource["id"] = i

print(f"✓ Built {len(health_resources)} health resources:")
categories = {}
for r in health_resources:
    cat = r["category"]
    categories[cat] = categories.get(cat, 0) + 1
for cat, count in categories.items():
    print(f"  - {cat}: {count} resources")

# COMMAND ----------

# DBTITLE 1,Create Delta Tables
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# ============================================================================
# CREATE DELTA LAKE TABLES
# ============================================================================

# workspace catalog already exists; use workspace.default schema
# (no CREATE CATALOG / CREATE SCHEMA permission needed)

# --- Table 1: gym_info ---
gym_schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("facility_name", StringType(), True),
    StructField("max_occupancy", IntegerType(), True),
    StructField("current_occupancy_pct", IntegerType(), True),
    StructField("current_occupancy_count", IntegerType(), True),
    StructField("crowd_level", StringType(), True),
    StructField("location", StringType(), True),
    StructField("hours", StringType(), True),
    StructField("amenities", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("description", StringType(), True),
])

gym_df = spark.createDataFrame(gym_rows, schema=gym_schema)
gym_df.createOrReplaceTempView("_gym_temp")

spark.sql("""
CREATE OR REPLACE TABLE workspace.default.gym_info AS
SELECT * FROM _gym_temp
""")

print(f"✓ Created workspace.default.gym_info with {len(gym_rows)} rows")

# --- Table 2: health_resources ---
health_schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("category", StringType(), True),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("location", StringType(), True),
    StructField("hours", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("website", StringType(), True),
    StructField("keywords", StringType(), True),
])

health_df = spark.createDataFrame(health_resources, schema=health_schema)
health_df.createOrReplaceTempView("_health_temp")

spark.sql("""
CREATE OR REPLACE TABLE workspace.default.health_resources AS
SELECT * FROM _health_temp
""")

print(f"✓ Created workspace.default.health_resources with {len(health_resources)} rows")

# Verify
display(spark.table("workspace.default.gym_info"))

# COMMAND ----------

# DBTITLE 1,Build Health Resource Finder Function
import re

# ============================================================================
# BUILD RECOMMENDATION FUNCTIONS
# ============================================================================

# Load data from Delta tables into pandas for fast lookup
health_pdf = spark.table("workspace.default.health_resources").toPandas()
gym_pdf = spark.table("workspace.default.gym_info").toPandas()

# Build keyword index for health resources
health_keyword_index = {}
for _, row in health_pdf.iterrows():
    resource_id = row["id"]
    text = f"{row['name']} {row['description']} {row['keywords']}".lower()
    for word in re.findall(r"\b\w+\b", text):
        if len(word) > 2:
            if word not in health_keyword_index:
                health_keyword_index[word] = set()
            health_keyword_index[word].add(resource_id)

# Synonyms / aliases to improve matching
SYNONYMS = {
    "sad": {"depression", "mental", "counseling"},
    "depressed": {"depression", "mental", "counseling"},
    "anxious": {"anxiety", "mental", "counseling"},
    "panic": {"anxiety", "crisis", "counseling"},
    "overwhelmed": {"stress", "mental", "counseling"},
    "lonely": {"mental", "counseling", "wellness"},
    "tired": {"sleep", "wellness", "nutrition"},
    "flu": {"medical", "clinic", "health", "sick"},
    "cold": {"medical", "clinic", "health", "sick"},
    "injured": {"orthopedics", "medical", "injury", "clinic"},
    "hurt": {"orthopedics", "medical", "injury"},
    "pregnant": {"gynecology", "womens", "health"},
    "vaccine": {"immunization", "allergy", "clinic"},
    "prescription": {"pharmacy", "medication"},
    "medicine": {"pharmacy", "medication"},
    "blood": {"laboratory", "lab", "test"},
}

def find_health_resources(query: str) -> list:
    """
    Find health resources matching a natural language query.
    
    Args:
        query: Natural language query from student
    
    Returns:
        List of dicts with matched health resources, sorted by relevance
    """
    query_lower = query.lower()
    query_words = re.findall(r"\b\w+\b", query_lower)
    
    expanded_words = set(query_words)
    for word in query_words:
        if word in SYNONYMS:
            expanded_words.update(SYNONYMS[word])
    
    scores = {}
    for word in expanded_words:
        if word in health_keyword_index:
            for rid in health_keyword_index[word]:
                scores[rid] = scores.get(rid, 0) + 1
    
    for _, row in health_pdf.iterrows():
        cat = row["category"].lower()
        if cat in query_lower:
            scores[row["id"]] = scores.get(row["id"], 0) + 3
    
    # Crisis boost: if the query contains crisis-related words, heavily
    # boost Emergency resources and those with crisis/suicide/hotline keywords
    crisis_terms = {"crisis", "suicide", "emergency", "urgent", "immediate",
                    "kill myself", "end my life", "hurt myself", "help now",
                    "overdose", "self-harm", "self harm", "dying"}
    if any(term in query_lower for term in crisis_terms):
        for _, row in health_pdf.iterrows():
            keywords = row["keywords"].lower()
            if any(kw in keywords for kw in ["crisis", "suicide", "emergency", "988", "hotline"]):
                scores[row["id"]] = scores.get(row["id"], 0) + 10
    
    if not scores:
        return []
    
    category_priority = {"Emergency": 0, "Mental Health": 1, "Physical Health": 2}
    ranked = sorted(scores.items(), key=lambda x: (
        -x[1],
        category_priority.get(health_pdf[health_pdf["id"] == x[0]].iloc[0]["category"], 99)
    ))
    
    results = []
    for rid, score in ranked[:5]:
        row = health_pdf[health_pdf["id"] == rid].iloc[0]
        results.append({
            "id": int(rid),
            "category": row["category"],
            "name": row["name"],
            "description": row["description"],
            "location": row["location"],
            "hours": row["hours"],
            "phone": row["phone"],
            "website": row["website"],
            "match_score": int(score),
        })
    
    return results

print("✓ find_health_resources() function ready!")

# COMMAND ----------

# DBTITLE 1,Build Gym Occupancy Function
# ============================================================================
# GYM OCCUPANCY FUNCTION
# ============================================================================

def get_gym_occupancy(facility_name: str = None) -> dict:
    """
    Get current gym occupancy data. Optionally filter by facility name.
    
    Args:
        facility_name: Optional facility name to filter (e.g., 'McComas').
                       If None, returns all facilities.
    
    Returns:
        Dict with gym occupancy information
    """
    if facility_name:
        facility_name_lower = facility_name.lower()
        matching = gym_pdf[gym_pdf["facility_name"].str.lower().str.contains(facility_name_lower, na=False)]
        if matching.empty:
            matching = gym_pdf[gym_pdf["description"].str.lower().str.contains(facility_name_lower, na=False)]
        if matching.empty:
            return {"error": f"No facility found matching '{facility_name}'. Available: {list(gym_pdf['facility_name'])}"}
    else:
        matching = gym_pdf
    
    facilities = []
    for _, row in matching.iterrows():
        facilities.append({
            "facility_name": row["facility_name"],
            "current_occupancy_pct": int(row["current_occupancy_pct"]),
            "current_occupancy_count": int(row["current_occupancy_count"]),
            "max_occupancy": int(row["max_occupancy"]),
            "crowd_level": row["crowd_level"],
            "hours": row["hours"],
            "location": row["location"],
            "amenities": row["amenities"],
            "description": row["description"],
        })
    
    facilities.sort(key=lambda x: x["current_occupancy_pct"])
    
    if facility_name and len(facilities) == 1:
        f = facilities[0]
        return {
            "facility_name": f["facility_name"],
            "current_occupancy_pct": f["current_occupancy_pct"],
            "current_occupancy_count": f["current_occupancy_count"],
            "max_occupancy": f["max_occupancy"],
            "crowd_level": f["crowd_level"],
            "hours": f["hours"],
            "location": f["location"],
            "amenities": f["amenities"],
            "description": f["description"],
        }
    
    return {"facilities": facilities, "total": len(facilities)}

print("✓ get_gym_occupancy() function ready!")

# COMMAND ----------

# DBTITLE 1,Combined Query Router
# ============================================================================
# COMBINED HEALTH QUERY ROUTER
# ============================================================================
# This function routes queries to either gym or health resource functions.
# The app's route_query() will call this for health-related queries.

def health_query_router(query: str) -> str:
    """
    Route a health-related query to the appropriate function and format a text response.
    This is what gets called by the app's main router for health keywords.
    
    Args:
        query: Natural language query from student
    
    Returns:
        Formatted text response for voice/text output
    """
    query_lower = query.lower()
    
    gym_keywords = ["gym", "mccomas", "war memorial", "wmh", "workout", "fitness", "exercise",
                    "weight", "cardio", "pool", "climbing", "bouldering", "esports", "crowded",
                    "occupancy", "basketball", "racquetball", "gaming"]
    
    if any(kw in query_lower for kw in gym_keywords):
        specific = None
        for name in gym_pdf["facility_name"]:
            if name.lower() in query_lower:
                specific = name
                break
        
        if specific:
            result = get_gym_occupancy(specific)
            if "error" in result:
                return result["error"]
            return (f"{result['facility_name']} is currently {result['crowd_level']} "
                    f"at {result['current_occupancy_pct']}% capacity "
                    f"({result['current_occupancy_count']} of {result['max_occupancy']} people).\n"
                    f"Hours: {result['hours']}\n"
                    f"Location: {result['location']}\n"
                    f"Amenities: {result['amenities']}")
        else:
            result = get_gym_occupancy()
            lines = ["Here's the current gym occupancy at VT:"]
            for f in result["facilities"]:
                lines.append(f"\n  {f['facility_name']}: {f['current_occupancy_pct']}% ({f['crowd_level']})")
            lines.append(f"\n\nThe least crowded facility is {result['facilities'][0]['facility_name']}.")
            return "\n".join(lines)
    
    results = find_health_resources(query)
    if not results:
        return ("I couldn't find a specific health resource for your query. "
                "You can try asking about:\n"
                "- Gym occupancy (e.g., 'How crowded is McComas?')\n"
                "- Counseling (e.g., 'I need to talk to a counselor')\n"
                "- Medical services (e.g., 'I feel sick')\n"
                "- Crisis resources (e.g., 'I need help now')")
    
    lines = [f"I found {len(results)} health resource(s) for you:"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n#{i} {r['name']} ({r['category']})")
        lines.append(f"   {r['description']}")
        lines.append(f"   Location: {r['location']}")
        lines.append(f"   Hours: {r['hours']}")
        lines.append(f"   Phone: {r['phone']}")
        if r.get('website'):
            lines.append(f"   Website: {r['website']}")
    
    return "\n".join(lines)

print("✓ health_query_router() function ready!")

# COMMAND ----------

# DBTITLE 1,Test Functions
# ============================================================================
# TEST ALL FUNCTIONS
# ============================================================================

test_queries = [
    "When is McComas least crowded?",
    "I need to talk to a counselor",
    "What time does the climbing wall close?",
    "I feel sick and need a doctor",
    "I'm feeling overwhelmed and stressed",
    "How busy is the gym right now?",
    "I need a vaccine",
    "Where can I get my prescription filled?",
    "I'm having a mental health crisis",
    "What's the least crowded gym?",
]

for query in test_queries:
    print(f"\n{'='*70}")
    print(f"QUERY: \"{query}\"")
    print(f"{'='*70}")
    response = health_query_router(query)
    print(response)

print(f"\n\n{'='*70}")
print("✓ All tests complete! Health Helper is ready to integrate into the app.")
print("\nFunctions to export to the app:")
print("  - find_health_resources(query: str) -> list[dict]")
print("  - get_gym_occupancy(facility_name: str = None) -> dict")
print("  - health_query_router(query: str) -> str  (main entry point for the app)")

# COMMAND ----------

# DBTITLE 1,Integration Notes
# MAGIC %md
# MAGIC ## Integration Notes for Julian
# MAGIC
# MAGIC To integrate into the app:
# MAGIC
# MAGIC 1. **Replace the stub** in `app.py`: Change the `find_health_resources` function to call `health_query_router` from this notebook.
# MAGIC
# MAGIC 2. **The main entry point** is `health_query_router(query: str) -> str` — it returns a formatted text response suitable for voice output.
# MAGIC
# MAGIC 3. **Tables created:**
# MAGIC    * `workspace.default.gym_info` — 4 facilities with live occupancy
# MAGIC    * `workspace.default.health_resources` — 20 resources (mental health, physical health, emergency)
# MAGIC
# MAGIC 4. **Live occupancy** is scraped fresh each time the notebook runs. For the app, the data is loaded from Delta tables, so re-run this notebook to refresh occupancy numbers.
# MAGIC
# MAGIC 5. **Gym routing keywords** (already in app.py): gym, workout, health, counselor, mental, fitness, mccomas, sick
# MAGIC
# MAGIC ---
# MAGIC **Done! Ping Julian when ready to integrate.**

# COMMAND ----------

# DBTITLE 1,ACTION: Grant Julian table permissions
# MAGIC %sql
# MAGIC -- ACTION NEEDED: Grant Julian access so he can integrate this into the app!
# MAGIC GRANT SELECT ON TABLE workspace.default.gym_info TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.health_resources TO `julianmiller@vt.edu`;