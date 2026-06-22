import os
from dotenv import load_dotenv

load_dotenv()

# GROQ
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
# Free tier allows ~100k tokens/day on the 70b model. Score the highest-value
# jobs within this budget (quality-first); the rest are picked up next run.
GROQ_DAILY_TOKEN_BUDGET = 95000
# Seconds to wait between scoring calls — keeps us under the per-minute token
# limit (~12k TPM) so we sip gently instead of bursting all calls at once.
SCORE_DELAY_SECONDS = 10

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
# SEARCH_KEYWORDS — used as live search terms on LinkedIn/Indeed (keep narrow:
# each keyword is a separate scrape, so more = slower + more rate-limit risk).
SEARCH_KEYWORDS = [
    "Data Engineer",
    "Senior Data Engineer",
]
# DATA_ROLE_KEYWORDS — used to filter job TITLES from ATS boards (Greenhouse/
# Lever return a company's full job list, so a broad match here = more jobs).
DATA_ROLE_KEYWORDS = [
    "data engineer",
    "data developer",
    "analytics engineer",
    "data platform",
    "data infrastructure",
    "big data",
    "etl developer",
    "etl engineer",
    "data pipeline",
    "data warehouse",
    "datawarehouse",
    "data architect",
    "machine learning engineer",
    "ml engineer",
    "data ops",
    "dataops",
]
LOCATION = "Canada"
HOURS_OLD = 48       # fetch jobs posted in last 48 hours
MAX_JOBS_PER_SOURCE = 50

# Location filtering — shared by all ATS fetchers.
# A job is kept if its location matches a CANADA_HINT and no EXCLUDE_LOCATION.
CANADA_HINTS = {
    "canada", "canadian",
    # provinces + abbreviations
    "ontario", "quebec", "québec", "british columbia", "alberta",
    "manitoba", "saskatchewan", "nova scotia", "new brunswick",
    "newfoundland", "prince edward",
    ", on", ", qc", ", bc", ", ab", ", mb", ", sk", ", ns", ", nb",
    # major cities / tech hubs
    "toronto", "vancouver", "montreal", "montréal", "calgary", "ottawa",
    "edmonton", "winnipeg", "kitchener", "waterloo", "mississauga",
    "brampton", "hamilton", "halifax", "victoria", "markham", "vaughan",
    "burnaby", "gatineau", "kanata", "oakville", "saskatoon", "regina",
    "kelowna", "guelph", "london, on", "london, ontario",
}
EXCLUDE_LOCATIONS = {
    "united states", "usa", "u.s.", "us only", "us-based", "us based",
    "london, uk", "united kingdom", "uk only", "england",
    "australia", "india", "germany", "france", "brazil", "singapore",
    "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai",
    "ireland", "netherlands", "spain", "poland", "mexico", "philippines",
}

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
    # ── More Canadian companies ────────────────────────────────────────────
    "faire", "clearbanc", "instacart", "lyft", "pinterest",
    "samsara", "affirm", "doordash", "robinhood", "asana",
    "gitlab", "okta", "snowflake", "confluentinc", "anthropic",
    "openai", "scale", "ramp", "airtable", "webflow",
    "sentry", "render", "supabase", "planetscale", "neon",
    "modernhealth", "carta", "moderntreasury", "dbtlabs",
    "thoughtspot", "sigma-computing", "preset", "mode",
    "fullstory", "postman", "vanta", "drata",
    # ── Canadian scaleups ──────────────────────────────────────────────────
    "wave", "knak", "flipp", "sondermind", "wattpad",
    "later", "jane-app", "kira-systems", "deep-genomics",
    "blue-j", "ada", "sampler", "voiceflow", "cohere-ai",
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
    # ── More Lever-hosted companies ────────────────────────────────────────
    "plaid", "brex", "nuro", "scaleai", "huggingface",
    "wealthfront", "betterment", "chime", "upgrade",
    "faire", "ramp", "rippling", "gusto", "ironclad",
    "verkada", "samsara", "instabase", "writer",
    "cresta", "sourcegraph", "temporal", "convoy",
    "shippo", "rec-room", "fanatics", "attentive",
    "clari", "gong", "outreach", "chorus",
    "alloy", "ridgeline", "fundbox", "blend",
]
