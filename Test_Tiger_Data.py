# Databricks notebook source
# DBTITLE 1,Tiger Data Integration Test
# MAGIC %md
# MAGIC # 🐅 Tiger Data Integration Test
# MAGIC
# MAGIC This notebook tests the Tiger Data (Timescale PostgreSQL) integration for real-time bus tracking and gym occupancy.
# MAGIC
# MAGIC **What Tiger Data Does:**
# MAGIC * Real-time bus GPS positions (updated every 10 seconds)
# MAGIC * Gym occupancy tracking (updated every minute)
# MAGIC * Time-series queries ("Show me last 5 minutes", "Average ETA this week")
# MAGIC * Performance monitoring
# MAGIC
# MAGIC **Prize:** Best Use of Tiger Data

# COMMAND ----------

# DBTITLE 1,Test Connection
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Connection string from app.yaml
TIGERDATA_URL = "postgres://tsdbadmin:e8x2yz8rlrafokn2@wu00rbek8w.wpv5i950k6.tsdb.cloud.timescale.com:37733/tsdb?sslmode=require"

try:
    conn = psycopg2.connect(TIGERDATA_URL)
    print("✅ Successfully connected to Tiger Data!")
    
    # Get database version
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"\n📈 Database: {version}\n")
    
    # Check if TimescaleDB extension is available
    with conn.cursor() as cur:
        cur.execute("""
            SELECT installed_version 
            FROM pg_available_extensions 
            WHERE name = 'timescaledb'
        """)
        result = cur.fetchone()
        if result and result[0]:
            print(f"✅ TimescaleDB extension: v{result[0]}")
        else:
            print("⚠️ TimescaleDB not detected (might not be needed)")
            
except Exception as e:
    print(f"❌ Connection failed: {str(e)}")
    conn = None

# COMMAND ----------

# DBTITLE 1,Create Hypertables
# Create the three hypertables for time-series data

if conn:
    try:
        with conn.cursor() as cur:
            # Table 1: Real-time bus positions
            print("🚌 Creating bus_positions_realtime table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus_positions_realtime (
                    time TIMESTAMPTZ NOT NULL,
                    vehicle_id TEXT NOT NULL,
                    route_code TEXT NOT NULL,
                    route_name TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    current_stop TEXT,
                    next_stop TEXT,
                    eta_minutes INTEGER,
                    speed_mph DOUBLE PRECISION
                )
            """)
            
            # Convert to hypertable (skip if already exists)
            try:
                cur.execute("""
                    SELECT create_hypertable('bus_positions_realtime', 'time',
                                           if_not_exists => TRUE)
                """)
                print("  ✅ Converted to hypertable")
            except Exception as e:
                if "already a hypertable" in str(e).lower():
                    print("  ✅ Already a hypertable")
                else:
                    print(f"  ⚠️ Hypertable creation: {str(e)}")
            
            # Table 2: Gym occupancy tracking
            print("\n🏋️ Creating gym_occupancy_realtime table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gym_occupancy_realtime (
                    time TIMESTAMPTZ NOT NULL,
                    facility_name TEXT NOT NULL,
                    current_occupancy INTEGER,
                    max_capacity INTEGER,
                    occupancy_percent DOUBLE PRECISION
                )
            """)
            
            try:
                cur.execute("""
                    SELECT create_hypertable('gym_occupancy_realtime', 'time',
                                           if_not_exists => TRUE)
                """)
                print("  ✅ Converted to hypertable")
            except Exception as e:
                if "already a hypertable" in str(e).lower():
                    print("  ✅ Already a hypertable")
                else:
                    print(f"  ⚠️ Hypertable creation: {str(e)}")
            
            # Table 3: Query performance tracking
            print("\n📊 Creating query_performance table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_performance (
                    time TIMESTAMPTZ NOT NULL,
                    query_type TEXT NOT NULL,
                    response_time_ms INTEGER,
                    ai_service TEXT,
                    success BOOLEAN
                )
            """)
            
            try:
                cur.execute("""
                    SELECT create_hypertable('query_performance', 'time',
                                           if_not_exists => TRUE)
                """)
                print("  ✅ Converted to hypertable")
            except Exception as e:
                if "already a hypertable" in str(e).lower():
                    print("  ✅ Already a hypertable")
                else:
                    print(f"  ⚠️ Hypertable creation: {str(e)}")
            
            conn.commit()
            print("\n✅ All tables created successfully!")
            
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
else:
    print("❌ No connection available")

# COMMAND ----------

# DBTITLE 1,Populate Sample Bus Data
# Insert sample bus position data for demo
import time
from datetime import datetime

if conn:
    try:
        # Simulate 20 bus position updates over "time"
        sample_routes = [
            {"id": "GRN-1", "code": "GRN", "name": "Explorer Green", "lat": 37.2296, "lon": -80.4139, "stop": "Squires Student Center", "next": "Downtown Blacksburg", "eta": 8},
            {"id": "BLU-1", "code": "BLU", "name": "Explorer Blue", "lat": 37.2250, "lon": -80.4200, "stop": "Patrick Henry Mall", "next": "Walmart", "eta": 12},
            {"id": "HWC-1", "code": "HWC", "name": "Hethwood Combined", "lat": 37.2100, "lon": -80.4300, "stop": "Hethwood Commons", "next": "Squires Student Center", "eta": 15},
            {"id": "TCP-1", "code": "TCP", "name": "Toms Creek Progress", "lat": 37.2180, "lon": -80.4250, "stop": "Toms Creek Road", "next": "Progress Street", "eta": 6},
        ]
        
        inserted_count = 0
        
        with conn.cursor() as cur:
            for i in range(20):
                for route in sample_routes:
                    # Simulate movement
                    lat = route["lat"] + (i * 0.0005)
                    lon = route["lon"] + (i * 0.0005)
                    eta = max(1, route["eta"] - i // 5)
                    speed = 15.0 + (i % 10)
                    
                    cur.execute("""
                        INSERT INTO bus_positions_realtime 
                        (time, vehicle_id, route_code, route_name, latitude, longitude,
                         current_stop, next_stop, eta_minutes, speed_mph)
                        VALUES (NOW() - INTERVAL '%s seconds', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (i * 10, route["id"], route["code"], route["name"], lat, lon,
                          route["stop"], route["next"], eta, speed))
                    inserted_count += 1
            
            conn.commit()
        
        print(f"✅ Inserted {inserted_count} bus position records")
        print("   (Simulating 20 updates x 4 buses = 80 data points over 200 seconds)")
        
        # Query to verify
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT vehicle_id) as unique_vehicles,
                    MIN(time) as oldest_record,
                    MAX(time) as newest_record
                FROM bus_positions_realtime
            """)
            stats = cur.fetchone()
            
        print(f"\n📊 Database Stats:")
        print(f"   Total records: {stats['total_records']}")
        print(f"   Unique vehicles: {stats['unique_vehicles']}")
        print(f"   Oldest: {stats['oldest_record']}")
        print(f"   Newest: {stats['newest_record']}")
        
    except Exception as e:
        print(f"❌ Error inserting data: {str(e)}")
else:
    print("❌ No connection available")

# COMMAND ----------

# DBTITLE 1,Test Time-Series Queries
# Test time-series queries

if conn:
    try:
        print("🔍 Testing time-series queries...\n")
        
        # Query 1: Get all positions from last 2 minutes
        print("1️⃣ Recent positions (last 2 minutes):")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT vehicle_id, route_code, current_stop, next_stop, eta_minutes,
                       EXTRACT(EPOCH FROM (NOW() - time)) as seconds_ago
                FROM bus_positions_realtime
                WHERE time >= NOW() - INTERVAL '2 minutes'
                ORDER BY time DESC
                LIMIT 10
            """)
            results = cur.fetchall()
            
        for r in results:
            print(f"   {r['vehicle_id']:>6} ({r['route_code']}) - {r['current_stop'][:20]:20} -> {r['next_stop'][:20]:20} | ETA: {r['eta_minutes']}min | {int(r['seconds_ago'])}s ago")
        
        # Query 2: Average ETA by route
        print("\n2️⃣ Average ETA by route:")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    route_code,
                    route_name,
                    AVG(eta_minutes) as avg_eta,
                    COUNT(*) as data_points
                FROM bus_positions_realtime
                GROUP BY route_code, route_name
                ORDER BY route_code
            """)
            results = cur.fetchall()
            
        for r in results:
            print(f"   {r['route_code']:>5} - {r['route_name'][:25]:25} | Avg ETA: {r['avg_eta']:.1f} min | Data: {r['data_points']} points")
        
        # Query 3: Latest position per vehicle
        print("\n3️⃣ Latest position for each vehicle:")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (vehicle_id)
                    vehicle_id,
                    route_code,
                    current_stop,
                    eta_minutes,
                    time
                FROM bus_positions_realtime
                ORDER BY vehicle_id, time DESC
            """)
            results = cur.fetchall()
            
        for r in results:
            print(f"   {r['vehicle_id']:>6} - Currently at {r['current_stop'][:30]:30} | {r['time']}")
        
        print("\n✅ All queries executed successfully!")
        
    except Exception as e:
        print(f"❌ Error querying data: {str(e)}")
else:
    print("❌ No connection available")

# COMMAND ----------

# DBTITLE 1,Populate Gym Occupancy Data
# Insert sample gym occupancy data

if conn:
    try:
        facilities = [
            {"name": "McComas Hall", "capacity": 300},
            {"name": "War Memorial Gym", "capacity": 150},
        ]
        
        inserted_count = 0
        
        with conn.cursor() as cur:
            # Simulate hourly occupancy for last 24 hours
            for hour in range(24):
                for facility in facilities:
                    # Simulate realistic occupancy patterns
                    # Peak: 5pm-7pm, Low: 2am-6am
                    if 17 <= hour <= 19:  # Peak evening
                        occupancy = int(facility["capacity"] * (0.7 + (hour - 17) * 0.1))
                    elif 12 <= hour <= 14:  # Lunch rush
                        occupancy = int(facility["capacity"] * 0.6)
                    elif 2 <= hour <= 6:  # Early morning
                        occupancy = int(facility["capacity"] * 0.2)
                    else:
                        occupancy = int(facility["capacity"] * 0.4)
                    
                    occupancy_pct = (occupancy / facility["capacity"]) * 100
                    
                    cur.execute("""
                        INSERT INTO gym_occupancy_realtime
                        (time, facility_name, current_occupancy, max_capacity, occupancy_percent)
                        VALUES (NOW() - INTERVAL '%s hours', %s, %s, %s, %s)
                    """, (24 - hour, facility["name"], occupancy, facility["capacity"], occupancy_pct))
                    inserted_count += 1
            
            conn.commit()
        
        print(f"✅ Inserted {inserted_count} gym occupancy records")
        print("   (24 hours x 2 facilities = 48 data points)")
        
        # Query patterns
        print("\n🏋️ Gym Occupancy Patterns:\n")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    facility_name,
                    EXTRACT(HOUR FROM time) as hour,
                    AVG(occupancy_percent) as avg_occupancy
                FROM gym_occupancy_realtime
                WHERE facility_name = 'McComas Hall'
                GROUP BY facility_name, EXTRACT(HOUR FROM time)
                ORDER BY hour
                LIMIT 12
            """)
            results = cur.fetchall()
            
        print("McComas Hall - Occupancy by Hour:")
        for r in results:
            hour = int(r['hour'])
            pct = r['avg_occupancy']
            bar = '█' * int(pct / 5)
            print(f"   {hour:2d}:00 | {bar:20} {pct:.1f}%")
        
    except Exception as e:
        print(f"❌ Error inserting gym data: {str(e)}")
else:
    print("❌ No connection available")

# COMMAND ----------

# DBTITLE 1,Demo: Real-Time Queries
# Demo the kind of queries you'll use in the app

if conn:
    print("🎯 DEMO: Real-Time Queries for Campus Assistant\n")
    print("="*70)
    
    # Use case 1: "Where is the GRN bus right now?"
    print("\n🚌 Student asks: 'Where is the GRN bus right now?'\n")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM bus_positions_realtime
                WHERE route_code = 'GRN'
                ORDER BY time DESC
                LIMIT 1
            """)
            result = cur.fetchone()
            
        if result:
            print(f"Response: The GRN bus is currently at {result['current_stop']}.")
            print(f"          It will reach {result['next_stop']} in about {result['eta_minutes']} minutes.")
            print(f"          (Last updated: {result['time']})")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Use case 2: "When should I go to the gym?"
    print("\n\n🏋️ Student asks: 'When is McComas least crowded?'\n")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    EXTRACT(HOUR FROM time) as hour,
                    AVG(occupancy_percent) as avg_occupancy
                FROM gym_occupancy_realtime
                WHERE facility_name = 'McComas Hall'
                GROUP BY EXTRACT(HOUR FROM time)
                ORDER BY avg_occupancy ASC
                LIMIT 3
            """)
            results = cur.fetchall()
            
        print("Response: Based on the last 24 hours, McComas is least crowded:")
        for i, r in enumerate(results, 1):
            hour = int(r['hour'])
            am_pm = 'AM' if hour < 12 else 'PM'
            display_hour = hour if hour <= 12 else hour - 12
            if display_hour == 0:
                display_hour = 12
            print(f"          {i}. Around {display_hour}:00 {am_pm} (avg {r['avg_occupancy']:.1f}% full)")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    # Use case 3: "How long does GRN usually take to reach Walmart?"
    print("\n\n📊 Student asks: 'How long does GRN usually take?'\n")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    AVG(eta_minutes) as avg_eta,
                    MIN(eta_minutes) as min_eta,
                    MAX(eta_minutes) as max_eta,
                    COUNT(*) as samples
                FROM bus_positions_realtime
                WHERE route_code = 'GRN'
            """)
            result = cur.fetchone()
            
        if result:
            print(f"Response: Based on {result['samples']} recent data points:")
            print(f"          GRN typically takes {result['avg_eta']:.1f} minutes")
            print(f"          (Range: {result['min_eta']}-{result['max_eta']} minutes)")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "="*70)
    print("✅ Tiger Data enables real-time, data-driven responses!")
    
else:
    print("❌ No connection available")

# COMMAND ----------

# DBTITLE 1,Summary
# MAGIC %md
# MAGIC ## ✅ Tiger Data Integration Complete!
# MAGIC
# MAGIC ### What We Built:
# MAGIC
# MAGIC 1. **3 Hypertables** (time-series optimized tables)
# MAGIC    * `bus_positions_realtime` - Real-time GPS tracking
# MAGIC    * `gym_occupancy_realtime` - Facility usage patterns
# MAGIC    * `query_performance` - System monitoring
# MAGIC
# MAGIC 2. **Sample Data**
# MAGIC    * 80+ bus position records (4 buses x 20 updates)
# MAGIC    * 48 gym occupancy records (2 facilities x 24 hours)
# MAGIC    * Ready for time-series queries
# MAGIC
# MAGIC 3. **Real-Time Queries**
# MAGIC    * "Where is bus X right now?" - Sub-second response
# MAGIC    * "When is gym least crowded?" - Pattern analysis
# MAGIC    * "How long does route take?" - Historical averages
# MAGIC
# MAGIC ### Why This Wins Tiger Data Prize:
# MAGIC
# MAGIC ✅ **Perfect use case**: Campus assistant NEEDS real-time data  
# MAGIC ✅ **Time-series queries**: ETAs, occupancy patterns, performance  
# MAGIC ✅ **Proper architecture**: Tiger Data (real-time) + Delta Lake (historical)  
# MAGIC ✅ **Actually useful**: Real students would use this  
# MAGIC
# MAGIC ### Next Steps:
# MAGIC
# MAGIC 1. Test these queries from `app.py`
# MAGIC 2. Add to your demo presentation
# MAGIC 3. Mention multi-database architecture to judges
# MAGIC 4. Win 3 prizes! (🎧 ElevenLabs + 🤖 Gemini + 🐅 Tiger Data)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **Connection Info (already in app.yaml):**
# MAGIC ```
# MAGIC Host: wu00rbek8w.wpv5i950k6.tsdb.cloud.timescale.com
# MAGIC Port: 37733
# MAGIC Database: tsdb
# MAGIC ```

# COMMAND ----------

