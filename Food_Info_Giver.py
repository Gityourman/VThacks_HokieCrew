# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Project Overview
# MAGIC %md
# MAGIC # 🍽️ VThacks Food Info-Giver
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC This notebook implements the **Food Info-Giver** — an AI-powered food recommendation system for Virginia Tech students.
# MAGIC
# MAGIC ### Features
# MAGIC * Natural language food recommendations based on dietary restrictions, preferences, and budget
# MAGIC * Real-time VT dining hall menus scraped from foodpro.students.vt.edu
# MAGIC * Dietary filtering (vegetarian, vegan, gluten-free, allergen-aware, halal)
# MAGIC * Local restaurant recommendations with budget levels ($, $$, $$$)
# MAGIC * 12 VT dining locations with breakfast, lunch, and dinner menus
# MAGIC
# MAGIC ### Data Sources
# MAGIC * VT Daily Menus: https://foodpro.students.vt.edu/menus/ (JSON API)
# MAGIC * VT Dining Plans: https://dining.vt.edu/plans_overview/find_your_plan.html
# MAGIC * Local restaurants (curated Blacksburg dataset)
# MAGIC
# MAGIC ### Delta Tables
# MAGIC * `workspace.default.dining_halls` — VT dining locations with hours and meal plan info
# MAGIC * `workspace.default.food_menus` — Daily menu items with dietary tags and allergens
# MAGIC * `workspace.default.restaurants` — Local restaurants with cuisine, budget, and dietary options
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,Install Dependencies
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
# MAGIC Scrape VT dining hall menus from the foodpro API and build a local restaurant dataset.
# MAGIC
# MAGIC ### API Endpoints Discovered:
# MAGIC * `https://foodpro.students.vt.edu/menus/API/Locations.aspx` — List of dining locations
# MAGIC * `https://foodpro.students.vt.edu/menus/API/MenuAtLocation.aspx?locationNum=X&dtdate=MM/DD/YYYY` — Menu for a location on a date
# MAGIC
# MAGIC ### Dietary Legend Codes:
# MAGIC * `WCVEG` / `vegan` — Vegan
# MAGIC * `WCVTN` / `vegetarian` — Vegetarian
# MAGIC * `WCHA` / `halal` — Halal
# MAGIC * `WCAL` / `alcohol` — Contains alcohol

# COMMAND ----------

# DBTITLE 1,Scrape VT Dining Locations
import requests
import json
from datetime import datetime

# ── VT Dining Menu API ──
BASE_API = "https://foodpro.students.vt.edu/menus/API"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://foodpro.students.vt.edu/menus/",
}

# Fetch all dining locations
resp = requests.get(f"{BASE_API}/Locations.aspx", headers=HEADERS, timeout=30)
resp.raise_for_status()
locations = resp.json()

print(f"✓ Fetched {len(locations)} dining locations:")
for loc in locations:
    print(f"  [{loc['locationNum']}] {loc['name']}")

# Build a lookup dict: locationNum -> name
LOC_MAP = {loc["locationNum"]: loc["name"] for loc in locations}

# COMMAND ----------

# DBTITLE 1,Fetch Menus for All Dining Halls
# Fetch today's menu for every dining location
today = datetime.now().strftime("%m/%d/%Y")

all_menu_items = []   # Flattened menu items for food_menus table
dining_hall_info = [] # Metadata for dining_halls table

# Known dining hall details (hours, description, meal plan acceptance)
# Source: https://dining.vt.edu/plans_overview/find_your_plan.html
DINING_HALL_DETAILS = {
    "15": {"description": "All-you-care-to-eat dining hall in Dietrick Hall. Largest dining hall on campus.",
           "hours": "7:00 AM - 9:00 PM", "meal_plan": "Major Flex Plan / Dining Plan",
           "address": "2133 Dietrick Hall, 1455 Washington St NW", "lat": 37.2275, "lon": -80.4250},
    "72": {"description": "A la carte dining in Dietrick Hall featuring branded concepts.",
           "hours": "7:00 AM - 10:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Dietrick Hall, 1455 Washington St NW", "lat": 37.2275, "lon": -80.4250},
    "01": {"description": "Dining at the Graduate Life Center featuring Ducky's.",
           "hours": "10:30 AM - 8:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Graduate Life Center, 1455 Washington St NW", "lat": 37.2260, "lon": -80.4260},
    "71": {"description": "DXpress convenience dining in Dietrick Hall.",
           "hours": "11:00 AM - 11:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Dietrick Hall, 1455 Washington St NW", "lat": 37.2275, "lon": -80.4250},
    "09": {"description": "Food court and Hokie Grill at Owens Hall with multiple stations.",
           "hours": "10:30 AM - 9:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Owens Hall, 460 Turner St NW", "lat": 37.2290, "lon": -80.4200},
    "07": {"description": "Xpress Lane Market — grab-and-go and convenience items.",
           "hours": "7:00 AM - 11:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Owens Hall, 460 Turner St NW", "lat": 37.2290, "lon": -80.4200},
    "06": {"description": "Perry Place at HITT Hall — made-to-order and featured concepts.",
           "hours": "10:30 AM - 8:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "HITT Hall, 460 Turner St NW", "lat": 37.2290, "lon": -80.4200},
    "18": {"description": "Squires Food Court with multiple quick-serve options.",
           "hours": "10:30 AM - 10:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Squires Student Center, 290 College Ave", "lat": 37.2290, "lon": -80.4175},
    "14": {"description": "Turner Place at Lavery Hall — a la carte with diverse cuisines.",
           "hours": "7:00 AM - 9:00 PM", "meal_plan": "Major Flex Plan / Dining Plan",
           "address": "Lavery Hall, 1455 Washington St NW", "lat": 37.2270, "lon": -80.4240},
    "19": {"description": "Viva Market at Johnston Student Center and Viva Too at Goodwin Hall.",
           "hours": "10:30 AM - 8:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Johnston Student Center, 280 Washington St", "lat": 37.2280, "lon": -80.4190},
    "16": {"description": "West End at Cochrane Hall — a la carte featured concepts.",
           "hours": "7:00 AM - 9:00 PM", "meal_plan": "Major Flex Plan / Dining Plan",
           "address": "Cochrane Hall, 480 Washington St", "lat": 37.2280, "lon": -80.4220},
    "39": {"description": "Owens Food Court with multiple dining stations.",
           "hours": "10:30 AM - 9:00 PM", "meal_plan": "Flex Plans / Dining Dollars",
           "address": "Owens Hall, 460 Turner St NW", "lat": 37.2290, "lon": -80.4200},
}

for loc in locations:
    loc_num = loc["locationNum"]
    loc_name = loc["name"]
    details = DINING_HALL_DETAILS.get(loc_num, {})

    # Build dining_halls row
    dining_hall_info.append({
        "location_num": loc_num,
        "name": loc_name,
        "description": details.get("description", "Virginia Tech dining location."),
        "hours": details.get("hours", "Hours vary"),
        "meal_plan": details.get("meal_plan", "Dining Dollars"),
        "address": details.get("address", "Virginia Tech campus"),
        "latitude": details.get("lat", 37.2280),
        "longitude": details.get("lon", -80.4200),
    })

    # Fetch menu for this location
    try:
        menu_resp = requests.get(
            f"{BASE_API}/MenuAtLocation.aspx",
            params={"locationNum": loc_num, "dtdate": today},
            headers=HEADERS,
            timeout=30,
        )
        menu_resp.raise_for_status()
        menu_data = menu_resp.json()

        item_count = 0
        for meal in menu_data.get("meals", []):
            meal_name = meal.get("mealName", "Unknown")
            for section in meal.get("sections", []):
                section_name = section.get("sectionName", "Unknown")
                for recipe in section.get("recipes", []):
                    legend_images = recipe.get("legendImages", [])
                    all_menu_items.append({
                        "recipe_id": recipe.get("recipeId", ""),
                        "name": recipe.get("name", ""),
                        "description": recipe.get("description", ""),
                        "meal": meal_name,
                        "station": section_name,
                        "location_num": loc_num,
                        "location_name": loc_name,
                        "is_vegetarian": "vegetarian" in legend_images,
                        "is_vegan": "vegan" in legend_images,
                        "is_halal": "halal" in legend_images,
                        "has_alcohol": "alcohol" in legend_images,
                        "allergens": recipe.get("allergens", ""),
                        "portion_size": str(recipe.get("portionSize", "")),
                        "portion_unit": recipe.get("portionUnit", ""),
                        "price": recipe.get("price", ""),
                        "menu_date": today,
                    })
                    item_count += 1

        print(f"  ✓ {loc_name}: {item_count} menu items")
    except Exception as e:
        print(f"  ✗ {loc_name}: {e}")

print(f"\n✓ Total: {len(all_menu_items)} menu items across {len(dining_hall_info)} dining halls")
print(f"✓ Vegetarian items: {sum(1 for i in all_menu_items if i['is_vegetarian'])}")
print(f"✓ Vegan items: {sum(1 for i in all_menu_items if i['is_vegan'])}")
print(f"✓ Halal items: {sum(1 for i in all_menu_items if i['is_halal'])}")
print(f"✓ Gluten-free items: {sum(1 for i in all_menu_items if 'Gluten' not in i['allergens'] and i['allergens'] != '')}")

# COMMAND ----------

# DBTITLE 1,Build Local Restaurant Dataset
# ── Local Restaurants in Blacksburg (curated dataset) ──
# Includes popular off-campus dining options with budget levels and dietary options
restaurants_data = [
    {"name": "The Cellar", "cuisine": "American", "budget": "$$", "address": "302 N Main St", "lat": 37.2302, "lon": -80.4146, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Burgers, pizzas, and craft beer in a cozy underground atmosphere. Student favorite."},
    {"name": "Boudreaux's Cajun Kitchen", "cuisine": "Cajun/Creole", "budget": "$$", "address": "105 Draper Rd NW", "lat": 37.2305, "lon": -80.4155, "vegetarian": True, "vegan": False, "gluten_free": False, "description": "Authentic Cajun and Creole dishes. Jambalaya, gumbo, po'boys."},
    {"name": "El Mariachi", "cuisine": "Mexican", "budget": "$$", "address": "403 N Main St", "lat": 37.2310, "lon": -80.4148, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Traditional Mexican cuisine with vegetarian and vegan options. Fajitas, tacos, burritos."},
    {"name": "Blacksburg Burger Co.", "cuisine": "American", "budget": "$$", "address": "202 N Main St", "lat": 37.2298, "lon": -80.4144, "vegetarian": True, "vegan": False, "gluten_free": True, "description": "Gourmet burgers with veggie options and gluten-free buns. Craft milkshakes."},
    {"name": "Gillie's", "cuisine": "Vegetarian/American", "budget": "$$", "address": "151 College Ave", "lat": 37.2290, "lon": -80.4160, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Vegetarian-friendly restaurant with many vegan options. Breakfast all day."},
    {"name": "The Underground", "cuisine": "American", "budget": "$$", "address": "301 N Main St", "lat": 37.2301, "lon": -80.4145, "vegetarian": True, "vegan": False, "gluten_free": False, "description": "Pizza, sandwiches, and salads. Popular study spot with coffee."},
    {"name": "Forte", "cuisine": "Italian", "budget": "$$", "address": "413 N Main St", "lat": 37.2312, "lon": -80.4149, "vegetarian": True, "vegan": False, "gluten_free": True, "description": "Italian cuisine with pasta, pizza, and gluten-free pasta options."},
    {"name": "Next Door Bake Shop", "cuisine": "Bakery/Cafe", "budget": "$", "address": "212 N Main St", "lat": 37.2298, "lon": -80.4145, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Bakery with vegan and gluten-free baked goods. Coffee and light bites."},
    {"name": "Souvlaki", "cuisine": "Greek/Mediterranean", "budget": "$$", "address": "124 N Main St", "lat": 37.2295, "lon": -80.4142, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Greek cuisine with gyros, falafel, hummus, and vegetarian platters."},
    {"name": "EasyChair Coffee Roasters", "cuisine": "Coffee/Cafe", "budget": "$", "address": "107 N Main St", "lat": 37.2293, "lon": -80.4140, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Specialty coffee roaster with pastries, vegan options, and study seating."},
    {"name": "Café Mochi", "cuisine": "Asian Fusion", "budget": "$$", "address": "460 N Main St", "lat": 37.2320, "lon": -80.4155, "vegetarian": True, "vegan": True, "gluten_free": False, "description": "Asian fusion with sushi, ramen, and vegetarian options. Boba tea."},
    {"name": "PK's Bar & Grill", "cuisine": "American", "budget": "$$", "address": "325 N Main St", "lat": 37.2303, "lon": -80.4147, "vegetarian": True, "vegan": False, "gluten_free": False, "description": "Classic college bar food with burgers, wings, and nachos. Vegetarian burgers available."},
    {"name": "Bento Bowl", "cuisine": "Japanese", "budget": "$$", "address": "140 University City Blvd", "lat": 37.2250, "lon": -80.4250, "vegetarian": True, "vegan": True, "gluten_free": False, "description": "Japanese rice bowls, sushi, and ramen. Tofu options available."},
    {"name": "Six Pence & Silver Spoon", "cuisine": "Tea Room", "budget": "$$", "address": "109 S Main St", "lat": 37.2280, "lon": -80.4135, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "British tea room with scones, sandwiches, and dietary accommodations."},
    {"name": "Cabo Fish Taco", "cuisine": "Mexican/Seafood", "budget": "$$", "address": "460 N Main St", "lat": 37.2320, "lon": -80.4155, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Baja-style fish tacos with vegetarian and vegan options. Fresh and casual."},
    {"name": "Mellow Mushroom", "cuisine": "Pizza", "budget": "$$", "address": "1001 University City Blvd", "lat": 37.2120, "lon": -80.4380, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Pizza chain with vegan cheese, gluten-free crust, and creative toppings."},
    {"name": "Waffle House", "cuisine": "American", "budget": "$", "address": "3025 N Main St", "lat": 37.2350, "lon": -80.4150, "vegetarian": True, "vegan": False, "gluten_free": False, "description": "24/7 diner with breakfast, burgers, and hash browns. Budget-friendly."},
    {"name": "Sharkey's", "cuisine": "American", "budget": "$$", "address": "101 Draper Rd NW", "lat": 37.2305, "lon": -80.4155, "vegetarian": True, "vegan": False, "gluten_free": False, "description": "Burgers, wings, and sandwiches. Popular sports bar with VT game day specials."},
    {"name": "Torcuato", "cuisine": "Argentine/Spanish", "budget": "$$$", "address": "122 N Main St", "lat": 37.2295, "lon": -80.4142, "vegetarian": True, "vegan": False, "gluten_free": True, "description": "Upscale Argentine and Spanish small plates. Great for date night."},
    {"name": "Pup's Cups", "cuisine": "Dessert", "budget": "$", "address": "200 N Main St", "lat": 37.2297, "lon": -80.4144, "vegetarian": True, "vegan": True, "gluten_free": True, "description": "Cupcakes and ice cream with vegan and gluten-free options. Student-budget friendly."},
]

print(f"✓ Built local restaurant dataset with {len(restaurants_data)} restaurants")
for r in restaurants_data:
    print(f"  {r['budget']} {r['name']} ({r['cuisine']}) — Veg:{r['vegetarian']} Vegan:{r['vegan']} GF:{r['gluten_free']}")

# COMMAND ----------

# DBTITLE 1,Delta Tables Section
# MAGIC %md
# MAGIC ## Step 2: Create Delta Lake Tables
# MAGIC Store dining halls, food menus, and restaurant data in Unity Catalog Delta tables.

# COMMAND ----------

# DBTITLE 1,Create dining_halls Delta Table
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, BooleanType, DoubleType

# ── Create dining_halls table in workspace.default (schema already exists) ──
dh_schema = StructType([
    StructField("location_num", StringType(), True),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("hours", StringType(), True),
    StructField("meal_plan", StringType(), True),
    StructField("address", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
])

dh_df = spark.createDataFrame(dining_hall_info, schema=dh_schema)
dh_df.write.mode("overwrite").saveAsTable("workspace.default.dining_halls")

print(f"✓ Created workspace.default.dining_halls with {len(dining_hall_info)} rows")
display(spark.table("workspace.default.dining_halls"))

# COMMAND ----------

# DBTITLE 1,Create food_menus Delta Table
# ── Create food_menus table ──
fm_schema = StructType([
    StructField("recipe_id", StringType(), True),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("meal", StringType(), True),
    StructField("station", StringType(), True),
    StructField("location_num", StringType(), True),
    StructField("location_name", StringType(), True),
    StructField("is_vegetarian", BooleanType(), True),
    StructField("is_vegan", BooleanType(), True),
    StructField("is_halal", BooleanType(), True),
    StructField("has_alcohol", BooleanType(), True),
    StructField("allergens", StringType(), True),
    StructField("portion_size", StringType(), True),
    StructField("portion_unit", StringType(), True),
    StructField("price", StringType(), True),
    StructField("menu_date", StringType(), True),
])

fm_df = spark.createDataFrame(all_menu_items, schema=fm_schema)
fm_df.createOrReplaceTempView("_food_menus_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.food_menus AS
SELECT * FROM _food_menus_temp
""")

print(f"✓ Created workspace.default.food_menus with {len(all_menu_items)} rows")

# Show a summary
print(f"\nMenu summary by location:")
spark.table("workspace.default.food_menus").groupBy("location_name").count().orderBy("count", ascending=False).show()

print("\nDietary breakdown:")
print(f"  Vegetarian: {spark.table('workspace.default.food_menus').filter('is_vegetarian').count()}")
print(f"  Vegan: {spark.table('workspace.default.food_menus').filter('is_vegan').count()}")
print(f"  Halal: {spark.table('workspace.default.food_menus').filter('is_halal').count()}")

# COMMAND ----------

# DBTITLE 1,Create restaurants Delta Table
# ── Create restaurants table ──
# Rename lat/lon keys to match schema field names
restaurants_data_fixed = []
for r in restaurants_data:
    r_fixed = dict(r)
    r_fixed["latitude"] = r_fixed.pop("lat")
    r_fixed["longitude"] = r_fixed.pop("lon")
    restaurants_data_fixed.append(r_fixed)

rest_schema = StructType([
    StructField("name", StringType(), True),
    StructField("cuisine", StringType(), True),
    StructField("budget", StringType(), True),
    StructField("address", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("vegetarian", BooleanType(), True),
    StructField("vegan", BooleanType(), True),
    StructField("gluten_free", BooleanType(), True),
    StructField("description", StringType(), True),
])

rest_df = spark.createDataFrame(restaurants_data_fixed, schema=rest_schema)
rest_df.createOrReplaceTempView("_restaurants_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.restaurants AS
SELECT * FROM _restaurants_temp
""")

print(f"✓ Created workspace.default.restaurants with {len(restaurants_data)} rows")
display(spark.table("workspace.default.restaurants"))

# COMMAND ----------

# DBTITLE 1,Recommendation Section
# MAGIC %md
# MAGIC ## Step 3: Recommendation Engine
# MAGIC Natural language food recommendation system that filters by dietary restrictions, preferences, and budget.
# MAGIC
# MAGIC ### Function Signatures for App Integration:
# MAGIC * `recommend_food(query: str, dietary_restrictions: list = None, budget: str = None) -> list[dict]`
# MAGIC * `recommend_dining_hall(query: str, dietary_restrictions: list = None) -> list[dict]`
# MAGIC * `recommend_restaurant(query: str, dietary_restrictions: list = None, budget: str = None) -> list[dict]`

# COMMAND ----------

# DBTITLE 1,Recommendation Helpers
import re

# Load data from Delta tables into pandas for fast lookup
menus_pdf = spark.table("workspace.default.food_menus").toPandas()
halls_pdf = spark.table("workspace.default.dining_halls").toPandas()
rest_pdf = spark.table("workspace.default.restaurants").toPandas()

# Dietary restriction synonyms
DIETARY_SYNONYMS = {
    "vegetarian": ["vegetarian", "veggie", "veg", "meatless", "no meat"],
    "vegan": ["vegan", "plant-based", "plant based", "no animal", "no dairy"],
    "gluten-free": ["gluten-free", "gluten free", "gf", "celiac", "no gluten", "wheat-free"],
    "halal": ["halal"],
    "nut-free": ["nut-free", "nut free", "peanut-free", "tree nut free"],
    "dairy-free": ["dairy-free", "dairy free", "lactose", "no milk"],
    "soy-free": ["soy-free", "soy free"],
    "egg-free": ["egg-free", "egg free"],
}

# Cuisine / food preference keywords
CUISINE_KEYWORDS = {
    "pizza": ["pizza", "flatbread"],
    "mexican": ["mexican", "taco", "burrito", "salsa", "quesadilla", "fajita"],
    "italian": ["italian", "pasta", "lasagna", "risotto"],
    "asian": ["asian", "ramen", "sushi", "bento", "stir fry", "pan asia", "rice bowl"],
    "greek": ["greek", "gyro", "falafel", "hummus", "mediterranean"],
    "burgers": ["burger", "patty melt"],
    "breakfast": ["breakfast", "pancake", "waffle", "omelet", "bacon"],
    "salad": ["salad", "caesar", "greens"],
    "soup": ["soup", "chili", "broth"],
    "dessert": ["dessert", "cake", "cookie", "ice cream", "brownie", "pastry", "sweet"],
    "coffee": ["coffee", "espresso", "latte"],
    "cajun": ["cajun", "creole", "jambalaya", "gumbo", "po boy"],
    "grill": ["grill", "grilled", "bbq", "barbecue"],
}

def parse_dietary_restrictions(query: str) -> list:
    """Extract dietary restrictions from a natural language query."""
    query_lower = query.lower()
    found = []
    for diet, synonyms in DIETARY_SYNONYMS.items():
        if any(syn in query_lower for syn in synonyms):
            found.append(diet)
    return found

def parse_cuisine_preferences(query: str) -> list:
    """Extract cuisine/food type preferences from a natural language query."""
    query_lower = query.lower()
    found = []
    for cuisine, keywords in CUISINE_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            found.append(cuisine)
    return found

def parse_budget(query: str) -> str:
    """Extract budget level from a natural language query."""
    query_lower = query.lower()
    if any(w in query_lower for w in ["cheap", "budget", "affordable", "cheap eats"]):
        return "$"
    elif any(w in query_lower for w in ["expensive", "fancy", "upscale", "date night"]):
        return "$$$"
    elif any(w in query_lower for w in ["moderate", "mid-range"]):
        return "$$"
    return None

def filter_menu_by_dietary(menus_df, restrictions: list):
    """Filter menu items by dietary restrictions."""
    filtered = menus_df.copy()
    for restriction in restrictions:
        if restriction == "vegetarian":
            filtered = filtered[filtered["is_vegetarian"] == True]
        elif restriction == "vegan":
            filtered = filtered[filtered["is_vegan"] == True]
        elif restriction == "halal":
            filtered = filtered[filtered["is_halal"] == True]
        elif restriction == "gluten-free":
            filtered = filtered[~filtered["allergens"].str.contains("Gluten", case=False, na=False)]
        elif restriction == "nut-free":
            filtered = filtered[~filtered["allergens"].str.contains("Nut|Peanut|Tree Nut", case=False, na=False, regex=True)]
        elif restriction == "dairy-free":
            filtered = filtered[~filtered["allergens"].str.contains("Milk", case=False, na=False)]
        elif restriction == "soy-free":
            filtered = filtered[~filtered["allergens"].str.contains("Soy", case=False, na=False)]
        elif restriction == "egg-free":
            filtered = filtered[~filtered["allergens"].str.contains("Egg", case=False, na=False)]
    return filtered

def filter_restaurants_by_dietary(rest_df, restrictions: list):
    """Filter restaurants by dietary restrictions."""
    filtered = rest_df.copy()
    for restriction in restrictions:
        if restriction == "vegetarian":
            filtered = filtered[filtered["vegetarian"] == True]
        elif restriction == "vegan":
            filtered = filtered[filtered["vegan"] == True]
        elif restriction == "gluten-free":
            filtered = filtered[filtered["gluten_free"] == True]
    return filtered

print("Helpers loaded: dietary parsers, cuisine detectors, budget parser")

# COMMAND ----------

# DBTITLE 1,Build Recommendation Functions
def recommend_dining_hall(query: str, dietary_restrictions: list = None) -> list:
    """
    Find dining hall menu items matching the query and dietary restrictions.
    
    Args:
        query: Natural language query from student
        dietary_restrictions: List of restrictions (vegetarian, vegan, gluten-free, etc.)
    
    Returns:
        List of dicts with matching menu items, sorted by relevance
    """
    restrictions = dietary_restrictions or parse_dietary_restrictions(query)
    cuisines = parse_cuisine_preferences(query)
    
    # Filter by dietary restrictions
    filtered = filter_menu_by_dietary(menus_pdf, restrictions)
    
    if len(filtered) == 0:
        return []
    
    # Score items by keyword matches
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Build cuisine keyword set
    cuisine_words = set()
    for c in cuisines:
        cuisine_words.update(CUISINE_KEYWORDS.get(c, []))
    
    item_scores = {}
    for idx, row in filtered.iterrows():
        score = 0
        name_lower = row["name"].lower()
        desc_lower = row["description"].lower()
        station_lower = row["station"].lower()
        
        # Direct word match
        for word in query_words:
            if len(word) > 2 and word in name_lower:
                score += 3
            elif len(word) > 2 and word in desc_lower:
                score += 1
            elif len(word) > 2 and word in station_lower:
                score += 2
        
        # Cuisine match
        for cword in cuisine_words:
            if cword in name_lower or cword in station_lower:
                score += 5
        
        if score > 0:
            item_scores[idx] = score
    
    # If no keyword matches but we have dietary restrictions, return filtered items
    if not item_scores and restrictions:
        for idx in list(filtered.index)[:10]:
            item_scores[idx] = 1
    
    # Sort by score
    ranked = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
    
    results = []
    for idx, score in ranked[:10]:
        row = filtered.loc[idx]
        results.append({
            "name": row["name"],
            "location": row["location_name"],
            "meal": row["meal"],
            "station": row["station"],
            "description": row["description"],
            "is_vegetarian": bool(row["is_vegetarian"]),
            "is_vegan": bool(row["is_vegan"]),
            "is_halal": bool(row["is_halal"]),
            "allergens": row["allergens"],
            "match_score": score,
            "source": "dining_hall",
        })
    
    return results


def recommend_restaurant(query: str, dietary_restrictions: list = None, budget: str = None) -> list:
    """
    Find local restaurants matching the query, dietary restrictions, and budget.
    
    Args:
        query: Natural language query from student
        dietary_restrictions: List of restrictions
        budget: Budget level ($, $$, or $$$)
    
    Returns:
        List of dicts with matching restaurants, sorted by relevance
    """
    restrictions = dietary_restrictions or parse_dietary_restrictions(query)
    cuisines = parse_cuisine_preferences(query)
    budget_level = budget or parse_budget(query)
    
    # Filter by dietary restrictions
    filtered = filter_restaurants_by_dietary(rest_pdf, restrictions)
    
    # Filter by budget
    if budget_level:
        filtered = filtered[filtered["budget"] == budget_level]
    
    if len(filtered) == 0:
        return []
    
    # Score restaurants by keyword matches
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    results = []
    for _, row in filtered.iterrows():
        score = 0
        name_lower = row["name"].lower()
        desc_lower = row["description"].lower()
        cuisine_lower = row["cuisine"].lower()
        
        for word in query_words:
            if len(word) > 2:
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1
                if word in cuisine_lower:
                    score += 5
        
        for c in cuisines:
            for kw in CUISINE_KEYWORDS.get(c, []):
                if kw in cuisine_lower or kw in desc_lower:
                    score += 5
        
        results.append({
            "name": row["name"],
            "cuisine": row["cuisine"],
            "budget": row["budget"],
            "description": row["description"],
            "address": row["address"],
            "vegetarian": bool(row["vegetarian"]),
            "vegan": bool(row["vegan"]),
            "gluten_free": bool(row["gluten_free"]),
            "match_score": score,
            "source": "restaurant",
        })
    
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:10]


def recommend_food(query: str, dietary_restrictions: list = None, budget: str = None) -> list:
    """
    Main entry point: Find food recommendations matching the query.
    
    Searches both VT dining halls and local restaurants. Returns combined results.
    
    Args:
        query: Natural language query from student
        dietary_restrictions: List of restrictions (vegetarian, vegan, gluten-free, etc.)
        budget: Budget level for restaurants ($, $$, $$$)
    
    Returns:
        List of dicts with matching food options, sorted by relevance
    
    Example queries:
        "I want vegan food"
        "Where can I get pizza?"
        "I need gluten-free options for dinner"
        "I want Mexican food that's vegetarian"
        "I'm on a budget and want something cheap"
    """
    restrictions = dietary_restrictions or parse_dietary_restrictions(query)
    
    # Get dining hall recommendations
    dining_results = recommend_dining_hall(query, restrictions)
    
    # Get restaurant recommendations
    restaurant_results = recommend_restaurant(query, restrictions, budget)
    
    # Combine and sort by match score
    all_results = dining_results + restaurant_results
    all_results.sort(key=lambda x: x["match_score"], reverse=True)
    
    return all_results


print("Recommendation functions ready!")
print(f"  - {len(menus_pdf)} menu items across {menus_pdf['location_name'].nunique()} dining halls")
print(f"  - {len(rest_pdf)} local restaurants")
print(f"  - Dietary filters: {list(DIETARY_SYNONYMS.keys())}")
print(f"  - Cuisine detectors: {list(CUISINE_KEYWORDS.keys())}")

# COMMAND ----------

# DBTITLE 1,Test Section
# MAGIC %md
# MAGIC ## Step 4: Test the Recommendation System
# MAGIC Run example queries to verify the Food Info-Giver works!

# COMMAND ----------

# DBTITLE 1,Run Test Examples
# Example queries demonstrating the food recommendation system
example_queries = [
    "I want vegan food",
    "Where can I get pizza?",
    "I need gluten-free options for dinner",
    "I want Mexican food that's vegetarian",
    "I'm on a budget and want something cheap",
    "I want breakfast",
    "I need halal food",
    "I want Italian pasta",
]

for query in example_queries:
    print(f'\nFood Query: "{query}"')
    print("=" * 70)
    
    results = recommend_food(query)
    
    if results:
        for i, result in enumerate(results[:5], 1):
            source_tag = "dining hall" if result["source"] == "dining_hall" else "restaurant"
            print(f"\n  #{i} {result['name']} [{source_tag}]")
            if result["source"] == "dining_hall":
                print(f"     Location: {result['location']} | Meal: {result['meal']} | Station: {result['station']}")
                print(f"     Description: {result['description']}")
                tags = []
                if result.get("is_vegetarian"): tags.append("vegetarian")
                if result.get("is_vegan"): tags.append("vegan")
                if result.get("is_halal"): tags.append("halal")
                if result.get("allergens"): tags.append(f"allergens: {result['allergens']}")
                if tags: print(f"     Tags: {', '.join(tags)}")
            else:
                print(f"     Cuisine: {result['cuisine']} | Budget: {result['budget']}")
                print(f"     Description: {result['description']}")
                tags = []
                if result.get("vegetarian"): tags.append("vegetarian")
                if result.get("vegan"): tags.append("vegan")
                if result.get("gluten_free"): tags.append("gluten-free")
                if tags: print(f"     Tags: {', '.join(tags)}")
            print(f"     Match score: {result['match_score']}")
    else:
        print("  No matches found.")
    print("\n" + "-" * 70)

print("\nTesting complete! Food Info-Giver is ready to integrate into the app.")

# COMMAND ----------

# DBTITLE 1,ACTION: Grant Julian table permissions
# MAGIC %sql
# MAGIC -- ACTION NEEDED: Grant Julian access so he can integrate this into the app!
# MAGIC GRANT SELECT ON TABLE workspace.default.dining_halls TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.restaurants TO `julianmiller@vt.edu`;