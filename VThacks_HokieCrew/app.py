"""VThacks Campus Life Intelligence Hub - Databricks App

Deloitte × Databricks Challenge
Multi-AI Architecture:
- ElevenLabs: Voice input/output
- Gemini: AI understanding
- Tiger Data: Real-time tracking
- Databricks: Data platform
"""

import os
import base64
import json
import time
from flask import Flask, render_template_string, request, jsonify
import pandas as pd


def load_table(table_name):
    """Read Unity Catalog through a SQL warehouse.
    Uses the Databricks SDK WorkspaceClient which auto-discovers auth:
    - Databricks Apps: OAuth token from the app's service principal
    - Render with DATABRICKS_TOKEN: PAT auth
    - Render with DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET: OAuth M2M
    """
    import re
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){2}", table_name):
        raise ValueError("Expected a catalog.schema.table identifier")
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        raise RuntimeError("Configure DATABRICKS_WAREHOUSE_ID for the app")
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    identifier = ".".join(f"`{part}`" for part in table_name.split("."))
    stmt = w.statement_execution.execute_statement(
        statement=f"SELECT * FROM {identifier}",
        warehouse_id=warehouse_id,
    )
    # Poll for result (warehouse may need to auto-start from STOPPED)
    for _ in range(90):  # 90 x 2s = 180s max wait
        result = w.statement_execution.get_statement(stmt.statement_id)
        state = result.status.state
        state_name = state.name if hasattr(state, 'name') else str(state)
        if state_name == "SUCCEEDED":
            break
        elif state_name in ("FAILED", "CANCELED"):
            raise RuntimeError(f"SQL query failed: {result.status.error}")
        time.sleep(2)
    else:
        raise RuntimeError("SQL query timed out after 180s")
    # Convert to pandas DataFrame
    columns = [c.name for c in result.manifest.schema.columns]
    col_types = [c.type_name.name if hasattr(c.type_name, 'name') else str(c.type_name).upper() for c in result.manifest.schema.columns]
    data = result.result.data_array if result.result and result.result.data_array else []
    rows = [list(row) for row in data]
    df = pd.DataFrame(rows, columns=columns)
    # Statement execution API returns all values as strings; convert back to native types
    for i, col in enumerate(columns):
        tname = col_types[i]
        if tname == "BOOLEAN":
            df[col] = df[col].map(lambda v: True if str(v).lower() == "true" else (False if str(v).lower() == "false" else None))
        elif tname in ("INT", "BIGINT", "SMALLINT", "TINYINT", "INTEGER", "LONG"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif tname in ("FLOAT", "DOUBLE", "DECIMAL", "REAL"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def filter_dietary(frame, restrictions, menu=False):
    """Only claim a dietary match when the source has an explicit true flag."""
    for restriction in restrictions:
        column = ("is_" if menu else "") + restriction.replace("-", "_")
        if column not in frame.columns:
            return frame.iloc[0:0]
        frame = frame[frame[column].eq(True).fillna(False)]
    return frame


def optional_number(value, integer=False):
    """Keep missing/invalid telemetry missing instead of reporting a zero ETA."""
    import math
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return int(number) if integer else number
    except (ValueError, TypeError, OverflowError):
        return None

# Initialize Flask app
app = Flask(__name__)

# ============================================================================
# DATABRICKS TABLE ACCESS (works on both Databricks Apps and Render)
# ============================================================================


# ============================================================================
# FEATURE IMPORTS
# ============================================================================
# These functions will be imported from your feature notebooks once they're ready.
# For now, we'll define stub functions that you'll replace with actual imports.

# Feature 1: Bus Helper - queries Delta Lake + Tiger Data
def recommend_bus_route(query: str) -> str:
    """
    Get bus route recommendations using:
    - Delta Lake: Route schedules, stops, descriptions (historical/reference data)
    - Tiger Data: Real-time bus positions, ETAs, historical averages (time-series)
    """
    import time as _time
    start = _time.time()
    
    try:
        # Delta Lake: Get routes and vehicle positions
        routes_df = load_table("workspace.vthacks.bt_routes_full")
        positions_df = load_table("workspace.vthacks.bt_vehicle_positions")
        
        # Tiger Data: Push current positions to time-series DB
        if tigerdata_conn:
            for _, v in positions_df.iterrows():
                store_bus_position_realtime(
                    vehicle_id=str(v.get("vehicle_id", "")),
                    route_code=str(v.get("route_code", "")),
                    route_name=str(v.get("route_name", "")),
                    lat=optional_number(v.get("latitude")),
                    lon=optional_number(v.get("longitude")),
                    current_stop=str(v.get("current_stop", "")),
                    next_stop=str(v.get("next_stop", "")),
                    eta_min=optional_number(v.get("eta_next_stop_min"), integer=True),
                    speed=0.0
                )
        
        # Match routes to query (keyword-based scoring with punctuation handling)
        import re
        import numpy as np
        query_clean = re.sub(r'[^\w\s]', '', query.lower())
        words = [w for w in query_clean.split() if len(w) >= 3]
        scored = []
        for _, r in routes_df.iterrows():
            stops = r.get("stops", [])
            if isinstance(stops, np.ndarray):
                stops_str = " ".join(str(s) for s in stops.tolist()).lower()
            elif isinstance(stops, list):
                stops_str = " ".join(str(s) for s in stops).lower()
            else:
                stops_str = str(stops).lower()
            desc = str(r.get("description", "")).lower()
            name = str(r.get("route_name", "")).lower()
            score = 0
            for word in words:
                if word in stops_str:
                    score += 2
                if word in desc:
                    score += 1
                if word in name:
                    score += 1
            if score > 0:
                scored.append((score, r))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        top_routes = scored[:3]
        
        if not top_routes:
            top_routes = [(0, r) for _, r in routes_df.head(3).iterrows()]
        
        # Build response with Delta Lake data + Tiger Data real-time
        lines = []
        lines.append(f'Bus Recommendations for: "{query}"')
        lines.append('=' * 60)
        lines.append('')
        
        for i, (score, r) in enumerate(top_routes, 1):
            code = str(r.get("route_code", ""))
            name = str(r.get("route_name", ""))
            desc = str(r.get("description", ""))
            service = str(r.get("service_hours", ""))
            freq = str(r.get("frequency", ""))
            stops = r.get("stops", [])
            if isinstance(stops, np.ndarray):
                stops_list = stops.tolist()
            elif isinstance(stops, list):
                stops_list = stops
            else:
                import ast
                try:
                    stops_list = ast.literal_eval(str(stops))
                except:
                    stops_list = str(stops).split(",")
            if not isinstance(stops_list, (list, tuple)):
                stops_list = [] if stops_list is None else [stops_list]
            stops_str = ", ".join(str(s) for s in stops_list[:5]) if stops_list else "N/A"
            
            lines.append(f'#{i} Route {code} - {name}')
            lines.append(f'   {desc}')
            lines.append(f'   Service: {service} | Frequency: {freq}')
            lines.append(f'   Key stops: {stops_str}')
            
            # Tiger Data: Get real-time positions for this route
            route_buses = positions_df[positions_df["route_code"] == code]
            if len(route_buses) > 0:
                lines.append(f'   LIVE ({len(route_buses)} bus(es) active):')
                for _, bus in route_buses.iterrows():
                    bus_id = str(bus.get("vehicle_id", ""))
                    curr = str(bus.get("current_stop", ""))
                    nxt = str(bus.get("next_stop", ""))
                    eta = optional_number(bus.get("eta_next_stop_min"), integer=True)
                    eta_text = f'{eta} min' if eta is not None else 'unavailable'
                    lines.append(f'     Bus {bus_id}: at {curr} -> {nxt} | ETA: {eta_text}')
                
                # Tiger Data: Get historical average ETA
                if tigerdata_conn:
                    for _, bus in route_buses.head(2).iterrows():
                        avg_eta = get_average_eta_for_route(code, str(bus.get("next_stop", "")), hours_back=24)
                        if avg_eta:
                            lines.append(f'     Historical avg to {bus.get("next_stop", "")}: {avg_eta:.1f} min (last 24h)')
            else:
                lines.append(f'   No buses currently active (check service hours)')
            lines.append('')
        
        response = "\n".join(lines)
        
        # Tiger Data: Track query performance
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("bus", elapsed_ms, "delta+tigerdata", True)
        
        return response
        
    except Exception as e:
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("bus", elapsed_ms, "delta+tigerdata", False)
        raise RuntimeError("Campus data lookup failed") from e

# Feature 2: Food Info-Giver - queries Delta Lake tables from teammate notebook
def recommend_food(query: str) -> str:
    """
    Get food recommendations using Delta Lake tables:
    - workspace.default.food_menus (1417 items across 7 dining halls)
    - workspace.default.dining_halls (12 locations)
    - workspace.default.restaurants (20 local restaurants)
    """
    import time as _time
    start = _time.time()
    
    try:
        import re
        menus_pdf = load_table("workspace.default.food_menus")
        rest_pdf = load_table("workspace.default.restaurants")
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        # Detect dietary restrictions
        dietary_keywords = {
            'vegetarian': ['vegetarian', 'veggie', 'veg', 'meatless'],
            'vegan': ['vegan', 'plant-based', 'plant based'],
            'gluten-free': ['gluten-free', 'gluten free', 'gf', 'celiac'],
            'halal': ['halal'],
        }
        restrictions = []
        for diet, keywords in dietary_keywords.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', query_lower) for kw in keywords):
                restrictions.append(diet)
        
        # Detect budget
        budget = None
        if any(w in query_lower for w in ['cheap', 'budget', 'affordable', 'inexpensive']):
            budget = '$'
        elif any(w in query_lower for w in ['expensive', 'fancy', 'nice']):
            budget = '$$$'
        
        lines = []
        lines.append(f'Food Recommendations for: "{query}"')
        lines.append('=' * 60)
        if restrictions:
            lines.append(f'Dietary filters: {", ".join(restrictions)}')
        lines.append('')
        
        # ── Search dining hall menus ──
        filtered = filter_dietary(menus_pdf, restrictions, menu=True)
        
        if len(filtered) > 0:
            # Score by keyword matches
            scored_items = []
            for idx, row in filtered.iterrows():
                item_text = f"{row.get('name', '')} {row.get('description', '')} {row.get('station', '')}".lower()
                score = sum(1 for w in query_words if w in item_text and len(w) > 2)
                scored_items.append((score, row))
            scored_items.sort(key=lambda x: x[0], reverse=True)
            
            lines.append(f'Dining Hall Options ({len(filtered)} items match):')
            for i, (score, row) in enumerate(scored_items[:5], 1):
                name = str(row.get('name', ''))
                location = str(row.get('location_name', row.get('location', '')))
                meal = str(row.get('meal', ''))
                station = str(row.get('station', ''))
                lines.append(f'  #{i} {name}')
                lines.append(f'     {location} | {meal} | {station}')
            lines.append('')
        
        # ── Search restaurants ──
        rest_filtered = filter_dietary(rest_pdf, restrictions)
        if budget and 'budget' in rest_filtered.columns:
            rest_filtered = rest_filtered[rest_filtered['budget'] == budget]
        
        if len(rest_filtered) > 0:
            scored_rest = []
            for idx, row in rest_filtered.iterrows():
                item_text = f"{row.get('name', '')} {row.get('cuisine', '')} {row.get('description', '')}".lower()
                score = sum(1 for w in query_words if w in item_text and len(w) > 2)
                scored_rest.append((score, row))
            scored_rest.sort(key=lambda x: x[0], reverse=True)
            
            lines.append(f'Restaurant Options ({len(rest_filtered)} match):')
            for i, (score, row) in enumerate(scored_rest[:5], 1):
                name = str(row.get('name', ''))
                cuisine = str(row.get('cuisine', ''))
                budget_val = str(row.get('budget', ''))
                desc = str(row.get('description', ''))[:60]
                lines.append(f'  #{i} {name} ({cuisine}) {budget_val}')
                lines.append(f'     {desc}')
            lines.append('')
        
        if filtered.empty and rest_filtered.empty:
            lines.append('No verified dietary matches available. Confirm dietary needs with the dining provider.')
        if len(lines) <= 3:
            lines.append('No specific matches found. Try: "vegan food", "pizza", "gluten-free options"')
        
        response = '\n'.join(lines)
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("food", elapsed_ms, "delta", True)
        return response
        
    except Exception as e:
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("food", elapsed_ms, "delta", False)
        raise RuntimeError("Campus data lookup failed") from e

# Feature 3: Health Helper - queries Tiger Data for gym occupancy + Delta for resources
def find_health_resources(query: str) -> str:
    """
    Find health resources using:
    - Tiger Data: Real-time gym occupancy, historical patterns (time-series)
    - Delta Lake: Health resources, facility info (when teammate notebook ready)
    """
    import time as _time
    start = _time.time()
    
    query_lower = query.lower()
    lines = []
    lines.append(f'Health & Wellness for: "{query}"')
    lines.append('=' * 60)
    lines.append('')
    
    # GYM OCCUPANCY from Tiger Data
    if any(w in query_lower for w in ["gym", "mccomas", "workout", "fitness", "crowd", "busy", "occupancy", "war memorial"]):
        if tigerdata_conn:
            lines.append('Gym Occupancy (Tiger Data real-time):')
            lines.append('')
            
            with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (facility_name)
                        facility_name, current_occupancy, max_capacity, occupancy_percent, time
                    FROM gym_occupancy_realtime
                    ORDER BY facility_name, time DESC
                """)
                facilities = cur.fetchall()
            
            if facilities:
                for f in facilities:
                    pct = float(f['occupancy_percent'] or 0)
                    bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
                    lines.append(f"  {f['facility_name']}")
                    lines.append(f"  [{bar}] {pct:.0f}% full ({f['current_occupancy']}/{f['max_capacity']})")
                    
                    # Get pattern: least crowded times
                    with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT 
                                EXTRACT(HOUR FROM time) as hour,
                                AVG(occupancy_percent) as avg_pct
                            FROM gym_occupancy_realtime
                            WHERE facility_name = %s
                            GROUP BY EXTRACT(HOUR FROM time)
                            ORDER BY avg_pct ASC
                            LIMIT 3
                        """, (f['facility_name'],))
                        best_times = cur.fetchall()
                    
                    if best_times:
                        times_str = ", ".join(
                            f"{int(t['hour'])}:00 ({float(t['avg_pct']):.0f}%)" 
                            for t in best_times
                        )
                        lines.append(f"  Least crowded: {times_str}")
                    lines.append('')
            else:
                lines.append('  No occupancy data yet. Run Test_Tiger_Data notebook to populate.')
                lines.append('')
        else:
            lines.append('  Tiger Data not connected. Gym occupancy unavailable.')
            lines.append('')
    
    # HEALTH RESOURCES from Delta Lake (teammate Health_Helper notebook)
    if any(w in query_lower for w in ["counsel", "mental", "therapy", "wellness", "health", "sick", "medical", "doctor", "schiffert", "stress", "anxious", "depress", "flu", "vaccine", "prescription", "crisis"]):
        try:
            import re
            health_pdf = load_table("workspace.default.health_resources")
            query_words = set(re.findall(r'\b\w+\b', query_lower))
            
            scored = []
            for _, row in health_pdf.iterrows():
                text = f"{row.get('name', '')} {row.get('description', '')} {row.get('keywords', '')}".lower()
                score = sum(1 for w in query_words if w in text and len(w) > 2)
                if score > 0:
                    scored.append((score, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            
            if scored:
                lines.append('Health Resources:')
                for i, (score, row) in enumerate(scored[:5], 1):
                    name = str(row.get('name', ''))
                    cat = str(row.get('category', ''))
                    desc = str(row.get('description', ''))[:80]
                    lines.append(f'  #{i} {name} [{cat}]')
                    lines.append(f'     {desc}')
                lines.append('')
            else:
                # Fallback: show all resources
                lines.append('Health Resources (showing all):')
                for i, (_, row) in enumerate(health_pdf.iterrows(), 1):
                    if i > 5: break
                    name = str(row.get('name', ''))
                    cat = str(row.get('category', ''))
                    lines.append(f'  #{i} {name} [{cat}]')
                lines.append('')
        except Exception:
            # Fallback to basic info if Delta tables unavailable
            lines.append('Mental Health: Cook Counseling Center (540) 231-6557')
            lines.append('Medical: Schiffert Health Center (540) 231-6444')
            lines.append('')
    
    if len(lines) <= 3:
        lines.append('I can help with:')
        lines.append('  Gym occupancy - "How crowded is McComas?"')
        lines.append('  Mental health - "I need to talk to a counselor"')
        lines.append('  Medical - "Where is Schiffert Health Center?"')
    
    response = "\n".join(lines)
    
    # Track performance
    elapsed_ms = int((_time.time() - start) * 1000)
    track_query_performance("health", elapsed_ms, "tigerdata", True)
    
    return response

# Feature 4: Interest & Identity - queries Delta Lake tables from teammate notebook
def find_events_and_clubs(query: str) -> str:
    """
    Find campus events, clubs, and cultural centers using Delta Lake tables:
    - workspace.default.ii_campus_events (20 events)
    - workspace.default.ii_student_clubs (25 clubs)
    - workspace.default.ii_cultural_centers (12 cultural centers)
    """
    import time as _time
    start = _time.time()
    
    try:
        import re
        events_pdf = load_table("workspace.default.ii_campus_events")
        clubs_pdf = load_table("workspace.default.ii_student_clubs")
        centers_pdf = load_table("workspace.default.ii_cultural_centers")
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        lines = []
        lines.append(f'Campus Life for: "{query}"')
        lines.append('=' * 60)
        lines.append('')
        
        # ── Search events ──
        scored_events = []
        for _, row in events_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')} {row.get('category', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_events.append((score, row))
        scored_events.sort(key=lambda x: x[0], reverse=True)
        
        if scored_events and scored_events[0][0] > 0:
            lines.append(f'Events in the dataset ({len(scored_events)} total; check dates):')
            for i, (score, row) in enumerate(scored_events[:4], 1):
                name = str(row.get('name', ''))
                category = str(row.get('category', ''))
                date = str(row.get('date', ''))
                time_val = str(row.get('time', ''))
                location = str(row.get('location', ''))
                lines.append(f'  #{i} {name} [{category}]')
                lines.append(f'     {date} at {time_val} - {location}')
            lines.append('')
        
        # ── Search clubs ──
        scored_clubs = []
        for _, row in clubs_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')} {row.get('category', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_clubs.append((score, row))
        scored_clubs.sort(key=lambda x: x[0], reverse=True)
        
        if scored_clubs and scored_clubs[0][0] > 0:
            lines.append(f'Student Clubs ({len(scored_clubs)} total):')
            for i, (score, row) in enumerate(scored_clubs[:4], 1):
                name = str(row.get('name', ''))
                category = str(row.get('category', ''))
                desc = str(row.get('description', ''))[:60]
                lines.append(f'  #{i} {name} [{category}]')
                lines.append(f'     {desc}')
            lines.append('')
        
        # ── Search cultural centers ──
        scored_centers = []
        for _, row in centers_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_centers.append((score, row))
        scored_centers.sort(key=lambda x: x[0], reverse=True)
        
        if scored_centers and scored_centers[0][0] > 0:
            lines.append('Cultural & Community Centers:')
            for i, (score, row) in enumerate(scored_centers[:3], 1):
                name = str(row.get('name', ''))
                location = str(row.get('location', ''))
                lines.append(f'  #{i} {name} - {location}')
            lines.append('')
        
        if len(lines) <= 3:
            lines.append('Try: "dance events", "cultural clubs", "Asian culture", "volunteer opportunities"')
        
        response = '\n'.join(lines)
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("events", elapsed_ms, "delta", True)
        return response
        
    except Exception as e:
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("events", elapsed_ms, "delta", False)
        raise RuntimeError("Campus data lookup failed") from e

# Feature 5: Professional Helper - queries Delta Lake tables from teammate notebook
def find_professional_resources(query: str) -> str:
    """
    Find research opportunities and career resources using Delta Lake tables:
    - workspace.default.research_opportunities (46 opportunities)
    - workspace.default.career_resources (21 resources)
    - workspace.default.career_events (17 events)
    - workspace.default.career_pathways (12 pathways)
    """
    import time as _time
    start = _time.time()
    
    try:
        import re
        research_pdf = load_table("workspace.default.research_opportunities")
        resources_pdf = load_table("workspace.default.career_resources")
        events_pdf = load_table("workspace.default.career_events")
        pathways_pdf = load_table("workspace.default.career_pathways")
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        lines = []
        lines.append(f'Professional Resources for: "{query}"')
        lines.append('=' * 60)
        lines.append('')
        
        # ── Research opportunities ──
        scored_research = []
        for _, row in research_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')} {row.get('field', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_research.append((score, row))
        scored_research.sort(key=lambda x: x[0], reverse=True)
        
        if scored_research and scored_research[0][0] > 0:
            lines.append(f'Research Opportunities ({len(scored_research)} total):')
            for i, (score, row) in enumerate(scored_research[:4], 1):
                name = str(row.get('name', ''))
                field = str(row.get('field', ''))
                cat = str(row.get('category', ''))
                lines.append(f'  #{i} {name} [{cat}]')
                lines.append(f'     Field: {field}')
            lines.append('')
        
        # ── Career resources ──
        scored_resources = []
        for _, row in resources_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')} {row.get('category', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_resources.append((score, row))
        scored_resources.sort(key=lambda x: x[0], reverse=True)
        
        if scored_resources and scored_resources[0][0] > 0:
            lines.append(f'Career Resources ({len(scored_resources)} total):')
            for i, (score, row) in enumerate(scored_resources[:4], 1):
                name = str(row.get('name', ''))
                cat = str(row.get('category', ''))
                desc = str(row.get('description', ''))[:60]
                lines.append(f'  #{i} {name} [{cat}]')
                lines.append(f'     {desc}')
            lines.append('')
        
        # ── Career events ──
        scored_events = []
        for _, row in events_pdf.iterrows():
            text = f"{row.get('name', '')} {row.get('description', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_events.append((score, row))
        scored_events.sort(key=lambda x: x[0], reverse=True)
        
        if scored_events and scored_events[0][0] > 0:
            lines.append(f'Career Events ({len(scored_events)} total):')
            for i, (score, row) in enumerate(scored_events[:3], 1):
                name = str(row.get('name', ''))
                date = str(row.get('date_info', ''))
                lines.append(f'  #{i} {name}')
                lines.append(f'     {date}')
            lines.append('')
        
        # ── Career pathways ──
        scored_pathways = []
        for _, row in pathways_pdf.iterrows():
            text = f"{row.get('pathway', '')} {row.get('description', '')}".lower()
            score = sum(1 for w in query_words if w in text and len(w) > 2)
            scored_pathways.append((score, row))
        scored_pathways.sort(key=lambda x: x[0], reverse=True)
        
        if scored_pathways and scored_pathways[0][0] > 0:
            lines.append(f'Career Pathways:')
            for i, (score, row) in enumerate(scored_pathways[:3], 1):
                pathway = str(row.get('pathway', ''))
                lines.append(f'  #{i} {pathway}')
            lines.append('')
        
        if len(lines) <= 3:
            lines.append('Try: "research in biology", "resume help", "career fair", "internship opportunities"')
        
        response = '\n'.join(lines)
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("professional", elapsed_ms, "delta", True)
        return response
        
    except Exception as e:
        elapsed_ms = int((_time.time() - start) * 1000)
        track_query_performance("professional", elapsed_ms, "delta", False)
        raise RuntimeError("Campus data lookup failed") from e

# ============================================================================
# ELEVENLABS VOICE INTEGRATION
# ============================================================================

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    print("⚠️ ElevenLabs not installed. Run: pip install elevenlabs")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from datetime import datetime, timedelta
    TIGERDATA_AVAILABLE = True
except ImportError:
    TIGERDATA_AVAILABLE = False
    print("⚠️ psycopg2 not installed. Run: pip install psycopg2-binary")

# Gemini uses REST API directly (no library needed - works on serverless)
GEMINI_AVAILABLE = True  # requests is always available

# Initialize ElevenLabs client
# TODO: Set your ElevenLabs API key
# Get it from: https://elevenlabs.io/sign-up (free tier available)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

if ELEVENLABS_API_KEY and ELEVENLABS_AVAILABLE:
    elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
else:
    elevenlabs_client = None
    print("⚠️ ElevenLabs API key not set. Voice features will be disabled.")
    print("   Set ELEVENLABS_API_KEY environment variable.")

# Initialize Gemini via REST API (no library dependency)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

def gemini_generate(prompt: str) -> str:
    """Call Gemini API via REST. Returns generated text or None on error."""
    if not GEMINI_API_KEY:
        return None
    try:
        import requests as _req
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        resp = _req.post(url, headers={"x-goog-api-key": GEMINI_API_KEY}, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=10)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Gemini error: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"Gemini error: {str(e)}")
        return None

gemini_model = GEMINI_API_KEY  # Truthy if key is set

# ============================================================================
# TIGER DATA (TIMESCALE) INTEGRATION
# ============================================================================
# Tiger Data = PostgreSQL optimized for time-series data
# Use for: Real-time bus tracking, gym occupancy trends, query performance

TIGERDATA_URL = os.environ.get("TIGERDATA_URL", "")
tigerdata_conn = None

if TIGERDATA_URL and TIGERDATA_AVAILABLE:
    try:
        tigerdata_conn = psycopg2.connect(TIGERDATA_URL, connect_timeout=5)
        tigerdata_conn.autocommit = True  # A failed optional statement must not poison later queries.
        print("✅ Connected to Tiger Data (Timescale)")
        
        # Initialize hypertables for time-series data
        with tigerdata_conn.cursor() as cur:
            # Table 1: Real-time bus positions
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
            
            # Convert to hypertable for time-series optimization
            try:
                cur.execute("""
                    SELECT create_hypertable('bus_positions_realtime', 'time',
                                           if_not_exists => TRUE)
                """)
            except Exception as e:
                # Table might already be a hypertable
                pass
            
            # Table 2: Gym occupancy tracking
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
            except Exception as e:
                pass
            
            # Table 3: Query performance tracking
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
            except Exception as e:
                pass
            
            tigerdata_conn.commit()
            print("✅ Tiger Data tables initialized")
            
    except Exception as e:
        print(f"⚠️ Tiger Data connection failed: {str(e)}")
        tigerdata_conn = None
else:
    print("⚠️ Tiger Data not configured. Real-time tracking will use Delta Lake only.")

# Tiger Data helper functions
def store_bus_position_realtime(vehicle_id, route_code, route_name, lat, lon, 
                                current_stop, next_stop, eta_min, speed=0.0):
    """Store bus position in Tiger Data for real-time tracking."""
    if not tigerdata_conn:
        return False
    
    try:
        with tigerdata_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bus_positions_realtime 
                (time, vehicle_id, route_code, route_name, latitude, longitude,
                 current_stop, next_stop, eta_minutes, speed_mph)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (vehicle_id, route_code, route_name, lat, lon, 
                  current_stop, next_stop, eta_min, speed))
            tigerdata_conn.commit()
        return True
    except Exception as e:
        print(f"Error storing bus position: {str(e)}")
        return False

def get_bus_positions_last_n_minutes(minutes=5):
    """Get all bus positions from the last N minutes."""
    if not tigerdata_conn:
        return []
    
    try:
        with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM bus_positions_realtime
                WHERE time >= NOW() - %s * INTERVAL '1 minute'
                ORDER BY time DESC
            """, (minutes,))
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching bus positions: {str(e)}")
        return []

def get_average_eta_for_route(route_code, stop_name, hours_back=24):
    """Get average ETA for a specific route/stop over last N hours."""
    if not tigerdata_conn:
        return None
    
    try:
        with tigerdata_conn.cursor() as cur:
            cur.execute("""
                SELECT AVG(eta_minutes) as avg_eta
                FROM bus_positions_realtime
                WHERE route_code = %s 
                  AND next_stop = %s
                  AND time >= NOW() - %s * INTERVAL '1 hour'
            """, (route_code, stop_name, hours_back))
            result = cur.fetchone()
            return result[0] if result and result[0] else None
    except Exception as e:
        print(f"Error calculating average ETA: {str(e)}")
        return None

def store_gym_occupancy(facility_name, current, max_capacity):
    """Store gym occupancy snapshot in Tiger Data."""
    if not tigerdata_conn:
        return False
    
    try:
        occupancy_pct = (current / max_capacity * 100) if max_capacity > 0 else 0
        with tigerdata_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gym_occupancy_realtime
                (time, facility_name, current_occupancy, max_capacity, occupancy_percent)
                VALUES (NOW(), %s, %s, %s, %s)
            """, (facility_name, current, max_capacity, occupancy_pct))
            tigerdata_conn.commit()
        return True
    except Exception as e:
        print(f"Error storing gym occupancy: {str(e)}")
        return False

def get_gym_occupancy_pattern(facility_name, day_of_week=None):
    """Get typical gym occupancy pattern by hour of day."""
    if not tigerdata_conn:
        return []
    
    try:
        with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT 
                    EXTRACT(HOUR FROM time) as hour,
                    AVG(occupancy_percent) as avg_occupancy,
                    MIN(occupancy_percent) as min_occupancy,
                    MAX(occupancy_percent) as max_occupancy
                FROM gym_occupancy_realtime
                WHERE facility_name = %s
                  AND time >= NOW() - INTERVAL '30 days'
            """
            
            if day_of_week is not None:
                query += " AND EXTRACT(DOW FROM time) = %s"
                cur.execute(query + " GROUP BY EXTRACT(HOUR FROM time) ORDER BY hour",
                          (facility_name, day_of_week))
            else:
                cur.execute(query + " GROUP BY EXTRACT(HOUR FROM time) ORDER BY hour",
                          (facility_name,))
            
            return cur.fetchall()
    except Exception as e:
        print(f"Error getting gym pattern: {str(e)}")
        return []

def track_query_performance(query_type, response_time_ms, ai_service, success=True):
    """Track query performance for monitoring."""
    if not tigerdata_conn:
        return False
    
    try:
        with tigerdata_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO query_performance
                (time, query_type, response_time_ms, ai_service, success)
                VALUES (NOW(), %s, %s, %s, %s)
            """, (query_type, response_time_ms, ai_service, success))
            tigerdata_conn.commit()
        return True
    except Exception as e:
        print(f"Error tracking performance: {str(e)}")
        return False

def transcribe_audio(audio_base64: str) -> str:
    """
    Convert speech to text using ElevenLabs.
    
    Args:
        audio_base64: Base64-encoded audio data from browser
    
    Returns:
        Transcribed text
    """
    if not elevenlabs_client:
        raise RuntimeError("Voice input unavailable: configure ELEVENLABS_API_KEY")
    
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64, validate=True)
        
        # Call ElevenLabs speech-to-text API (scribe_v1 model)
        import io
        result = elevenlabs_client.speech_to_text.convert(
            file=io.BytesIO(audio_bytes),
            model_id="scribe_v1",
            file_format="other",  # MP3/webm from browser mic
        )
        text = getattr(result, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("No speech was recognized")
        return text.strip()
    except Exception as e:
        raise RuntimeError("Could not transcribe the recording. Please try again or type your question.") from e

def text_to_speech(text: str) -> str:
    """
    Convert text to speech using ElevenLabs.
    
    Args:
        text: Response text to speak
    
    Returns:
        Base64-encoded audio data
    """
    if not elevenlabs_client:
        return ""
    
    try:
        # Call ElevenLabs TTS API (new API: text_to_speech.convert)
        audio = elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id="hpp4J3VqNfWAUOO0d1Us",  # Bella voice
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        
        # Convert audio generator to bytes
        audio_bytes = b"".join(audio)
        
        # Encode as base64 for browser
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        return audio_base64
    except Exception as e:
        print(f"TTS error: {str(e)}")
        return ""

# ============================================================================
# QUERY ROUTING
# ============================================================================

def route_query_with_gemini(query: str) -> str:
    """
    Use Gemini AI to understand query intent and route to appropriate feature.
    Falls back to keyword matching if Gemini is unavailable.
    
    Args:
        query: Natural language query from student
    
    Returns:
        Response text from the appropriate feature
    """
    if not gemini_model:
        # Fallback to keyword matching
        return route_query_keywords(query)
    
    try:
        # Ask Gemini to classify the query intent
        classification_prompt = f"""
You are a campus assistant router. Classify this student query into ONE category:
- "bus" (transportation, getting to a place, routes, transit)
- "food" (dining, eating, restaurants, dietary needs, allergies, meal plans)
- "health" (gym, fitness, mental health, counseling, medical, wellness)
- "events" (clubs, activities, groups, social, cultural events)
- "professional" (research, internship, career, resume, job, career fair)
- "general" (anything else)

Student query: "{query}"

Respond with ONLY the category name, nothing else.
"""
        
        classification = gemini_generate(classification_prompt)
        if not classification:
            return route_query_keywords(query)
        category = classification.strip().lower()
        
        # Route based on AI classification
        if "bus" in category or "transit" in category:
            response = recommend_bus_route(query)
        elif "food" in category or "dining" in category:
            response = recommend_food(query)
        elif "health" in category or "gym" in category or "wellness" in category:
            response = find_health_resources(query)
        elif "event" in category or "club" in category:
            response = find_events_and_clubs(query)
        elif "professional" in category or "career" in category or "research" in category:
            response = find_professional_resources(query)
        else:
            response = (
                "I'm your VT Campus Life Assistant! I can help with:\n\n"
                "🚌 Bus Routes - Ask me how to get somewhere\n"
                "🍽️ Food - Find dining options and dietary info\n"
                "💪 Health - Gym hours, mental health resources\n"
                "🎉 Events - Campus activities and clubs\n"
                "Professional - Research, internships, career resources\n\n"
                "Try asking: 'How do I get to Walmart?' or 'Where can I eat vegetarian food?'"
            )
        
        if "food" in category or "dining" in category:
            return response

        # Use Gemini to make the response more conversational
        enhancement_prompt = f"""
You are a friendly VT campus assistant. Take this technical response and make it more conversational and student-friendly. Keep all the factual information but make it sound natural and helpful.

Original response:
{response}

Student's question: {query}

Provide an enhanced response that's warm, helpful, and natural. Keep it concise (under 200 words).
"""
        
        enhanced = gemini_generate(enhancement_prompt)
        if enhanced:
            return enhanced.strip()
        return response
        
    except Exception as e:
        print(f"Gemini error: {str(e)}")
        # Fallback to keyword matching
        return route_query_keywords(query)

def route_query_keywords(query: str) -> str:
    """
    Fallback keyword-based routing (used when Gemini is unavailable).
    
    Args:
        query: Natural language query from student
    
    Returns:
        Response text from the appropriate feature
    """
    query_lower = query.lower()
    
    # Feature 1: Bus/Transit keywords
    if any(word in query_lower for word in ["bus", "transit", "ride", "route", "get to", "how do i get"]):
        return recommend_bus_route(query)
    
    # Feature 2: Food keywords
    elif any(word in query_lower for word in ["food", "eat", "dining", "meal", "restaurant", "hungry", "dietary", "allergy"]):
        return recommend_food(query)
    
    # Feature 3: Health keywords
    elif any(word in query_lower for word in ["gym", "workout", "health", "counselor", "mental", "fitness", "mccomas", "sick"]):
        return find_health_resources(query)
    
    # Feature 4: Events/clubs keywords
    elif any(word in query_lower for word in ["event", "club", "activities", "group", "meet people", "cultural"]):
        return find_events_and_clubs(query)
    
    # Feature 5: Professional keywords
    elif any(word in query_lower for word in ["research", "internship", "career", "resume", "job", "career fair", "interview", "professional", "co-op"]):
        return find_professional_resources(query)
    
    # Default: provide guidance
    else:
        return (
            "I'm your VT Campus Life Assistant! I can help with:\n\n"
            "🚌 Bus Routes - Ask me how to get somewhere\n"
            "🍽️ Food - Find dining options and dietary info\n"
            "💪 Health - Gym hours, mental health resources\n"
            "🎉 Events - Campus activities and clubs (coming soon)\n\n"
            "Try asking: 'How do I get to Walmart?' or 'Where can I eat vegetarian food?'"
        )

# Main routing function (uses Gemini if available)
def route_query(query: str) -> str:
    """Route query using Gemini AI or fallback to keywords."""
    return route_query_with_gemini(query)

# ============================================================================
# WEB ROUTES
# ============================================================================

@app.route("/")
def home():
    """Main page with voice-enabled chat interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/query", methods=["POST"])
def handle_query():
    """Handle text or voice queries"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send a JSON object"}), 400
    query_type = data.get("type", "text")
    if query_type not in ("text", "voice"):
        return jsonify({"error": "Unknown query type"}), 400
    if query_type == "voice":
        recording = data.get("audio")
        if not isinstance(recording, str) or not recording.strip():
            return jsonify({"error": "No recording provided"}), 400
        try:
            query_text = transcribe_audio(recording)
        except RuntimeError as exc:
            app.logger.exception("Voice transcription failed")
            return jsonify({"error": str(exc)}), 502
    else:
        query_text = data.get("query")
    if not isinstance(query_text, str) or not query_text.strip():
        return jsonify({"error": "Provide a non-empty text query"}), 400
    query_text = query_text.strip()
    try:
        response_text = route_query(query_text)
    except Exception:
        app.logger.exception("Query failed")
        return jsonify({"error": "Campus data is temporarily unavailable. Please try again."}), 503

    # Convert response to speech if requested
    audio_base64 = ""
    if data.get("want_audio", False):
        audio_base64 = text_to_speech(response_text)
    
    return jsonify({
        "query": query_text,
        "response": response_text,
        "audio": audio_base64
    })

@app.route("/health")
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "features": {
            "bus_helper": "ready",
            "food_info": "ready",
            "health_helper": "ready",
            "events_clubs": "ready",
            "professional": "ready"
        },
        "ai_services": {
            "elevenlabs": "enabled" if elevenlabs_client else "disabled",
            "gemini": "enabled" if gemini_model else "disabled",
            "tiger_data": "enabled" if tigerdata_conn else "disabled"
        },
        "architecture": {
            "data_platform": "Databricks Delta Lake",
            "realtime_db": "Tiger Data (Timescale)" if tigerdata_conn else "Delta Lake only",
            "ai_brain": GEMINI_MODEL if gemini_model else "Keyword matching",
            "voice_io": "ElevenLabs" if elevenlabs_client else "Text only"
        }
    })

@app.route("/api/realtime/buses")
def realtime_buses():
    """Get real-time bus positions from Tiger Data (time-series query)."""
    if not tigerdata_conn:
        return jsonify({"error": "Tiger Data not connected", "positions": []}), 503
    
    try:
        minutes = request.args.get("minutes", 5, type=int)
        with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (vehicle_id)
                    vehicle_id, route_code, route_name, latitude, longitude,
                    current_stop, next_stop, eta_minutes, time
                FROM bus_positions_realtime
                WHERE time >= NOW() - %s * INTERVAL '1 minute'
                ORDER BY vehicle_id, time DESC
            """, (minutes,))
            positions = cur.fetchall()
        
        return jsonify({
            "source": "Tiger Data (Timescale)",
            "query": f"DISTINCT positions from last {minutes} minutes",
            "count": len(positions),
            "positions": [dict(p) for p in positions]
        })
    except Exception as e:
        return jsonify({"error": str(e), "positions": []}), 500

@app.route("/api/realtime/gym")
def realtime_gym():
    """Get real-time gym occupancy from Tiger Data."""
    if not tigerdata_conn:
        return jsonify({"error": "Tiger Data not connected", "facilities": []}), 503
    
    try:
        with tigerdata_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (facility_name)
                    facility_name, current_occupancy, max_capacity, occupancy_percent, time
                FROM gym_occupancy_realtime
                ORDER BY facility_name, time DESC
            """)
            facilities = cur.fetchall()
        
        return jsonify({
            "source": "Tiger Data (Timescale)",
            "facilities": [dict(f) for f in facilities]
        })
    except Exception as e:
        return jsonify({"error": str(e), "facilities": []}), 500

@app.route("/api/stats")
def tigerdata_stats():
    """Get Tiger Data statistics - shows time-series DB in action for judges."""
    if not tigerdata_conn:
        return jsonify({"error": "Tiger Data not connected"}), 503
    
    try:
        stats = {}
        with tigerdata_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bus_positions_realtime")
            stats["total_bus_records"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM gym_occupancy_realtime")
            stats["total_gym_records"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM query_performance")
            stats["total_queries_tracked"] = cur.fetchone()[0]
            
            cur.execute("""
                SELECT query_type, AVG(response_time_ms) as avg_ms, COUNT(*) as count
                FROM query_performance
                GROUP BY query_type
            """)
            perf = cur.fetchall()
            stats["query_performance"] = [
                {"type": r[0], "avg_ms": float(r[1]), "count": r[2]}
                for r in perf
            ]
        
        stats["database"] = "Tiger Data (Timescale PostgreSQL)"
        stats["tables"] = ["bus_positions_realtime", "gym_occupancy_realtime", "query_performance"]
        stats["hypertables"] = True
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# HTML TEMPLATE (Frontend)
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VT Campus Life Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #630031 0%, #cf4520 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .chat-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 700px;
            height: 600px;
            display: flex;
            flex-direction: column;
        }
        
        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        
        .message {
            margin-bottom: 15px;
            display: flex;
            align-items: flex-start;
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 16px;
            border-radius: 18px;
            white-space: pre-wrap;
        }
        
        .message.user .message-content {
            background: #630031;
            color: white;
        }
        
        .message.assistant .message-content {
            background: #f0f0f0;
            color: #333;
        }
        
        .input-area {
            padding: 20px;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        #queryInput {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
        }
        
        #queryInput:focus {
            border-color: #630031;
        }
        
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        #sendBtn {
            background: #630031;
            color: white;
        }
        
        #sendBtn:hover {
            background: #4a0024;
        }
        
        #voiceBtn {
            background: #cf4520;
            color: white;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        #voiceBtn:hover {
            background: #a83819;
        }
        
        #voiceBtn.recording {
            background: #ff0000;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            margin-top: 20px;
            max-width: 700px;
            width: 100%;
        }
        
        .feature-tag {
            background: rgba(255, 255, 255, 0.9);
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            color: #630031;
            font-weight: bold;
        }
        
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏫 VT Campus Life Assistant</h1>
        <p>Powered by Databricks, Gemini AI & ElevenLabs Voice</p>
    </div>
    
    <div class="chat-container">
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
                <div class="message-content">
                    👋 Hi! I'm your VT Campus Life Assistant powered by Databricks, Gemini AI, and ElevenLabs voice!\n\nI can help you with:\n🚌 Bus routes and transit\n🍽️ Dining and food options\n💪 Gym and health resources\n🎉 Campus events and clubs\nResearch and career resources\n\nI understand natural language - try asking complex questions like:\n• \"I'm at Squires and need vegetarian lunch near the gym\"\n• \"When's the best time to workout before my 2pm class?\"\n\nType your question or click 🎤 to speak!
                </div>
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="queryInput" placeholder="Ask me anything about campus life..." />
            <button id="sendBtn" onclick="sendTextQuery()">Send</button>
            <button id="voiceBtn" onclick="toggleVoiceInput()" title="Voice input">
                🎤
            </button>
        </div>
    </div>
    
    <div class="features">
        <div class="feature-tag">🚌 Bus Helper</div>
        <div class="feature-tag">🍽️ Food Finder</div>
        <div class="feature-tag">💪 Health Hub</div>
        <div class="feature-tag">🎉 Events & Clubs</div>
        <div class="feature-tag">Professional</div>
    </div>
    
    <script>
        let isRecording = false;
        let mediaRecorder = null;
        let audioChunks = [];
        
        // Send text query
        async function sendTextQuery() {
            const input = document.getElementById('queryInput');
            const query = input.value.trim();
            
            if (!query) return;
            
            // Add user message
            addMessage('user', query);
            input.value = '';
            
            // Show loading
            const container = document.querySelector('.chat-container');
            container.classList.add('loading');
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: 'text',
                        query: query,
                        want_audio: true
                    })
                });
                
                const data = await response.json();
                if (!response.ok || data.error) throw new Error(data.error || 'Request failed');
                
                // Add assistant response
                addMessage('assistant', data.response);
                
                // Play audio if available
                if (data.audio) {
                    playAudio(data.audio);
                }
            } catch (error) {
                addMessage('assistant', '⚠️ Error: ' + error.message);
            } finally {
                container.classList.remove('loading');
            }
        }
        
        // Toggle voice recording
        async function toggleVoiceInput() {
            const btn = document.getElementById('voiceBtn');
            
            if (!isRecording) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];
                    
                    mediaRecorder.ondataavailable = (event) => {
                        audioChunks.push(event.data);
                    };
                    
                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                        stream.getTracks().forEach(track => track.stop());
                        const reader = new FileReader();
                        reader.readAsDataURL(audioBlob);
                        reader.onloadend = async () => {
                            const base64Audio = reader.result.split(',')[1];
                            await sendVoiceQuery(base64Audio);
                        };
                    };
                    
                    mediaRecorder.start();
                    isRecording = true;
                    btn.classList.add('recording');
                    btn.textContent = '⏹️';
                } catch (error) {
                    alert('Microphone access denied or not available');
                }
            } else {
                mediaRecorder.stop();
                isRecording = false;
                btn.classList.remove('recording');
                btn.textContent = '🎤';
            }
        }
        
        // Send voice query
        async function sendVoiceQuery(audioBase64) {
            const container = document.querySelector('.chat-container');
            container.classList.add('loading');
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: 'voice',
                        audio: audioBase64,
                        want_audio: true
                    })
                });
                
                const data = await response.json();
                if (!response.ok || data.error) throw new Error(data.error || 'Request failed');
                
                // Add transcribed query
                addMessage('user', data.query);
                
                // Add assistant response
                addMessage('assistant', data.response);
                
                // Play audio response
                if (data.audio) {
                    playAudio(data.audio);
                }
            } catch (error) {
                addMessage('assistant', '⚠️ Error: ' + error.message);
            } finally {
                container.classList.remove('loading');
            }
        }
        
        // Add message to chat
        function addMessage(role, text) {
            const messagesDiv = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = text;
            
            messageDiv.appendChild(contentDiv);
            messagesDiv.appendChild(messageDiv);
            
            // Scroll to bottom
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        // Play audio response
        function playAudio(base64Audio) {
            const audio = new Audio('data:audio/mp3;base64,' + base64Audio);
            audio.play();
        }
        
        // Enter key to send
        document.getElementById('queryInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendTextQuery();
        });
    </script>
</body>
</html>
'''

# ============================================================================
# RUN APP
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", os.environ.get("PORT", 8000)))
    app.run(host="0.0.0.0", port=port, debug=False)
