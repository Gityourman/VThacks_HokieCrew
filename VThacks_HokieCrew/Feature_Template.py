# Databricks notebook source
# DBTITLE 1,Feature Overview
# MAGIC %md
# MAGIC # 🎯 [YOUR FEATURE NAME] - VThacks Template
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC Describe what your feature does. Example:
# MAGIC * Food recommendations based on dietary restrictions and budget
# MAGIC * Health resource finder for physical and mental wellness
# MAGIC * Event and club discovery based on student interests
# MAGIC
# MAGIC ## Data Sources
# MAGIC List the websites/APIs you'll scrape:
# MAGIC * URL 1: Brief description
# MAGIC * URL 2: Brief description
# MAGIC
# MAGIC ## Tables to Create
# MAGIC * `workspace.vthacks.[your_table_1]` - Description
# MAGIC * `workspace.vthacks.[your_table_2]` - Description
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

# DBTITLE 1,Data Collection Section
# MAGIC %md
# MAGIC ## Step 1: Data Collection
# MAGIC Scrape your data sources and build structured data.

# COMMAND ----------

# DBTITLE 1,Scrape Data
import requests
from bs4 import BeautifulSoup
import json

# Replace with your actual URL
DATA_URL = "https://your-vt-data-source.edu"

# Fetch the page
response = requests.get(DATA_URL, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

print(f"Page fetched: {response.status_code}")
print(f"Page length: {len(response.text)} chars")

# TODO: Parse the HTML and extract relevant data
# Example: Find all relevant elements
items = soup.find_all("div", class_="your-target-class")

print(f"\nFound {len(items)} items")

# Build structured data (example)
data_rows = []
for item in items:
    # Extract fields from each item
    name = item.find("h2").get_text(strip=True) if item.find("h2") else "Unknown"
    description = item.find("p").get_text(strip=True) if item.find("p") else ""
    
    data_rows.append({
        "name": name,
        "description": description,
        # Add more fields as needed
    })

print(f"\n✓ Collected {len(data_rows)} data rows")
for row in data_rows[:5]:  # Preview first 5
    print(f"  - {row['name']}")

# COMMAND ----------

# DBTITLE 1,Delta Tables Section
# MAGIC %md
# MAGIC ## Step 2: Create Delta Lake Tables
# MAGIC Store your data in Unity Catalog Delta tables.

# COMMAND ----------

# DBTITLE 1,Create Delta Table
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# Define your schema (customize for your data)
data_schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
    # Add more fields as needed
])

# Add IDs to your data
for i, row in enumerate(data_rows, 1):
    row["id"] = i

# Create DataFrame
data_df = spark.createDataFrame(data_rows, schema=data_schema)

# Ensure catalog and schema exist
spark.sql("CREATE CATALOG IF NOT EXISTS workspace")
spark.sql("CREATE SCHEMA IF NOT EXISTS workspace.vthacks")

# Register as temp view
data_df.createOrReplaceTempView("_your_feature_temp")

# Create Delta table (replace 'your_table_name' with actual name)
spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.vthacks.your_table_name AS
SELECT *
FROM _your_feature_temp
""")

print(f"✓ Created workspace.vthacks.your_table_name with {len(data_rows)} rows")

# Verify by reading back
display(spark.table("workspace.vthacks.your_table_name"))

# COMMAND ----------

# DBTITLE 1,Recommendation Section
# MAGIC %md
# MAGIC ## Step 3: Recommendation Function
# MAGIC Build a function that takes a natural language query and returns recommendations.

# COMMAND ----------

# DBTITLE 1,Build Recommendation Function
# Load data from Delta table into pandas for fast lookup
import re

data_pdf = spark.table("workspace.vthacks.your_table_name").toPandas()

# Build keyword index
keyword_to_items = {}

for _, row in data_pdf.iterrows():
    item_id = row["id"]
    name = row["name"].lower()
    description = row["description"].lower()
    
    # Add name words as keywords
    for word in name.split():
        if word not in keyword_to_items:
            keyword_to_items[word] = set()
        keyword_to_items[word].add(item_id)
    
    # Add description words as keywords
    for word in description.split():
        word = word.strip(".,;:!?()[]")
        if len(word) > 3:
            if word not in keyword_to_items:
                keyword_to_items[word] = set()
            keyword_to_items[word].add(item_id)

def recommend(query: str) -> list:
    """
    Find items matching the natural language query.
    
    Args:
        query: Natural language query from student
    
    Returns:
        List of dicts with matched items, sorted by relevance
    """
    query_lower = query.lower()
    query_words = re.findall(r'\b\w+\b', query_lower)
    
    # Score items by keyword matches
    item_scores = {}
    for word in query_words:
        if word in keyword_to_items:
            for item_id in keyword_to_items[word]:
                item_scores[item_id] = item_scores.get(item_id, 0) + 1
    
    # If no matches, return empty list
    if not item_scores:
        return []
    
    # Sort by score
    ranked_ids = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Build result list
    results = []
    for item_id, score in ranked_ids[:5]:  # Top 5
        row = data_pdf[data_pdf["id"] == item_id].iloc[0]
        results.append({
            "id": item_id,
            "name": row["name"],
            "description": row["description"],
            "match_score": score
        })
    
    return results

print("✓ Recommendation function ready!")

# COMMAND ----------

# DBTITLE 1,Test Section
# MAGIC %md
# MAGIC ## Step 4: Test Your Function
# MAGIC Run example queries to verify your recommendation system works.

# COMMAND ----------

# DBTITLE 1,Test Examples
# Test your function with example queries
example_queries = [
    "your example query 1",
    "your example query 2",
    "your example query 3",
]

for query in example_queries:
    print(f"\nQuery: \"{query}\"")
    print("=" * 60)
    results = recommend(query)
    if results:
        for i, result in enumerate(results, 1):
            print(f"\n#{i} {result['name']}")
            print(f"   {result['description']}")
            print(f"   Match score: {result['match_score']}")
    else:
        print("  No matches found.")
    print()

print("\n✓ Testing complete! Your feature is ready to integrate into the app.")

# COMMAND ----------

