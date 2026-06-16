import os
from dotenv import load_dotenv

load_dotenv()

# GROQ
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Gmail SMTP
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "komirishettyvinay98@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT", "komirishettyvinay98@gmail.com")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESUME_PATH = os.path.join(BASE_DIR, "resume", "Vinay_Komirishetty_Resume.pdf")

# Google Sheets storage
SPREADSHEET_ID          = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")   # JSON string (Streamlit Cloud)
GOOGLE_CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json") # local file fallback

# Job search
SEARCH_KEYWORDS = [
    "Data Engineer",
    "Senior Data Engineer",
]
LOCATION = "Canada"
HOURS_OLD = 48       # fetch jobs posted in last 48 hours
MAX_JOBS_PER_SOURCE = 50

# ATS score thresholds
TIER_STRONG = 75
TIER_MAYBE = 50      # below this = Skip

# Companies on Greenhouse (public API — apply links go directly to company career pages)
GREENHOUSE_COMPANIES = [
    # ── Canadian tech ──────────────────────────────────────────────────────
    "shopify", "wealthsimple", "clio", "hootsuite", "ada-support",
    "cohere", "absorb", "vidyard", "properly", "ritual",
    "borrowell", "unbounce", "tulip-retail", "miovision",
    "ecobee", "clutch", "eventmobi", "mejuri", "clearco",
    "trulioo", "league", "kijiji", "tailscale", "certn",
    "nuvei", "tucows", "mds", "financeit", "hyper",
    "tenstorrent", "layer6", "coveo", "pelmorex",
    # ── Data / Analytics platforms ─────────────────────────────────────────
    "confluent", "databricks", "dbt-labs", "fivetran", "hightouch",
    "starburst", "prefect", "dagster-labs", "monte-carlo-data",
    "astronomer", "singlestore", "cockroachdb", "airbyte",
    "rudderstack", "lightdash", "metabase", "atlan", "select-star",
    "datafold", "recce", "openmetadata",
    # ── Cloud / Infra ──────────────────────────────────────────────────────
    "hashicorp", "elastic", "mongodb", "cloudflare", "pagerduty",
    "datadog", "grafana-labs", "newrelic", "honeycomb-io",
    "temporalio", "redpanda-data",
    # ── Global tech hiring in Canada ───────────────────────────────────────
    "hubspot", "zendesk", "twilio", "squarespace", "brex",
    "figma", "notion", "linear", "vercel",
    "stripe", "plaid", "gusto", "rippling", "lattice",
    "roblox", "unity-technologies", "epic-games",
    "benchling", "duolingo", "canva",
]

# Companies on Lever (public API — apply links go directly to company career pages)
LEVER_COMPANIES = [
    # ── Canadian ───────────────────────────────────────────────────────────
    "1password", "freshbooks", "benevity", "hopper",
    "dapper-labs", "koho", "thinkific", "jobber",
    "vendasta", "achievers", "d2l", "procurify",
    "reliq-health", "snapcommerce", "wello", "borrowell",
    "clutch-technologies", "dialog", "planswell",
    # ── Global with Canadian offices / remote-friendly ─────────────────────
    "netflix", "dropbox", "reddit", "coinbase",
    "amplitude", "mixpanel", "census", "meltano",
    "retool", "launchdarkly", "descript", "loom",
    "mercury", "remote", "deel", "oyster",
    "klaviyo", "segment", "heap",
    "anomalo", "acceldata", "validio",
]
