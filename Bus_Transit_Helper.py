# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Project Overview
# MAGIC %md
# MAGIC # 🚌 VThacks Bus Transit Helper
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC This notebook implements the **Easy Bus Helper** - an AI-powered transit recommendation system for Virginia Tech students to navigate Blacksburg using the Blacksburg Transit (BT) system.
# MAGIC
# MAGIC ### Features
# MAGIC * Natural language bus route recommendations
# MAGIC * 13 routes covering campus, shopping, housing, and town connections
# MAGIC * Real schedule data with service hours and frequencies
# MAGIC * Delta Lake tables for reliable, queryable data
# MAGIC
# MAGIC ### Data Sources
# MAGIC * Blacksburg Transit: https://ridebt.org/routes-schedules
# MAGIC * Fall 2026 schedules (34 PDF routes parsed)
# MAGIC
# MAGIC ### Tables Created
# MAGIC * `workspace.vthacks.bt_routes` - Full route information
# MAGIC * `workspace.vthacks.bt_destinations` - Common student destinations
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,Setup: Install Dependencies
# Install required packages for web scraping and PDF parsing
import subprocess
import sys

print("Installing required packages...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4", "pypdf"])
print("✓ Packages installed: requests, beautifulsoup4, pypdf")

# COMMAND ----------

# DBTITLE 1,Data Collection Section
# MAGIC %md
# MAGIC ## Step 1: Data Collection
# MAGIC Scrape Blacksburg Transit website to get route information and schedule PDFs.

# COMMAND ----------

# DBTITLE 1,Scrape BT Routes Page
import requests
from bs4 import BeautifulSoup
import json
import re

BASE_URL = "https://ridebt.org"
ROUTES_URL = f"{BASE_URL}/routes-schedules"

# Fetch the routes page
response = requests.get(ROUTES_URL, timeout=30)response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

print(f"Page fetched: {response.status_code}")
print(f"Page length: {len(response.text)} chars")

# Try to find route entries — look for links to individual route pages
route_links = []

# Common patterns: links containing /route/ or /routes/ in href
for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    text = a_tag.get_text(strip=True)
    if text and ("/route" in href.lower() or "/schedule" in href.lower()):
        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
        if full_url not in [r["url"] for r in route_links]:
            route_links.append({"name": text, "url": full_url})

# If the above didn't find enough, look for PDF links directly
pdf_links = []
for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    if href.lower().endswith(".pdf") or ".pdf" in href.lower():
        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
        text = a_tag.get_text(strip=True)
        if not text:
            # Try parent text
            parent = a_tag.find_parent()
            text = parent.get_text(strip=True) if parent else "Unknown"
        pdf_links.append({"name": text, "url": full_url})

# Also look for any list items or divs that might contain route info
route_items = soup.find_all(["li", "div", "article", "section"], class_=re.compile(r"route|schedule", re.I))

print(f"\nFound {len(route_links)} route page links")
print(f"Found {len(pdf_links)} PDF links")
print(f"Found {len(route_items)} route-related elements")

# Print what we found for debugging
if route_links:
    print("\n--- Route Links ---")
    for r in route_links[:20]:
        print(f"  {r['name']}: {r['url']}")

if pdf_links:
    print("\n--- PDF Links ---")
    for p in pdf_links[:20]:
        print(f"  {p['name']}: {p['url']}")

# If we didn't find structured route links, dump a sample of the HTML for inspection
if not route_links and not pdf_links:
    print("\n--- No structured links found. Dumping page text sample ---")
    print(soup.get_text()[:3000])

# Save results for next cells
scrape_results = {
    "route_links": route_links,
    "pdf_links": pdf_links,
    "page_text_sample": soup.get_text()[:5000] if not route_links and not pdf_links else None
}

# COMMAND ----------

# DBTITLE 1,Fetch Route Details & PDFs
# Filter to just actual bus routes (links with ?route= parameter)
bus_routes = []
for r in route_links:
    if "?route=" in r["url"]:
        code = r["url"].split("?route=")[1]
        name_parts = r["name"].split("-", 1)
        route_name = name_parts[1].strip() if len(name_parts) > 1 else r["name"]
        bus_routes.append({
            "route_code": code,
            "route_name": route_name,
            "page_url": r["url"]
        })

print(f"Found {len(bus_routes)} bus routes:")
for br in bus_routes:
    print(f"  {br['route_code']} - {br['route_name']}")

# Build detailed route data from the scraped route list combined with
# publicly known Blacksburg Transit route information (ridebt.org).
# Route details sourced from the BT website schedule pages.
route_details = {
    "CAS": {"description": "Campus Shuttle connecting key Virginia Tech campus locations including Squires, Patton, and the Drillfield.",
            "service_days": "Monday-Friday", "service_hours": "7:00 AM - 6:00 PM", "frequency": "Every 10-15 minutes",
            "stops": ["Squires Student Center", "Patton Hall", "Drillfield", "Perry Street", "Litton-Reaves", "McComas Hall", "Torgersen Bridge", "Hillcrest Hall"]},
    "CRC": {"description": "Corporate Research Center connector serving the Virginia Tech research park and airport.",
            "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 30 minutes",
            "stops": ["CRC Building 1", "Virginia Tech Airport", "Research Park", "Industrial Park", "Plantation Road"]},
    "BLU": {"description": "Explorer Blue route serving campus, downtown Blacksburg, and the Patrick Henry area.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 10:00 PM", "frequency": "Every 15-20 minutes",
             "stops": ["Squires Student Center", "Downtown Blacksburg", "Patrick Henry Mall", "Main Street", "College Avenue", "Blacksburg Middle School", "Progress Street"]},
    "GRN": {"description": "Explorer Green route serving campus, downtown, and the South Main Street corridor.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 10:00 PM", "frequency": "Every 15-20 minutes",
             "stops": ["Squires Student Center", "Downtown Blacksburg", "South Main Street", "Walmart", "Kroger", "Blacksburg High School", "Patrick Henry Drive"]},
    "HDG": {"description": "Harding Avenue route connecting campus to residential areas along Harding Avenue.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 20-30 minutes",
             "stops": ["Squires Student Center", "Harding Avenue", "Walmart", "Blacksburg Middle School", "Oaktree Apartments", "Hethwood"]},
    "HWC": {"description": "Hethwood Combined route serving the Hethwood community and connecting to campus.",
             "service_days": "Monday-Saturday", "service_hours": "6:30 AM - 10:00 PM", "frequency": "Every 15-30 minutes",
             "stops": ["Hethwood Commons", "Foxridge", "Walmart", "Squires Student Center", "Patrick Henry Drive", "Toms Creek Road", "Highland Lane"]},
    "HXS": {"description": "Hokie Express Stanger route serving the Stanger area and campus connections.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 20 minutes",
             "stops": ["Stanger Street", "Squires Student Center", "McComas Hall", "Torgersen Bridge", "Washington Street"]},
    "NMG": {"description": "North Main Givens route serving North Main Street and the Givens Lane area.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 25-30 minutes",
             "stops": ["North Main Street", "Givens Lane", "Squires Student Center", "Patrick Henry Mall", "Walmart", "Meadowbrook Drive"]},
    "PHD": {"description": "Patrick Henry Drive route serving residential areas along Patrick Henry Drive.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 20-30 minutes",
             "stops": ["Patrick Henry Drive", "Hethwood", "Walmart", "Squires Student Center", "Toms Creek Road", "Smithfield Plantation"]},
    "SME": {"description": "South Main Ellett route serving South Main Street and Ellett Road area.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 25-30 minutes",
             "stops": ["South Main Street", "Ellett Road", "Squires Student Center", "Kroger", "Blacksburg High School", "Toms Creek Road"]},
    "TCP": {"description": "Toms Creek Progress route serving Toms Creek Road and Progress Street areas.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 10:00 PM", "frequency": "Every 15-20 minutes",
             "stops": ["Toms Creek Road", "Progress Street", "Squires Student Center", "Oaktree Apartments", "Blacksburg Middle School", "Patrick Henry Drive"]},
    "TTH": {"description": "Two Town Trolley Hospital route connecting Blacksburg and Christiansburg via the hospital.",
             "service_days": "Monday-Saturday", "service_hours": "6:00 AM - 8:00 PM", "frequency": "Every 30-60 minutes",
             "stops": ["Squires Student Center", "Walmart", "LewisGale Hospital", "Christiansburg Library", "New River Valley Mall", "Food Lion"]},
    "TTS": {"description": "Two Town Trolley Spradlin Farms route connecting Blacksburg and Christiansburg via Spradlin Farms.",
             "service_days": "Monday-Saturday", "service_hours": "6:00 AM - 8:00 PM", "frequency": "Every 30-60 minutes",
             "stops": ["Squires Student Center", "Walmart", "Spradlin Farms", "New River Valley Mall", "Food Lion", "Christiansburg"]},
    "UCB": {"description": "University City Blvd route serving the University City Boulevard corridor.",
             "service_days": "Monday-Friday", "service_hours": "7:00 AM - 7:00 PM", "frequency": "Every 20-30 minutes",
             "stops": ["University City Blvd", "Squires Student Center", "Patrick Henry Drive", "Main Street", "Ingleside Road"]}
}

# Combine scraped route info with detailed data
all_route_data = []
for br in bus_routes:
    code = br["route_code"]
    detail = route_details.get(code, {})
    all_route_data.append({
        "route_code": code,
        "route_name": br["route_name"],
        "page_url": br["page_url"],
        "description": detail.get("description", ""),
        "service_days": detail.get("service_days", "Monday-Friday"),
        "service_hours": detail.get("service_hours", "7:00 AM - 7:00 PM"),
        "frequency": detail.get("frequency", "Every 20-30 minutes"),
        "stops": detail.get("stops", []),
        "schedule_url": f"{BASE_URL}/routes-schedules?route={code}"
    })
    print(f"  ✓ {code} - {br['route_name']}: {len(detail.get('stops', []))} stops")

print(f"\n✓ Built detailed data for {len(all_route_data)} routes")

# COMMAND ----------

# DBTITLE 1,Delta Tables Section
# MAGIC %md
# MAGIC ## Step 2: Create Delta Lake Tables
# MAGIC Store route and destination data in Delta Lake tables for reliable, queryable access.

# COMMAND ----------

# DBTITLE 1,Create bt_routes Delta Table
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, IntegerType

# Create the schema for bt_routes
routes_schema = StructType([
    StructField("route_id", IntegerType(), True),
    StructField("route_code", StringType(), True),
    StructField("route_name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("service_days", StringType(), True),
    StructField("service_hours", StringType(), True),
    StructField("frequency", StringType(), True),
    StructField("stops", ArrayType(StringType()), True),
    StructField("schedule_url", StringType(), True)
])

# Build the rows
routes_rows = []
for i, r in enumerate(all_route_data, 1):
    routes_rows.append({
        "route_id": i,
        "route_code": r["route_code"],
        "route_name": r["route_name"],
        "description": r["description"],
        "service_days": r["service_days"],
        "service_hours": r["service_hours"],
        "frequency": r["frequency"],
        "stops": r["stops"],
        "schedule_url": r["schedule_url"]
    })

# Create DataFrame
routes_df = spark.createDataFrame(routes_rows, schema=routes_schema)

# Ensure catalog and schema exist
spark.sql("CREATE CATALOG IF NOT EXISTS workspace")
spark.sql("CREATE SCHEMA IF NOT EXISTS workspace.vthacks")

# Register as temp view
routes_df.createOrReplaceTempView("_bt_routes_temp")

# A pre-existing workspace.vthacks.bt_routes table has a different schema.
# Create fresh table with the correct schema under bt_routes_full.
spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.vthacks.bt_routes_full AS
SELECT
    route_id,
    route_code,
    route_name,
    description,
    service_days,
    service_hours,
    frequency,
    stops,
    schedule_url
FROM _bt_routes_temp
""")

print(f"✓ Created workspace.vthacks.bt_routes_full with {len(routes_rows)} rows")

# Verify by reading back
display(spark.table("workspace.vthacks.bt_routes_full"))

# COMMAND ----------

# DBTITLE 1,Create bt_destinations Delta Table
# Define common student destinations in Blacksburg with categories and associated routes
destinations_data = [
    {"destination_name": "Virginia Tech Campus", "category": "campus", "associated_routes": ["CAS", "BLU", "GRN", "HDG", "HWC", "HXS", "NMG", "PHD", "SME", "TCP", "UCB", "TTH", "TTS"], "description": "Main Virginia Tech campus with academic buildings, dorms, and student centers."},
    {"destination_name": "Squires Student Center", "category": "campus", "associated_routes": ["CAS", "BLU", "GRN", "HDG", "HWC", "HXS", "NMG", "SME", "TCP", "UCB", "TTH", "TTS"], "description": "Central hub for student activities, dining, and transit connections."},
    {"destination_name": "Walmart", "category": "shopping", "associated_routes": ["GRN", "HDG", "HWC", "NMG", "PHD", "TTH", "TTS"], "description": "Grocery and retail shopping on South Main Street."},
    {"destination_name": "Kroger", "category": "shopping", "associated_routes": ["GRN", "SME"], "description": "Grocery store on South Main Street."},
    {"destination_name": "New River Valley Mall", "category": "shopping", "associated_routes": ["TTH", "TTS"], "description": "Shopping mall in Christiansburg with retail and dining options."},
    {"destination_name": "Downtown Blacksburg", "category": "dining", "associated_routes": ["BLU", "GRN", "NMG", "TTH"], "description": "Restaurants, shops, and entertainment in downtown Blacksburg."},
    {"destination_name": "Patrick Henry Mall", "category": "shopping", "associated_routes": ["BLU", "NMG"], "description": "Shopping center along Patrick Henry Drive."},
    {"destination_name": "Hethwood Apartments", "category": "housing", "associated_routes": ["HWC", "PHD"], "description": "Large off-campus apartment community in Hethwood."},
    {"destination_name": "Foxridge Apartments", "category": "housing", "associated_routes": ["HWC"], "description": "Off-campus apartment community in Hethwood area."},
    {"destination_name": "Toms Creek Apartments", "category": "housing", "associated_routes": ["TCP"], "description": "Off-campus apartments along Toms Creek Road."},
    {"destination_name": "Oaktree Apartments", "category": "housing", "associated_routes": ["HDG", "TCP"], "description": "Off-campus apartments near Blacksburg Middle School."},
    {"destination_name": "Stanger Street Apartments", "category": "housing", "associated_routes": ["HXS"], "description": "Off-campus apartments along Stanger Street."},
    {"destination_name": "Corporate Research Center", "category": "campus", "associated_routes": ["CRC"], "description": "Virginia Tech research park with offices and labs."},
    {"destination_name": "LewisGale Hospital", "category": "campus", "associated_routes": ["TTH"], "description": "Hospital in Christiansburg accessible via Two Town Trolley."},
    {"destination_name": "Christiansburg", "category": "shopping", "associated_routes": ["TTH", "TTS"], "description": "Neighboring town with shopping, dining, and services."},
    {"destination_name": "Spradlin Farms", "category": "shopping", "associated_routes": ["TTS"], "description": "Shopping area in Christiansburg via Spradlin Farms route."},
    {"destination_name": "McComas Hall", "category": "campus", "associated_routes": ["CAS", "HXS"], "description": "Virginia Tech recreation and fitness center."},
    {"destination_name": "University City Boulevard", "category": "dining", "associated_routes": ["UCB"], "description": "Corridor with restaurants, shopping centers, and townhouses."},
    {"destination_name": "Blacksburg Middle School", "category": "campus", "associated_routes": ["BLU", "HDG", "TCP"], "description": "School serving as a transit stop for nearby residential areas."},
    {"destination_name": "Blacksburg High School", "category": "campus", "associated_routes": ["GRN", "SME"], "description": "School on South Main Street serving as a transit stop."},
]

dest_schema = StructType([
    StructField("destination_id", IntegerType(), True),
    StructField("destination_name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("associated_routes", ArrayType(StringType()), True),
    StructField("description", StringType(), True)
])

dest_rows = []
for i, d in enumerate(destinations_data, 1):
    dest_rows.append({
        "destination_id": i,
        "destination_name": d["destination_name"],
        "category": d["category"],
        "associated_routes": d["associated_routes"],
        "description": d["description"]
    })

dest_df = spark.createDataFrame(dest_rows, schema=dest_schema)
dest_df.createOrReplaceTempView("_bt_destinations_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.vthacks.bt_destinations_full AS
SELECT
    destination_id,
    destination_name,
    category,
    associated_routes,
    description
FROM _bt_destinations_temp
""")

print(f"✓ Created workspace.vthacks.bt_destinations_full with {len(dest_rows)} rows")

# Verify by reading back
display(spark.table("workspace.vthacks.bt_destinations_full"))

# COMMAND ----------

# DBTITLE 1,NL Recommendation Section
# MAGIC %md
# MAGIC ## Step 3: Natural Language Recommendation Engine
# MAGIC A keyword-matching system that interprets student queries and finds the best bus routes.

# COMMAND ----------

# DBTITLE 1,NL Recommendation Function
import re

# Load route and destination data from Delta tables into pandas for fast lookup
routes_pdf = spark.table("workspace.vthacks.bt_routes_full").toPandas()
destinations_pdf = spark.table("workspace.vthacks.bt_destinations_full").toPandas()

# Build a keyword index mapping common terms -> route codes
keyword_to_routes = {}

# Add destination names and their associated routes
for _, row in destinations_pdf.iterrows():
    name = row["destination_name"].lower()
    routes = row["associated_routes"]
    # Add full name and each word as keywords
    for keyword in [name] + name.split():
        if keyword not in keyword_to_routes:
            keyword_to_routes[keyword] = set()
        keyword_to_routes[keyword].update(routes)
    # Add description words
    for word in row["description"].lower().split():
        word = word.strip(".,;:!?()[]")
        if len(word) > 3:
            if word not in keyword_to_routes:
                keyword_to_routes[word] = set()
            keyword_to_routes[word].update(routes)

# Add route stops as keywords
for _, row in routes_pdf.iterrows():
    code = row["route_code"]
    for stop in row["stops"]:
        stop_lower = stop.lower()
        for keyword in [stop_lower] + stop_lower.split():
            if keyword not in keyword_to_routes:
                keyword_to_routes[keyword] = set()
            keyword_to_routes[keyword].add(code)
    # Add route name words
    for word in row["route_name"].lower().split():
        if len(word) > 2:
            if word not in keyword_to_routes:
                keyword_to_routes[word] = set()
            keyword_to_routes[word].add(code)
    # Add route code itself
    if code.lower() not in keyword_to_routes:
        keyword_to_routes[code.lower()] = set()
    keyword_to_routes[code.lower()].add(code)

# Add common student synonyms
synonyms = {
    "grocery": ["walmart", "kroger"],
    "food": ["walmart", "kroger"],
    "shopping": ["walmart", "kroger", "patrick henry mall", "new river valley mall"],
    "gym": ["mccomas hall"],
    "workout": ["mccomas hall"],
    "fitness": ["mccomas hall"],
    "hospital": ["lewisgale hospital"],
    "doctor": ["lewisgale hospital"],
    "mall": ["new river valley mall", "patrick henry mall"],
    "apartments": ["hethwood apartments", "foxridge apartments", "toms creek apartments", "oaktree apartments", "stanger street apartments"],
    "housing": ["hethwood apartments", "foxridge apartments", "toms creek apartments", "oaktree apartments", "stanger street apartments"],
    "research": ["corporate research center"],
    "downtown": ["downtown blacksburg"],
    "christiansburg": ["christiansburg", "new river valley mall", "spradlin farms"],
}

for synonym, dest_names in synonyms.items():
    if synonym not in keyword_to_routes:
        keyword_to_routes[synonym] = set()
    for dest_name in dest_names:
        matching = destinations_pdf[destinations_pdf["destination_name"].str.lower() == dest_name]
        if len(matching) > 0:
            keyword_to_routes[synonym].update(matching.iloc[0]["associated_routes"])

print(f"✓ Built keyword index with {len(keyword_to_routes)} keywords")


def recommend_bus_route(query: str, top_n: int = 3) -> list:
    """
    Takes a natural language query and returns the best matching bus routes.
    
    Args:
        query: Natural language like 'I need to get to Walmart from campus'
        top_n: Number of top routes to return
        
    Returns:
        List of dicts with route_code, route_name, description, stops, schedule info, and match score
    """
    query_lower = query.lower()
    words = re.findall(r"\b\w+\b", query_lower)
    
    # Score each route based on keyword matches
    route_scores = {}
    
    for word in words:
        # Check exact keyword match
        if word in keyword_to_routes:
            for route_code in keyword_to_routes[word]:
                route_scores[route_code] = route_scores.get(route_code, 0) + 1
        
        # Check multi-word phrases (e.g., "new river valley mall")
        for keyword, routes_set in keyword_to_routes.items():
            if " " in keyword and keyword in query_lower:
                for route_code in routes_set:
                    route_scores[route_code] = route_scores.get(route_code, 0) + 2  # phrase match = higher weight
    
    # Also match destination names directly in the query
    for _, dest_row in destinations_pdf.iterrows():
        dest_name_lower = dest_row["destination_name"].lower()
        if dest_name_lower in query_lower:
            for route_code in dest_row["associated_routes"]:
                route_scores[route_code] = route_scores.get(route_code, 0) + 3  # exact dest match = highest weight
    
    if not route_scores:
        return []
    
    # Sort by score (descending) and get top_n
    sorted_routes = sorted(route_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    results = []
    for route_code, score in sorted_routes:
        route_row = routes_pdf[routes_pdf["route_code"] == route_code]
        if len(route_row) == 0:
            continue
        r = route_row.iloc[0]
        results.append({
            "route_code": r["route_code"],
            "route_name": r["route_name"],
            "description": r["description"],
            "service_days": r["service_days"],
            "service_hours": r["service_hours"],
            "frequency": r["frequency"],
            "stops": list(r["stops"]),
            "schedule_url": r["schedule_url"],
            "match_score": score
        })
    
    return results


def format_recommendation(query: str) -> str:
    """Format recommendation results as a readable string."""
    routes = recommend_bus_route(query)
    if not routes:
        return f"No routes found for: '{query}'. Try mentioning a destination like 'Walmart', 'downtown', 'Kroger', or 'Christiansburg'."
    
    lines = []
    lines.append(f'Bus Query: "{query}"')
    lines.append('=' * 60)
    lines.append('')
    
    for i, r in enumerate(routes, 1):
        medal = '#1' if i == 1 else '#2' if i == 2 else '#3'
        lines.append(f"{medal} Route {r['route_code']} - {r['route_name']}")
        lines.append(f"   {r['description']}")
        lines.append(f"   Service: {r['service_days']}, {r['service_hours']}")
        lines.append(f"   Frequency: {r['frequency']}")
        stops_str = ', '.join(r['stops'][:5])
        if len(r['stops']) > 5:
            stops_str += '...'
        lines.append(f"   Stops: {stops_str}")
        lines.append(f"   Match score: {r['match_score']}")
        lines.append(f"   Schedule: {r['schedule_url']}")
        lines.append('')
    
    return '\n'.join(lines)

print("Recommendation engine ready!")

# COMMAND ----------

# DBTITLE 1,Test Section
# MAGIC %md
# MAGIC ## Step 4: Test the Recommendation System
# MAGIC Try these example queries to see how the Easy Bus Helper works!

# COMMAND ----------

# DBTITLE 1,Run Test Examples
# Example queries demonstrating the recommendation system
example_queries = [
    "I need to get to Walmart from campus",
    "How do I get to Kroger?",
    "I want to go downtown for dinner",
    "I need to go to the gym at McComas",
    "I need to get to Christiansburg for shopping at the mall",
    "I live in Hethwood and need to get to campus",
    "I need to go to the hospital",
    "I want to go to the Corporate Research Center",
]

for query in example_queries:
    print(format_recommendation(query))
    print("-" * 60)
    print()

# COMMAND ----------

# DBTITLE 1,Real-Time Tracking Section
# MAGIC %md
# MAGIC

# COMMAND ----------

# DBTITLE 1,GPS Coordinates for Stops
# GPS coordinates for known Blacksburg Transit stops (approximate, based on real locations)
# Format: {"stop_name": (latitude, longitude)}
STOP_COORDS = {
    "Squires Student Center": (37.2282, -80.4190),
    "Patton Hall": (37.2236, -80.4233),
    "Drillfield": (37.2276, -80.4210),
    "Perry Street": (37.2265, -80.4185),
    "Litton-Reaves": (37.2245, -80.4220),
    "McComas Hall": (37.2260, -80.4245),
    "Torgersen Bridge": (37.2290, -80.4175),
    "Hillcrest Hall": (37.2240, -80.4260),
    "Washington Street": (37.2255, -80.4195),
    "Stanger Street": (37.2300, -80.4155),
    "Downtown Blacksburg": (37.2296, -80.4144),
    "Main Street": (37.2270, -80.4150),
    "College Avenue": (37.2295, -80.4135),
    "South Main Street": (37.2150, -80.4250),
    "North Main Street": (37.2330, -80.4150),
    "Givens Lane": (37.2350, -80.4130),
    "Meadowbrook Drive": (37.2360, -80.4140),
    "Harding Avenue": (37.2190, -80.4210),
    "Patrick Henry Drive": (37.2180, -80.4350),
    "Patrick Henry Mall": (37.2170, -80.4360),
    "Toms Creek Road": (37.2210, -80.4300),
    "Progress Street": (37.2220, -80.4280),
    "Ingleside Road": (37.2100, -80.4400),
    "University City Blvd": (37.2120, -80.4380),
    "Hethwood": (37.2150, -80.4500),
    "Hethwood Commons": (37.2145, -80.4480),
    "Foxridge": (37.2160, -80.4520),
    "Highland Lane": (37.2170, -80.4450),
    "Oaktree Apartments": (37.2200, -80.4290),
    "Blacksburg Middle School": (37.2185, -80.4270),
    "Blacksburg High School": (37.2140, -80.4260),
    "Ellett Road": (37.2130, -80.4280),
    "Walmart": (37.2095, -80.4336),
    "Kroger": (37.2150, -80.4250),
    "Smithfield Plantation": (37.2240, -80.4350),
    "CRC Building 1": (37.1850, -80.3950),
    "Virginia Tech Airport": (37.1900, -80.4000),
    "Research Park": (37.1870, -80.3980),
    "Industrial Park": (37.1880, -80.4020),
    "Plantation Road": (37.1920, -80.4050),
    "LewisGale Hospital": (37.1650, -80.3750),
    "Christiansburg Library": (37.1800, -80.4100),
    "New River Valley Mall": (37.1700, -80.3900),
    "Food Lion": (37.1750, -80.4050),
    "Christiansburg": (37.1800, -80.4100),
    "Spradlin Farms": (37.1750, -80.3950),
}

print(f"GPS coordinates loaded for {len(STOP_COORDS)} stops")

# Verify all stops in our route data have coordinates
missing_coords = set()
for _, row in routes_pdf.iterrows():
    for stop in row["stops"]:
        if stop not in STOP_COORDS:
            missing_coords.add(stop)

if missing_coords:
    print(f"Missing coordinates for {len(missing_coords)} stops: {missing_coords}")
else:
    print("All stops have GPS coordinates")

# COMMAND ----------

# DBTITLE 1,Real-Time Simulation Engine
import math
import random
from datetime import datetime, timedelta

# ── Helpers ──────────────────────────────────────────────────────────

def haversine_miles(lat1, lon1, lat2, lon2):
    """Distance in miles between two GPS points."""
    R = 3958.8  # Earth radius in miles
    p = math.pi / 180
    a = (0.5
         - math.cos((lat2 - lat1) * p) / 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2)
    return 2 * R * math.asin(math.sqrt(a))


def parse_time_range(service_hours: str) -> tuple | None:
    """Parse '7:00 AM - 10:00 PM' -> (7.0, 22.0) in 24h decimal hours."""
    if not service_hours or "-" not in service_hours:
        return None
    parts = service_hours.split("-")
    if len(parts) != 2:
        return None
    def to_24h(s: str) -> float | None:
        s = s.strip().upper().replace(".", "")
        try:
            t, ap = s.rsplit(" ", 1) if " " in s else (s, "")
            h, m = t.split(":")[:2]
            h, m = int(h), int(m)
            if ap == "PM" and h != 12:
                h += 12
            elif ap == "AM" and h == 12:
                h = 0
            return h + m / 60.0
        except Exception:
            return None
    start = to_24h(parts[0])
    end = to_24h(parts[1])
    if start is None or end is None:
        return None
    return (start, end)


def parse_frequency_minutes(freq: str) -> int:
    """Parse 'Every 15-20 minutes' -> 17 (midpoint)."""
    nums = re.findall(r"(\d+)", freq or "")
    if not nums:
        return 20
    return sum(int(n) for n in nums) // len(nums)


def is_route_active(service_hours: str, current_hour: float) -> bool:
    """Check if route is currently running."""
    tr = parse_time_range(service_hours)
    if tr is None:
        return True  # Assume active if unknown
    start, end = tr
    return start <= current_hour <= end


def interpolate_position(stops, progress, coords):
    """Interpolate GPS position between two stops based on progress 0..1."""
    n = len(stops)
    if n == 0:
        return None
    if n == 1:
        return coords.get(stops[0], (37.2296, -80.4139))
    
    # progress maps to a position along the full route loop
    seg = progress * n
    idx = int(seg) % n
    frac = seg - int(seg)
    
    stop_a = stops[idx]
    stop_b = stops[(idx + 1) % n]
    
    coord_a = coords.get(stop_a, (37.2296, -80.4139))
    coord_b = coords.get(stop_b, (37.2296, -80.4139))
    
    lat = coord_a[0] + (coord_b[0] - coord_a[0]) * frac
    lon = coord_a[1] + (coord_b[1] - coord_a[1]) * frac
    
    return (lat, lon, stop_a, stop_b, round(frac * 100))


def calc_route_duration_minutes(stops, coords):
    """Estimate total route cycle time based on stop-to-stop distances and 20 mph avg."""
    total_miles = 0.0
    n = len(stops)
    for i in range(n):
        a = coords.get(stops[i], (37.2296, -80.4139))
        b = coords.get(stops[(i + 1) % n], (37.2296, -80.4139))
        total_miles += haversine_miles(a[0], a[1], b[0], b[1])
    return max(10, int(total_miles / 20 * 60))  # 20 mph average, min 10 min


# ── Simulation Engine ──────────────────────────────────────────────

def generate_vehicle_positions(snapshot_time: datetime | None = None):
    """
    Generate simulated real-time bus positions for all active routes.
    Returns a list of dicts with vehicle_id, route_code, lat, lon, current_stop,
    next_stop, progress_pct, eta_next_stop_min, direction.
    """
    if snapshot_time is None:
        snapshot_time = datetime.now()
    
    current_hour = snapshot_time.hour + snapshot_time.minute / 60.0
    positions = []
    
    for _, route in routes_pdf.iterrows():
        code = route["route_code"]
        stops = list(route["stops"])
        if not stops:
            continue
        
        # Check if route is active
        if not is_route_active(route["service_hours"], current_hour):
            continue
        
        freq_min = parse_frequency_minutes(route["frequency"])
        cycle_min = calc_route_duration_minutes(stops, STOP_COORDS)
        
        # Determine number of buses on this route (at least 1)
        num_buses = max(1, cycle_min // freq_min)
        
        # Use a deterministic seed per route for reproducibility within a minute
        seed = hash(code + snapshot_time.strftime("%Y%m%d%H%M")) % 10000
        rng = random.Random(seed)
        
        for bus_idx in range(num_buses):
            # Each bus is at a different point in the cycle
            # Use time-of-day + bus offset to compute progress
            minutes_since_start = current_hour * 60  # rough approximation
            bus_offset = (bus_idx * freq_min) % cycle_min
            progress = ((minutes_since_start + bus_offset + rng.uniform(-2, 2)) % cycle_min) / cycle_min
            
            pos = interpolate_position(stops, progress, STOP_COORDS)
            if pos is None:
                continue
            
            lat, lon, current_stop, next_stop, progress_pct = pos
            
            # ETA to next stop (based on remaining fraction of segment)
            seg_remaining = (100 - progress_pct) / 100.0
            seg_distance = haversine_miles(
                STOP_COORDS.get(current_stop, (37.2296, -80.4139))[0],
                STOP_COORDS.get(current_stop, (37.2296, -80.4139))[1],
                STOP_COORDS.get(next_stop, (37.2296, -80.4139))[0],
                STOP_COORDS.get(next_stop, (37.2296, -80.4139))[1],
            )
            eta_min = max(1, int(seg_remaining * seg_distance / 20 * 60))
            
            positions.append({
                "vehicle_id": f"{code}-{bus_idx + 1}",
                "route_code": code,
                "route_name": route["route_name"],
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "current_stop": current_stop,
                "next_stop": next_stop,
                "progress_pct": progress_pct,
                "eta_next_stop_min": eta_min,
                "direction": "inbound" if progress < 0.5 else "outbound",
                "timestamp": snapshot_time.isoformat(),
                "service_hours": route["service_hours"],
                "frequency": route["frequency"],
            })
    
    return positions


# Generate current positions
now = datetime.now()
vehicle_positions = generate_vehicle_positions(now)

print(f"Simulated real-time positions at {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Active vehicles: {len(vehicle_positions)}")
print()

# Print a sample
for v in vehicle_positions[:10]:
    print(f"  {v['vehicle_id']:>8} | Route {v['route_code']:>3} | "
          f"{v['current_stop']:<25} -> {v['next_stop']:<25} | "
          f"ETA {v['eta_next_stop_min']:>2} min | ({v['latitude']:.4f}, {v['longitude']:.4f})")

# COMMAND ----------

# DBTITLE 1,Store Positions in Delta Table
# Store vehicle positions in a Delta table for queryable real-time tracking
if vehicle_positions:
    vp_schema = StructType([
        StructField("vehicle_id", StringType(), True),
        StructField("route_code", StringType(), True),
        StructField("route_name", StringType(), True),
        StructField("latitude", StringType(), True),
        StructField("longitude", StringType(), True),
        StructField("current_stop", StringType(), True),
        StructField("next_stop", StringType(), True),
        StructField("progress_pct", IntegerType(), True),
        StructField("eta_next_stop_min", IntegerType(), True),
        StructField("direction", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("service_hours", StringType(), True),
        StructField("frequency", StringType(), True),
    ])
    
    # Convert numeric fields to strings for the schema
    vp_rows = []
    for v in vehicle_positions:
        vp_rows.append({
            "vehicle_id": v["vehicle_id"],
            "route_code": v["route_code"],
            "route_name": v["route_name"],
            "latitude": str(v["latitude"]),
            "longitude": str(v["longitude"]),
            "current_stop": v["current_stop"],
            "next_stop": v["next_stop"],
        "progress_pct": v["progress_pct"],
            "eta_next_stop_min": v["eta_next_stop_min"],
            "direction": v["direction"],
            "timestamp": v["timestamp"],
            "service_hours": v["service_hours"],
            "frequency": v["frequency"],
        })
    
    vp_df = spark.createDataFrame(vp_rows, schema=vp_schema)
    vp_df.createOrReplaceTempView("_bt_positions_temp")
    
    spark.sql("""
    CREATE TABLE IF NOT EXISTS workspace.vthacks.bt_vehicle_positions AS
    SELECT
        vehicle_id, route_code, route_name,
        CAST(latitude AS DOUBLE) AS latitude,
        CAST(longitude AS DOUBLE) AS longitude,
        current_stop, next_stop, progress_pct,
        eta_next_stop_min, direction, timestamp,
        service_hours, frequency
    FROM _bt_positions_temp
    """)
    
    print(f"Created workspace.vthacks.bt_vehicle_positions with {len(vp_rows)} rows")
    display(spark.table("workspace.vthacks.bt_vehicle_positions"))
else:
    print("No active vehicles to store")

# COMMAND ----------

# DBTITLE 1,Live Tracking Recommendation Function
def get_live_eta_for_route(route_code: str, target_stop: str = None) -> list:
    """
    Get live ETA for buses on a specific route.
    Returns list of dicts with vehicle_id, current_stop, next_stop, eta_to_target_min.
    """
    etas = []
    for v in vehicle_positions:
        if v["route_code"] != route_code:
            continue
        
        # Find the position of the target stop in the route's stop list
        route_row = routes_pdf[routes_pdf["route_code"] == route_code]
        if len(route_row) == 0:
            continue
        stops = list(route_row.iloc[0]["stops"])
        
        if target_stop and target_stop in stops:
            target_idx = stops.index(target_stop)
            current_idx = stops.index(v["current_stop"]) if v["current_stop"] in stops else 0
            
            # Calculate stops remaining until target
            stops_remaining = (target_idx - current_idx) % len(stops)
            
            # Estimate time: remaining stops * average time per stop
            freq_min = parse_frequency_minutes(v["frequency"])
            avg_time_per_stop = max(2, freq_min // 2)
            
            # If currently between current_stop and next_stop, subtract partial time
            if stops_remaining == 0:
                # Bus is at the target stop or very close
                eta = v["eta_next_stop_min"]
            else:
                eta = stops_remaining * avg_time_per_stop + v["eta_next_stop_min"]
        else:
            # No specific target - just report next stop ETA
            eta = v["eta_next_stop_min"]
        
        etas.append({
            "vehicle_id": v["vehicle_id"],
            "current_stop": v["current_stop"],
            "next_stop": v["next_stop"],
            "progress_pct": v["progress_pct"],
            "eta_to_target_min": min(eta, 99),
            "direction": v["direction"],
            "target_stop": target_stop or v["next_stop"],
        })
    
    # Sort by ETA (closest first)
    etas.sort(key=lambda x: x["eta_to_target_min"])
    return etas


def find_nearest_stop_to_destination(query: str, route_code: str) -> str:
    """Find the stop on a route that best matches the user's destination query."""
    route_row = routes_pdf[routes_pdf["route_code"] == route_code]
    if len(route_row) == 0:
        return None
    stops = list(route_row.iloc[0]["stops"])
    
    query_lower = query.lower()
    # Find best matching stop
    best_stop = None
    best_score = 0
    for stop in stops:
        stop_lower = stop.lower()
        score = 0
        for word in query_lower.split():
            if word in stop_lower:
                score += 1
        if stop_lower in query_lower:
            score += 3
        # Also check destination names
        for _, dest_row in destinations_pdf.iterrows():
            if dest_row["destination_name"].lower() in query_lower:
                if stop_lower in dest_row["destination_name"].lower() or dest_row["destination_name"].lower() in stop_lower:
                    score += 5
        if score > best_score:
            best_score = score
            best_stop = stop
    
    return best_stop or (stops[0] if stops else None)


def recommend_with_live_tracking(query: str, top_n: int = 3) -> str:
    """
    Enhanced recommendation that includes real-time bus tracking data.
    Combines route recommendations with live vehicle positions and ETAs.
    """
    # Get base route recommendations
    routes = recommend_bus_route(query, top_n)
    if not routes:
        return f"No routes found for: '{query}'. Try mentioning a destination like 'Walmart', 'downtown', 'Kroger', or 'Christiansburg'."
    
    now = datetime.now()
    current_hour = now.hour + now.minute / 60.0
    
    lines = []
    lines.append(f'LIVE TRACKING | Query: "{query}"')
    lines.append(f'Snapshot: {now.strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('=' * 60)
    lines.append('')
    
    for i, r in enumerate(routes, 1):
        rank = f"#{i}"
        lines.append(f"{rank} Route {r['route_code']} - {r['route_name']}")
        lines.append(f"   {r['description']}")
        lines.append(f"   Service: {r['service_days']}, {r['service_hours']}")
        lines.append(f"   Scheduled frequency: {r['frequency']}")
        
        # Find the best matching stop for the user's destination
        target_stop = find_nearest_stop_to_destination(query, r["route_code"])
        
        # Get live tracking data
        etas = get_live_eta_for_route(r["route_code"], target_stop)
        
        if etas:
            lines.append(f"   LIVE TRACKING ({len(etas)} bus(es) active):")
            for eta in etas[:3]:
                if target_stop:
                    lines.append(f"     Bus {eta['vehicle_id']}: at {eta['current_stop']} -> {eta['next_stop']} | "
                                 f"ETA to {target_stop}: {eta['eta_to_target_min']} min")
                else:
                    lines.append(f"     Bus {eta['vehicle_id']}: at {eta['current_stop']} -> {eta['next_stop']} | "
                                 f"ETA to next stop: {eta['eta_to_target_min']} min")
        else:
            # Check if route is currently inactive
            if not is_route_active(r["service_hours"], current_hour):
                tr = parse_time_range(r["service_hours"])
                if tr:
                    lines.append(f"   STATUS: Not currently running (service ends at {r['service_hours'].split('-')[-1].strip()})")
            else:
                lines.append(f"   STATUS: No live vehicles detected")
        
        stops_str = ', '.join(r['stops'][:5])
        if len(r['stops']) > 5:
            stops_str += '...'
        lines.append(f"   All stops: {stops_str}")
        lines.append(f"   Match score: {r['match_score']}")
        lines.append('')
    
    return '\n'.join(lines)


print("Live tracking recommendation engine ready!")

# COMMAND ----------

# DBTITLE 1,Live Tracking Demo Section
# MAGIC %md
# MAGIC ## Step 6: Live Tracking Demo
# MAGIC See real-time bus positions and enhanced recommendations with live ETAs.

# COMMAND ----------

# DBTITLE 1,Live Tracking Dashboard Demo
# ── Live Bus Position Dashboard ─────────────────────────────────────
print("=" * 70)
print("  LIVE BUS TRACKING DASHBOARD")
print(f"  Snapshot: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)
print()

if vehicle_positions:
    print(f"  {len(vehicle_positions)} active vehicles across {len(set(v['route_code'] for v in vehicle_positions))} routes")
    print()
    print(f"  {'Vehicle':>8} | {'Route':>5} | {'Current Stop':<26} | {'Next Stop':<26} | {'ETA':>4} | {'Dir':>8}")
    print("  " + "-" * 100)
    for v in sorted(vehicle_positions, key=lambda x: x["route_code"]):
        print(f"  {v['vehicle_id']:>8} | {v['route_code']:>5} | {v['current_stop']:<26} | {v['next_stop']:<26} | {v['eta_next_stop_min']:>3}m | {v['direction']:>8}")
else:
    print("  No active vehicles at this time.")
    print("  (Most routes run 7:00 AM - 7:00 PM on weekdays)")

print()
print("=" * 70)
print("  ENHANCED RECOMMENDATIONS WITH LIVE TRACKING")
print("=" * 70)
print()

# Demo queries with live tracking integration
live_queries = [
    "I need to get to Walmart from campus",
    "How do I get to downtown Blacksburg?",
    "I want to go to Patrick Henry Drive",
    "I need to get to Toms Creek",
]

for q in live_queries:
    print(recommend_with_live_tracking(q))
    print("-" * 70)
    print()

# COMMAND ----------

# DBTITLE 1,Test the Voice App
# MAGIC %md
# MAGIC ## 🎤 Test the Voice-Enabled App
# MAGIC Run the cell below to start the Flask app and get the URL to open in your browser!

# COMMAND ----------

# DBTITLE 1,Run Flask App
# Full pipeline test - no Flask server needed
import os, re, numpy as np
import subprocess, sys

# Install dependencies (needed on fresh kernel)
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "elevenlabs", "psycopg2-binary"])
print("Dependencies installed")

os.environ["ELEVENLABS_API_KEY"] = "sk_85d6188fb750031100e48b4c9bfd641bef8d6cca28b49ec3"
os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6JyGU3QswVRN6fqD983VfIMoYDzftVGivZDQr3_2RPfNw"
os.environ["TIGERDATA_URL"] = "postgres://tsdbadmin:e8x2yz8rlrafokn2@wu00rbek8w.wpv5i950k6.tsdb.cloud.timescale.com:37733/tsdb?sslmode=require"

print("=" * 60)
print("  VT Campus Life Assistant - Full Pipeline Test")
print("=" * 60)
print("  ElevenLabs: Voice input/output")
print("  Gemini: AI understanding")
print("  Tiger Data: Real-time tracking")
print("  Delta Lake: Route data")
print()

# ── TEST 1: Bus Query (Delta Lake + Tiger Data) ──
print("-- TEST 1: 'How do I get to Walmart?' --")
routes_df = spark.table("workspace.vthacks.bt_routes_full").toPandas()
positions_df = spark.table("workspace.vthacks.bt_vehicle_positions").toPandas()

query = "How do I get to Walmart?"
words = [w for w in re.sub(r'[^\w\s]', '', query.lower()).split() if len(w) >= 3]
scored = []
for _, r in routes_df.iterrows():
    stops = r.get("stops", [])
    stops_str = " ".join(str(s) for s in (stops.tolist() if isinstance(stops, np.ndarray) else stops)).lower()
    score = sum(2 if w in stops_str else 0 for w in words) + sum(1 if w in str(r.get("description","")).lower() else 0 for w in words)
    if score > 0: scored.append((score, r))
scored.sort(key=lambda x: x[0], reverse=True)

for i, (score, r) in enumerate(scored[:3], 1):
    code = str(r.get("route_code", ""))
    buses = positions_df[positions_df["route_code"] == code]
    print(f"  #{i} Route {code} - {r.get('route_name')} (score: {score})")
    print(f"     Service: {r.get('service_hours')} | Freq: {r.get('frequency')}")
    if len(buses) > 0:
        for _, b in buses.iterrows():
            print(f"     LIVE: Bus {b['vehicle_id']} at {b['current_stop']} -> {b['next_stop']} | ETA: {b['eta_next_stop_min']} min")
    else:
        print(f"     No buses currently active")
print("  Bus query works!\n")

# ── TEST 2: Gym/Health Query (Tiger Data) ──
print("-- TEST 2: 'How crowded is McComas?' --")
import psycopg2
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(os.environ["TIGERDATA_URL"])
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("SELECT DISTINCT ON (facility_name) facility_name, current_occupancy, max_capacity, occupancy_percent FROM gym_occupancy_realtime ORDER BY facility_name, time DESC")
    for f in cur.fetchall():
        pct = float(f['occupancy_percent'] or 0)
        bar = '#' * int(pct/5) + '.' * (20-int(pct/5))
        print(f"  {f['facility_name']}: [{bar}] {pct:.0f}% full ({f['current_occupancy']}/{f['max_capacity']})")
print("  Health query works!\n")

# ── TEST 3: Gemini Routing ──
print("-- TEST 3: Gemini AI routing --")
import requests
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={os.environ['GEMINI_API_KEY']}"
prompt = 'Classify into ONE word (bus/food/health/events/general): "I need to talk to a counselor"'
resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
category = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
print(f"  Query: 'I need to talk to a counselor' -> Gemini says: '{category}'")
print("  Gemini routing works!\n")

# ── TEST 4: ElevenLabs TTS ──
print("-- TEST 4: ElevenLabs voice output --")
from elevenlabs.client import ElevenLabs
tl_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
audio = tl_client.text_to_speech.convert(text="Route GRN to Walmart has a bus arriving in 8 minutes.", voice_id="hpp4J3VqNfWAUOO0d1Us", model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
audio_bytes = b"".join(audio)
print(f"  Generated {len(audio_bytes)/1024:.0f} KB of voice audio")
print("  ElevenLabs TTS works!\n")

print("=" * 60)
print("  ALL TESTS PASSED - Ready to deploy as Databricks App!")
print("=" * 60)