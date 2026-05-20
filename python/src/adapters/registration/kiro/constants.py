"""Kiro registration constants."""

FIRST_NAMES = [
    "James", "Robert", "John", "Michael", "David",
    "William", "Richard", "Maria", "Elizabeth", "Jennifer",
    "Linda", "Barbara", "Susan", "Jessica",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Wilson", "Anderson", "Thomas", "Taylor",
]

OIDC_BASE = "https://oidc.us-east-1.amazonaws.com"
PORTAL_BASE = "https://portal.sso.us-east-1.amazonaws.com"
START_URL = "https://view.awsapps.com/start"

SCOPES = [
    "codewhisperer:analysis",
    "codewhisperer:completions",
    "codewhisperer:conversations",
    "codewhisperer:taskassist",
    "codewhisperer:transformations",
]
