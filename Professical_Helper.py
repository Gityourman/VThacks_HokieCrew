# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Project Overview
# MAGIC %md
# MAGIC # 🎓 VThacks Professional Helper
# MAGIC
# MAGIC **Deloitte × Databricks Challenge - Campus Life Intelligence Hub**
# MAGIC
# MAGIC ## Overview
# MAGIC This notebook implements the **Professional Helper** — an AI-powered recommendation system for Virginia Tech students seeking research, internship, and full-time career opportunities.
# MAGIC
# MAGIC ### Features
# MAGIC * Natural language recommendations for research opportunities at VT
# MAGIC * Career resource matching (resume help, interview prep, coaching)
# MAGIC * Upcoming career fair and event discovery
# MAGIC * Career pathway exploration by industry (12+ career communities)
# MAGIC * Filters by field of study, opportunity type, and eligibility
# MAGIC
# MAGIC ### Data Sources
# MAGIC * VT Office of Undergraduate Research: https://www.research.undergraduate.vt.edu/index.html
# MAGIC * VT Career and Professional Development: https://career.vt.edu/
# MAGIC * Handshake (referenced for job/internship search): http://vt.joinhandshake.com
# MAGIC
# MAGIC ### Delta Tables
# MAGIC * `workspace.default.research_opportunities` — Research programs, fellowships, and grants at VT
# MAGIC * `workspace.default.career_resources` — Career services, programs, and tools
# MAGIC * `workspace.default.career_events` — Upcoming career fairs and info sessions
# MAGIC * `workspace.default.career_pathways` — Industry-specific career community info
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# Install required packages for web scraping
import subprocess
import sys

print("Installing required packages...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4"])
print("Packages installed: requests, beautifulsoup4")

# COMMAND ----------

# DBTITLE 1,Data Collection Section
# MAGIC %md
# MAGIC ## Step 1: Data Collection
# MAGIC Scrape VT Office of Undergraduate Research and Career & Professional Development websites to build structured datasets.
# MAGIC
# MAGIC ### Sources:
# MAGIC * Research opportunities: https://www.research.undergraduate.vt.edu/research-and-engagement/student-research-and-engagement/research-opportunities/virginia-tech-research-opportunities.html
# MAGIC * Career resources: https://career.vt.edu/
# MAGIC * Career fairs: https://career.vt.edu/resources/career-fairs/
# MAGIC * Career pathways: https://career.vt.edu/channels/

# COMMAND ----------

# DBTITLE 1,Scrape Research Opportunities
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# ── Scrape VT Research Opportunities ──
RESEARCH_BASE = "https://www.research.undergraduate.vt.edu"
research_url = f"{RESEARCH_BASE}/research-and-engagement/student-research-and-engagement/research-opportunities/virginia-tech-research-opportunities.html"
resp = requests.get(research_url, headers=HEADERS, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

# Extract research programs from links
research_opportunities = []
seen_programs = set()

for link in soup.find_all("a", href=True):
    href = link["href"]
    text = link.get_text(strip=True)
    if text and len(text) > 5 and "/virginia-tech-research-opportunities/" in href:
        if text not in seen_programs and "License" not in text and "Current page" not in text:
            seen_programs.add(text)
            full_url = href if href.startswith("http") else f"{RESEARCH_BASE}/{href.lstrip('/')}"
            
            # Determine category based on program name
            name_lower = text.lower()
            if "fellowship" in name_lower or "furf" in name_lower or "surf" in name_lower:
                category = "Fellowship"
            elif "grant" in name_lower:
                category = "Grant"
            elif "reu" in name_lower:
                category = "REU Program"
            elif "summer" in name_lower:
                category = "Summer Program"
            elif "biotech" in name_lower or "biomedical" in name_lower or "neuro" in name_lower or "glyco" in name_lower:
                category = "Science Research"
            elif "data science" in name_lower or "dspg" in name_lower:
                category = "Data Science"
            elif "policy" in name_lower:
                category = "Policy Fellowship"
            else:
                category = "Research Program"
            
            # Determine field based on name
            if "biomed" in name_lower or "neuro" in name_lower or "glyco" in name_lower or "biotech" in name_lower:
                field = "Biomedical/Life Sciences"
            elif "neutrino" in name_lower or "physics" in name_lower:
                field = "Physics"
            elif "data science" in name_lower or "dspg" in name_lower:
                field = "Data Science"
            elif "global change" in name_lower or "cnre" in name_lower:
                field = "Environmental/Natural Resources"
            elif "honors" in name_lower:
                field = "All Fields"
            elif "ictas" in name_lower:
                field = "Engineering/Technology"
            elif "health" in name_lower or "ihsr" in name_lower:
                field = "Health Sciences"
            elif "first-year" in name_lower or "fralin" in name_lower:
                field = "Life Sciences"
            else:
                field = "Multiple Fields"
            
            # Determine eligibility
            if "first-year" in name_lower:
                eligibility = "First-year students"
            elif "summer" in name_lower or "surf" in name_lower:
                eligibility = "Summer program, undergraduates"
            elif "honors" in name_lower:
                eligibility = "Honors College students"
            else:
                eligibility = "Undergraduate students"
            
            research_opportunities.append({
                "name": text,
                "category": category,
                "field": field,
                "eligibility": eligibility,
                "url": full_url,
                "description": f"{category} in {field}. See program page for details and application deadlines.",
            })

# Add additional known research programs from the OUR website
additional_programs = [
    {"name": "Discovery Lab", "category": "Research Program", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/index.html", "description": "Hands-on research exploration program for students curious about undergraduate research at VT."},
    {"name": "Dennis Dean Undergraduate Research Conference", "category": "Conference", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/present-and-publish/student-present-and-publish/virginia-tech-conferences/dennis-dean-conference.html", "description": "Annual research conference where students present their work. Great for networking and showcasing research."},
    {"name": "Sigma Xi Student Research Awards", "category": "Award", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/research-and-engagement/student-research-and-engagement/our-and-sigma-xi.html", "description": "Research awards recognizing outstanding undergraduate research at Virginia Tech."},
    {"name": "Research Credit", "category": "Academic Credit", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/research-and-engagement/student-research-and-engagement/research-credit.html", "description": "Earn academic credit for research work with faculty mentors."},
    {"name": "Getting Started Guide", "category": "Resource", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/research-and-engagement/student-research-and-engagement/getting-started-guide.html", "description": "Step-by-step guide on how to get started with undergraduate research at VT."},
    {"name": "Student Travel Grant", "category": "Grant", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/funding-and-support/student-funding-and-support/travel-grant.html", "description": "Funding for students to travel and present their research at conferences."},
    {"name": "Poster Printing Support", "category": "Funding", "field": "All Fields", "eligibility": "All undergraduates", "url": f"{RESEARCH_BASE}/funding-and-support/student-funding-and-support/poster-printing.html", "description": "Free poster printing for students presenting research at conferences."},
]
research_opportunities.extend(additional_programs)

print(f"Collected {len(research_opportunities)} research opportunities:")
for r in research_opportunities:
    print(f"  [{r['category']}] {r['name']} ({r['field']})")

# COMMAND ----------

# DBTITLE 1,Scrape Career Resources
# ── Scrape Career Resources from career.vt.edu ──
CAREER_BASE = "https://career.vt.edu"

career_resources = []

# Known career resources and programs from career.vt.edu
career_resources_data = [
    {"name": "Handshake", "category": "Job Search Platform", "type": "Tool", "url": "http://vt.joinhandshake.com", "description": "VT's primary job and internship platform. Search thousands of opportunities, connect with employers, and schedule career fair appointments."},
    {"name": "Cooperative Education and Internship Program (CEIP)", "category": "Internship Program", "type": "Program", "url": f"{CAREER_BASE}/channels/ceip/", "description": "Structured co-op and internship program providing real-world experience while earning academic credit."},
    {"name": "Campus internEXP", "category": "Internship Program", "type": "Program", "url": f"{CAREER_BASE}/channels/campus-internexp/", "description": "On-campus internship program for students seeking professional experience without leaving campus."},
    {"name": "Career Coaching & Advising", "category": "Advising", "type": "Service", "url": f"{CAREER_BASE}/channels/career-advising/", "description": "One-on-one career coaching appointments with professional advisors. Get help with career exploration, job search, and more."},
    {"name": "Resume & CV Support", "category": "Resume Help", "type": "Resource", "url": f"{CAREER_BASE}/channels/resume-cv/", "description": "Resume and CV reviews, templates, and group advising sessions. Get your resume career-fair ready."},
    {"name": "Cover Letter Support", "category": "Documents", "type": "Resource", "url": f"{CAREER_BASE}/channels/cover-letter-supporting-documents/", "description": "Guides and templates for writing effective cover letters and supporting documents."},
    {"name": "Interview Preparation", "category": "Interview Prep", "type": "Resource", "url": f"{CAREER_BASE}/channels/prepare-for-an-interview/", "description": "Mock interviews, interview tips, and preparation resources for all types of interviews."},
    {"name": "Explore Your Interests / Self Assessment", "category": "Career Exploration", "type": "Tool", "url": f"{CAREER_BASE}/channels/explore-your-interests-self-assessment/", "description": "Self-assessment tools to help you discover career paths aligned with your interests and strengths."},
    {"name": "Networking & Mentorship", "category": "Networking", "type": "Resource", "url": f"{CAREER_BASE}/channels/expand-your-network-or-mentor/", "description": "Resources for building professional networks and finding mentors in your field."},
    {"name": "Graduate School Preparation", "category": "Grad School", "type": "Resource", "url": f"{CAREER_BASE}/channels/prepare-for-graduate-school/", "description": "Guidance on preparing for and applying to graduate school programs."},
    {"name": "Salary and Benefits", "category": "Career Info", "type": "Resource", "url": f"{CAREER_BASE}/channels/salary-benefits/", "description": "Salary negotiation guidance, benefits information, and market data for different career fields."},
    {"name": "Federal Job and Internship Search", "category": "Job Search", "type": "Resource", "url": f"{CAREER_BASE}/channels/federal-job-and-internship-search/", "description": "Specialized resources for finding federal government jobs and internships."},
    {"name": "Get Career Ready", "category": "Career Readiness", "type": "Program", "url": f"{CAREER_BASE}/channels/get-career-ready/", "description": "Career readiness program to develop professional skills and competencies employers seek."},
    {"name": "Career Ready Series", "category": "Career Readiness", "type": "Workshop Series", "url": f"{CAREER_BASE}/resources/career-ready-series/", "description": "Workshop series covering resume writing, interviewing, job search strategies, and more."},
    {"name": "Student Internship and Co-op Network (SICN)", "category": "Internship Program", "type": "Network", "url": f"{CAREER_BASE}/channels/sicn/", "description": "Network for students in co-ops and internships to connect and share experiences."},
    {"name": "Ut Prosim Internship Support Fund", "category": "Funding", "type": "Financial Support", "url": f"{CAREER_BASE}/resources/ut-prosim-fund/", "description": "Financial support for students completing unpaid or low-paid internships."},
    {"name": "Career Outfitters", "category": "Career Fair Prep", "type": "Service", "url": f"{CAREER_BASE}/channels/career-outfitters/", "description": "Free professional clothing for students attending career fairs and interviews."},
    {"name": "Peer Career Advisor Program", "category": "Advising", "type": "Peer Support", "url": f"{CAREER_BASE}/resources/peer-career-advisor-program/", "description": "Get advice from trained peer career advisors on resumes, job search, and career exploration."},
    {"name": "VMock Resume Review", "category": "Resume Help", "type": "AI Tool", "url": f"{CAREER_BASE}/", "description": "AI-powered resume review platform that provides instant feedback on your resume."},
    {"name": "Health Professions Advising", "category": "Advising", "type": "Specialized Advising", "url": f"{CAREER_BASE}/channels/health-professions-advising/", "description": "Specialized advising for students pursuing health professions (med school, dental, vet med, etc.)."},
    {"name": "iris Photo Booth", "category": "Career Fair Prep", "type": "Service", "url": f"{CAREER_BASE}/resources/iris-photo-booth/", "description": "Free professional headshots for your LinkedIn, Handshake, and professional profiles."},
]
career_resources = career_resources_data

print(f"Collected {len(career_resources)} career resources")
for r in career_resources:
    print(f"  [{r['category']}] {r['name']}")

# COMMAND ----------

# DBTITLE 1,Scrape Career Events
# ── Scrape Upcoming Career Events from career.vt.edu ──
events_url = f"{CAREER_BASE}/"
resp = requests.get(events_url, headers=HEADERS, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

career_events = []
seen_events = set()

for link in soup.find_all("a", href=True):
    href = link["href"]
    text = link.get_text(strip=True)
    if "/events/" in href and text and len(text) > 5 and "Event" in text:
        # Clean the event name and extract date/time info
        # Format: "Sep22Event:Data Science Connections Career Fair - Fall 2026Tue, Sep 22 from 10am - 4pm..."
        import re as _re
        # Extract event name after the date prefix
        name_match = _re.search(r'Event:(.+?)(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)', text)
        if name_match:
            event_name = name_match.group(1).strip()
            # Extract date/time
            date_match = _re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun), (\w+ \d+) from (.+?)(?:day|urday)', text)
            if date_match:
                date_info = f"{date_match.group(1)}, {date_match.group(2)} from {date_match.group(3)}"
            else:
                date_info = "See event page for details"
        else:
            event_name = text[:80]
            date_info = "See event page for details"
        
        if event_name not in seen_events:
            seen_events.add(event_name)
            full_url = href if href.startswith("http") else f"{CAREER_BASE}{href}"
            
            # Determine event type
            name_lower = event_name.lower()
            if "career fair" in name_lower or "connections" in name_lower:
                event_type = "Career Fair"
            elif "info session" in name_lower or "information session" in name_lower:
                event_type = "Info Session"
            elif "resume" in name_lower or "cv" in name_lower:
                event_type = "Resume Workshop"
            elif "interview" in name_lower:
                event_type = "Interview Workshop"
            elif "internship" in name_lower:
                event_type = "Internship Event"
            elif "advising" in name_lower or "advis" in name_lower:
                event_type = "Advising Session"
            elif "panel" in name_lower or "day in the life" in name_lower:
                event_type = "Panel Discussion"
            elif "stoke" in name_lower or "space" in name_lower or "rocket" in name_lower:
                event_type = "Company Info Session"
            else:
                event_type = "Career Event"
            
            # Determine target audience
            if "graduate" in name_lower or "dc" in name_lower:
                audience = "Graduate Students"
            elif "ceip" in name_lower or "co-op" in name_lower:
                audience = "Undergraduate Students"
            else:
                audience = "All Students"
            
            career_events.append({
                "name": event_name,
                "event_type": event_type,
                "audience": audience,
                "date_info": date_info,
                "url": full_url,
                "description": f"{event_type} for {audience}. {date_info}.",
            })

# Add known career fairs from the career fairs page
career_fairs_data = [
    {"name": "Fall 2026 University-wide Career Fair", "event_type": "Career Fair", "audience": "All Students", "date_info": "Fall 2026", "url": f"{CAREER_BASE}/resources/career-fairs/", "description": "Major university-wide career fair with hundreds of employers across all industries."},
    {"name": "Spring 2027 University-wide Career Fair", "event_type": "Career Fair", "audience": "All Students", "date_info": "Spring 2027", "url": f"{CAREER_BASE}/resources/career-fairs/", "description": "Spring semester career fair for full-time jobs and internships."},
    {"name": "Data Science Connections Career Fair", "event_type": "Career Fair", "audience": "All Students", "date_info": "Fall 2026", "url": f"{CAREER_BASE}/events/2026/09/22/data-science-connections-career-fair-fall-2026/", "description": "Career fair focused on data science, analytics, and technology roles."},
    {"name": "Aerospace, Defense, and Intelligence Career Fair", "event_type": "Career Fair", "audience": "All Students", "date_info": "Fall 2026", "url": f"{CAREER_BASE}/events/2026/09/22/aerospace-defense-and-intelligence-career-fair-2026/", "description": "Career fair for aerospace, defense, and intelligence industry employers."},
    {"name": "Graduate and Professional School Fair", "event_type": "Career Fair", "audience": "All Students", "date_info": "October 5", "url": f"{CAREER_BASE}/resources/career-fairs/", "description": "Fair for students considering graduate and professional school programs."},
    {"name": "Majors and Minors Fair", "event_type": "Academic Fair", "audience": "All Students", "date_info": "October 14", "url": f"{CAREER_BASE}/resources/career-fairs/", "description": "Explore majors and minors at VT. Great for students deciding on their academic path."},
]
career_events.extend(career_fairs_data)

print(f"Collected {len(career_events)} career events:")
for e in career_events:
    print(f"  [{e['event_type']}] {e['name']} ({e['date_info']})")

# COMMAND ----------

# DBTITLE 1,Build Career Pathways Data
# ── Career Pathways (Industry Communities from career.vt.edu) ──
career_pathways = [
    {"pathway": "Technology, Engineering, and Manufacturing", "description": "For students interested in how things work, developing innovative solutions, robotics, manufacturing, and engineering design.", "careers": ["Software Engineer", "Mechanical Engineer", "Manufacturing Engineer", "Process Engineer", "Quality Engineer", "Product Engineer"], "resources": ["Vault Career Guide to Information Technology", "Vault Guide to IT Jobs", "Forage Virtual Experiences"], "url": f"{CAREER_BASE}/channels/technology-engineering-manufacturing/"},
    {"pathway": "Data Analytics, Cybersecurity, and IT", "description": "Focuses on the design, development, and management of technology systems and data solutions.", "careers": ["Data Analyst", "Data Scientist", "Cybersecurity Analyst", "IT Consultant", "Cloud Engineer", "Database Administrator"], "resources": ["Vault Career Guide to Cybersecurity", "Vault Guide to IT Consulting Jobs", "Deloitte Data Analytics Virtual Experience"], "url": f"{CAREER_BASE}/channels/data-cybersecurity-information-technology/"},
    {"pathway": "Business Management, Administration, and Finance", "description": "Encompasses roles focused on optimizing and overseeing core business functions including finance, operations, and management.", "careers": ["Management Consultant", "Investment Banker", "Financial Analyst", "Accountant", "Operations Manager", "Project Manager"], "resources": ["Vault Career Guide to Consulting", "Vault Career Guide to Investment Banking", "Vault Guide to Case Interviews"], "url": f"{CAREER_BASE}/channels/business-management-administration-finance/"},
    {"pathway": "Advertising and Marketing", "description": "For students interested in brand strategy, digital marketing, advertising, and creative communications.", "careers": ["Marketing Manager", "Brand Strategist", "Digital Marketing Specialist", "Advertising Executive", "Social Media Manager", "Content Creator"], "resources": ["Vault Guide to Social Media Jobs", "Marketing internships on Handshake"], "url": f"{CAREER_BASE}/channels/advertising-marketing/"},
    {"pathway": "Agriculture and Food", "description": "Careers in agriculture, food science, sustainability, and natural resource management.", "careers": ["Agricultural Scientist", "Food Scientist", "Farm Manager", "Sustainability Specialist", "Agricultural Economist", "Extension Agent"], "resources": ["USDA job listings", "Agriculture internships on Handshake"], "url": f"{CAREER_BASE}/channels/agriculture-food/"},
    {"pathway": "Architecture and Construction", "description": "For students in architecture, construction management, and built environment fields.", "careers": ["Architect", "Construction Manager", "Urban Planner", "Interior Designer", "Landscape Architect", "Building Inspector"], "resources": ["Architecture firm listings", "Construction management internships"], "url": f"{CAREER_BASE}/channels/architecture-construction/"},
    {"pathway": "Arts, Design, and Communication", "description": "Creative careers in visual arts, design, media, journalism, and communications.", "careers": ["Graphic Designer", "UX/UI Designer", "Journalist", "Art Director", "Multimedia Artist", "Communications Specialist"], "resources": ["Creative agency internships", "Portfolio development resources"], "url": f"{CAREER_BASE}/channels/arts-design-communication/"},
    {"pathway": "Education and Human Services", "description": "Careers in teaching, counseling, social work, and community services.", "careers": ["Teacher", "School Counselor", "Social Worker", "Education Administrator", "Community Outreach Coordinator", "Academic Advisor"], "resources": ["Teacher certification programs", "Education internships"], "url": f"{CAREER_BASE}/channels/education-human-services/"},
    {"pathway": "Government and Public Administration", "description": "Public service careers in local, state, and federal government.", "careers": ["Policy Analyst", "Government Relations Specialist", "Public Administrator", "Legislative Aide", "City Planner", "Foreign Service Officer"], "resources": ["Federal job search resources", "Pathways Programs"], "url": f"{CAREER_BASE}/channels/government-public-administration/"},
    {"pathway": "Healthcare and Health Sciences", "description": "Clinical and non-clinical careers in healthcare, medicine, and health sciences.", "careers": ["Physician", "Nurse", "Physical Therapist", "Healthcare Administrator", "Public Health Specialist", "Biomedical Researcher"], "resources": ["Health Professions Advising", "MCAT prep resources", "Clinical experience opportunities"], "url": f"{CAREER_BASE}/channels/healthcare-health-sciences/"},
    {"pathway": "Hospitality, Tourism, and Events", "description": "Careers in hospitality management, tourism, event planning, and the visitor industry.", "careers": ["Hotel Manager", "Event Planner", "Tourism Director", "Restaurant Manager", "Catering Director", "Conference Coordinator"], "resources": ["Hospitality internships", "Event planning certifications"], "url": f"{CAREER_BASE}/channels/hospitality-tourism-events/"},
    {"pathway": "Natural Resources, Sustainability, and Energy", "description": "Careers focused on environmental conservation, sustainability, energy, and natural resource management.", "careers": ["Environmental Scientist", "Sustainability Director", "Energy Analyst", "Conservation Biologist", "Renewable Energy Specialist", "Park Ranger"], "resources": ["Environmental internships", "Sustainability career guides"], "url": f"{CAREER_BASE}/channels/natural-resources-sustainability-energy/"},
]

print(f"Collected {len(career_pathways)} career pathways")
for p in career_pathways:
    print(f"  {p['pathway']} ({len(p['careers'])} careers)")

# COMMAND ----------

# DBTITLE 1,Delta Tables Section
# MAGIC %md
# MAGIC ## Step 2: Create Delta Lake Tables
# MAGIC Store research opportunities, career resources, events, and pathways in Unity Catalog Delta tables.

# COMMAND ----------

# DBTITLE 1,Create research_opportunities Table
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# ── Create research_opportunities table ──
ro_schema = StructType([
    StructField("name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("field", StringType(), True),
    StructField("eligibility", StringType(), True),
    StructField("url", StringType(), True),
    StructField("description", StringType(), True),
])

ro_df = spark.createDataFrame(research_opportunities, schema=ro_schema)
ro_df.createOrReplaceTempView("_research_opp_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.research_opportunities AS
SELECT * FROM _research_opp_temp
""")

print(f"Created workspace.default.research_opportunities with {len(research_opportunities)} rows")
display(spark.table("workspace.default.research_opportunities"))

# COMMAND ----------

# DBTITLE 1,Create career_resources Table
# ── Create career_resources table ──
cr_schema = StructType([
    StructField("name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("type", StringType(), True),
    StructField("url", StringType(), True),
    StructField("description", StringType(), True),
])

cr_df = spark.createDataFrame(career_resources, schema=cr_schema)
cr_df.createOrReplaceTempView("_career_res_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.career_resources AS
SELECT * FROM _career_res_temp
""")

print(f"Created workspace.default.career_resources with {len(career_resources)} rows")
display(spark.table("workspace.default.career_resources"))

# COMMAND ----------

# DBTITLE 1,Create career_events Table
# ── Create career_events table ──
ce_schema = StructType([
    StructField("name", StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("audience", StringType(), True),
    StructField("date_info", StringType(), True),
    StructField("url", StringType(), True),
    StructField("description", StringType(), True),
])

ce_df = spark.createDataFrame(career_events, schema=ce_schema)
ce_df.createOrReplaceTempView("_career_events_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.career_events AS
SELECT * FROM _career_events_temp
""")

print(f"Created workspace.default.career_events with {len(career_events)} rows")
display(spark.table("workspace.default.career_events"))

# COMMAND ----------

# DBTITLE 1,Create career_pathways Table
# ── Create career_pathways table ──
# Flatten arrays into comma-separated strings for Delta table storage
cp_data_flat = []
for p in career_pathways:
    cp_data_flat.append({
        "pathway": p["pathway"],
        "description": p["description"],
        "careers": ", ".join(p["careers"]),
        "resources": ", ".join(p["resources"]),
        "url": p["url"],
    })

cp_schema = StructType([
    StructField("pathway", StringType(), True),
    StructField("description", StringType(), True),
    StructField("careers", StringType(), True),
    StructField("resources", StringType(), True),
    StructField("url", StringType(), True),
])

cp_df = spark.createDataFrame(cp_data_flat, schema=cp_schema)
cp_df.createOrReplaceTempView("_career_pathways_temp")

spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.default.career_pathways AS
SELECT * FROM _career_pathways_temp
""")

print(f"Created workspace.default.career_pathways with {len(cp_data_flat)} rows")
display(spark.table("workspace.default.career_pathways"))

# COMMAND ----------

# DBTITLE 1,Recommendation Section
# MAGIC %md
# MAGIC ## Step 3: Recommendation Engine
# MAGIC Natural language recommendation system for research and career opportunities.
# MAGIC
# MAGIC ### Function Signatures for App Integration:
# MAGIC * `recommend_professional(query: str) -> list[dict]` — Main entry point (searches both research and career)
# MAGIC * `recommend_research(query: str, field: str = None) -> list[dict]`
# MAGIC * `recommend_career(query: str, type: str = None) -> list[dict]`
# MAGIC * `recommend_career_pathway(query: str) -> list[dict]`

# COMMAND ----------

# DBTITLE 1,Recommendation Helpers
import re

# Load data from Delta tables into pandas for fast lookup
research_pdf = spark.table("workspace.default.research_opportunities").toPandas()
resources_pdf = spark.table("workspace.default.career_resources").toPandas()
events_pdf = spark.table("workspace.default.career_events").toPandas()
pathways_pdf = spark.table("workspace.default.career_pathways").toPandas()

# Field-of-study synonyms
FIELD_SYNONYMS = {
    "biomedical": ["biomedical", "biomed", "biology", "life science", "neuro", "molecular", "cell"],
    "physics": ["physics", "neutrino", "quantum", "astronomy"],
    "data science": ["data science", "data analytics", "machine learning", "ai", "artificial intelligence", "dspg"],
    "engineering": ["engineering", "mechanical", "electrical", "civil", "industrial", "aerospace", "ictas"],
    "environmental": ["environmental", "natural resources", "cnre", "global change", "sustainability", "ecology"],
    "health sciences": ["health", "medical", "nursing", "public health", "ihsr", "clinical"],
    "computer science": ["computer science", "computer", "software", "programming", "coding", "cybersecurity", "it"],
    "business": ["business", "finance", "management", "marketing", "accounting", "consulting"],
    "arts": ["art", "design", "music", "theater", "creative", "media", "communication"],
    "social sciences": ["psychology", "sociology", "political science", "economics", "anthropology"],
}

# Opportunity type synonyms
TYPE_SYNONYMS = {
    "research": ["research", "lab", "study", "investigate"],
    "internship": ["internship", "intern", "co-op", "ceip", "work experience"],
    "full-time": ["full-time", "full time", "job", "career", "hire", "employment"],
    "fellowship": ["fellowship", "fellow", "scholar", "award"],
    "funding": ["funding", "grant", "fund", "financial support", "stipend"],
    "summer": ["summer", "surf"],
    "career fair": ["career fair", "fair", "expo", "recruiting"],
    "resume": ["resume", "cv", "cover letter"],
    "interview": ["interview", "mock interview"],
    "advising": ["advising", "advisor", "coaching", "counsel"],
}

def parse_fields(query: str) -> list:
    """Extract field-of-study interests from a natural language query."""
    query_lower = query.lower()
    found = []
    for field, synonyms in FIELD_SYNONYMS.items():
        if any(syn in query_lower for syn in synonyms):
            found.append(field)
    return found

def parse_opportunity_type(query: str) -> list:
    """Extract opportunity types from a natural language query."""
    query_lower = query.lower()
    found = []
    for opt_type, synonyms in TYPE_SYNONYMS.items():
        if any(syn in query_lower for syn in synonyms):
            found.append(opt_type)
    return found

print("Helpers loaded: field parser, opportunity type parser")

# COMMAND ----------

# DBTITLE 1,Build Recommendation Functions
def recommend_research(query: str, field: str = None) -> list:
    """
    Find research opportunities matching the student's query and field of interest.
    
    Args:
        query: Natural language query from student
        field: Optional field-of-study filter
    
    Returns:
        List of dicts with matching research opportunities, sorted by relevance
    """
    fields = [field] if field else parse_fields(query)
    opt_types = parse_opportunity_type(query)
    
    filtered = research_pdf.copy()
    
    # Filter by field if specified
    if fields:
        mask = filtered["field"].apply(
            lambda x: any(f.lower() in x.lower() for f in fields) or x == "All Fields" or x == "Multiple Fields"
        )
        filtered = filtered[mask]
    
    # Score items by keyword matches
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Build field keyword set
    field_words = set()
    for f in fields:
        field_words.update(FIELD_SYNONYMS.get(f, []))
    
    results = []
    for _, row in filtered.iterrows():
        score = 0
        name_lower = row["name"].lower()
        desc_lower = row["description"].lower()
        cat_lower = row["category"].lower()
        field_lower = row["field"].lower()
        
        # Direct word match
        for word in query_words:
            if len(word) > 2:
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1
                if word in cat_lower:
                    score += 2
        
        # Field match
        for fword in field_words:
            if fword in name_lower or fword in field_lower or fword in desc_lower:
                score += 5
        
        # If no keywords matched but we have field filter, still include
        if score == 0 and fields:
            score = 1
        
        if score > 0:
            results.append({
                "name": row["name"],
                "category": row["category"],
                "field": row["field"],
                "eligibility": row["eligibility"],
                "description": row["description"],
                "url": row["url"],
                "match_score": score,
                "source": "research",
            })
    
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:10]


def recommend_career(query: str, type: str = None) -> list:
    """
    Find career resources and events matching the student's query.
    
    Args:
        query: Natural language query from student
        type: Optional opportunity type filter (internship, resume, interview, etc.)
    
    Returns:
        List of dicts with matching career resources and events
    """
    opt_types = [type] if type else parse_opportunity_type(query)
    
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Build type keyword set
    type_words = set()
    for t in opt_types:
        type_words.update(TYPE_SYNONYMS.get(t, []))
    
    results = []
    
    # Search career resources
    for _, row in resources_pdf.iterrows():
        score = 0
        name_lower = row["name"].lower()
        desc_lower = row["description"].lower()
        cat_lower = row["category"].lower()
        
        for word in query_words:
            if len(word) > 2:
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1
                if word in cat_lower:
                    score += 5
        
        for tw in type_words:
            if tw in name_lower or tw in cat_lower or tw in desc_lower:
                score += 5
        
        if score > 0:
            results.append({
                "name": row["name"],
                "category": row["category"],
                "type": row["type"],
                "description": row["description"],
                "url": row["url"],
                "match_score": score,
                "source": "career_resource",
            })
    
    # Search career events
    for _, row in events_pdf.iterrows():
        score = 0
        name_lower = row["name"].lower()
        desc_lower = row["description"].lower()
        etype_lower = row["event_type"].lower()
        
        for word in query_words:
            if len(word) > 2:
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1
                if word in etype_lower:
                    score += 5
        
        for tw in type_words:
            if tw in name_lower or tw in etype_lower or tw in desc_lower:
                score += 5
        
        if score > 0:
            results.append({
                "name": row["name"],
                "event_type": row["event_type"],
                "audience": row["audience"],
                "date_info": row["date_info"],
                "description": row["description"],
                "url": row["url"],
                "match_score": score,
                "source": "career_event",
            })
    
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:10]


def recommend_career_pathway(query: str) -> list:
    """
    Find career pathways matching the student's interests.
    
    Args:
        query: Natural language query from student
    
    Returns:
        List of dicts with matching career pathways
    """
    fields = parse_fields(query)
    query_lower = query.lower()
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Build field keyword set
    field_words = set()
    for f in fields:
        field_words.update(FIELD_SYNONYMS.get(f, []))
    
    results = []
    for _, row in pathways_pdf.iterrows():
        score = 0
        pathway_lower = row["pathway"].lower()
        desc_lower = row["description"].lower()
        careers_lower = row["careers"].lower()
        
        for word in query_words:
            if len(word) > 2:
                if word in pathway_lower:
                    score += 5
                if word in desc_lower:
                    score += 1
                if word in careers_lower:
                    score += 3
        
        for fword in field_words:
            if fword in pathway_lower or fword in desc_lower or fword in careers_lower:
                score += 7
        
        if score > 0:
            results.append({
                "name": row["pathway"],
                "pathway": row["pathway"],
                "description": row["description"],
                "careers": row["careers"],
                "resources": row["resources"],
                "url": row["url"],
                "match_score": score,
                "source": "career_pathway",
            })
    
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:5]


def recommend_professional(query: str) -> list:
    """
    Main entry point: Find professional opportunities matching the query.
    
    Searches research opportunities, career resources, events, and pathways.
    
    Args:
        query: Natural language query from student
    
    Returns:
        List of dicts with matching opportunities, sorted by relevance
    
    Example queries:
        "I want to do research in biomedical engineering"
        "I need help with my resume"
        "Are there any career fairs coming up?"
        "I'm looking for a summer internship in data science"
        "What career paths can I pursue with a CS degree?"
    """
    research_results = recommend_research(query)
    career_results = recommend_career(query)
    pathway_results = recommend_career_pathway(query)
    
    all_results = research_results + career_results + pathway_results
    all_results.sort(key=lambda x: x["match_score"], reverse=True)
    
    return all_results


print("Recommendation functions ready!")
print(f"  - {len(research_pdf)} research opportunities")
print(f"  - {len(resources_pdf)} career resources")
print(f"  - {len(events_pdf)} career events")
print(f"  - {len(pathways_pdf)} career pathways")

# COMMAND ----------

# DBTITLE 1,Test Section
# MAGIC %md
# MAGIC ## Step 4: Test the Recommendation System
# MAGIC Run example queries to verify the Professical Helper works!

# COMMAND ----------

# DBTITLE 1,Run Test Examples
# Example queries demonstrating the professional opportunities recommendation system
example_queries = [
    "I want to do research in biomedical engineering",
    "I need help with my resume",
    "Are there any career fairs coming up?",
    "I'm looking for a summer internship in data science",
    "What career paths can I pursue with a computer science degree?",
    "I need interview preparation help",
    "I want to find a fellowship in physics",
    "How do I get started with undergraduate research?",
]

for query in example_queries:
    print(f'\nProfessical Query: "{query}"')
    print("=" * 70)
    
    results = recommend_professional(query)
    
    if results:
        for i, result in enumerate(results[:5], 1):
            source_tag = result["source"].replace("_", " ").title()
            print(f"\n  #{i} {result['name']} [{source_tag}]")
            if result["source"] == "research":
                print(f"     Category: {result['category']} | Field: {result['field']} | Eligibility: {result['eligibility']}")
                print(f"     Description: {result['description']}")
                print(f"     URL: {result['url']}")
            elif result["source"] == "career_resource":
                print(f"     Category: {result['category']} | Type: {result['type']}")
                print(f"     Description: {result['description']}")
                print(f"     URL: {result['url']}")
            elif result["source"] == "career_event":
                print(f"     Type: {result['event_type']} | Audience: {result['audience']} | Date: {result['date_info']}")
                print(f"     Description: {result['description']}")
                print(f"     URL: {result['url']}")
            elif result["source"] == "career_pathway":
                print(f"     Pathway: {result['pathway']}")
                print(f"     Description: {result['description']}")
                print(f"     Careers: {result['careers']}")
            print(f"     Match score: {result['match_score']}")
    else:
        print("  No matches found.")
    print("\n" + "-" * 70)

print("\nTesting complete! Professical Helper is ready to integrate into the app.")

# COMMAND ----------

# DBTITLE 1,ACTION: Grant Julian table permissions
# MAGIC %sql
# MAGIC -- ACTION NEEDED: Grant Julian access so he can integrate this into the app!
# MAGIC GRANT SELECT ON TABLE workspace.default.research_opportunities TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.career_resources TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.career_events TO `julianmiller@vt.edu`;
# MAGIC GRANT SELECT ON TABLE workspace.default.career_pathways TO `julianmiller@vt.edu`;