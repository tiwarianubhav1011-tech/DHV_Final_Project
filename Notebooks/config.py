#!/usr/bin/env python3
"""
Configuration, file paths, and mapping dictionaries for the NIRF 2017-2025
Data Cleaning and Institute Unification pipeline.
"""

import os
import pandas as pd

# ── File Paths ─────────────────────────────────────────────────────────────
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_RAW = os.path.join(WORK_DIR, "nirf_2017_2025_raw.csv")
UPLOADED_RAW = os.path.join(
    os.path.expanduser("~"),
    ".gemini/antigravity/brain/c643ea25-90bc-4f06-93d6-48df47469915/"
    ".user_uploaded/media_1793905019588_aadb4315.csv",
)
RAW_INPUT = LOCAL_RAW if os.path.exists(LOCAL_RAW) else UPLOADED_RAW
CLEANED_CSV = os.path.join(WORK_DIR, "nirf_2017_2025_cleaned.csv")
UNIFIED_CSV = os.path.join(WORK_DIR, "nirf_2017_2025_unified.csv")
MAPPING_CSV = os.path.join(WORK_DIR, "institute_id_mapping.csv")
CLEANING_LOG = os.path.join(WORK_DIR, "cleaning_log.txt")
MATCHING_LOG = os.path.join(WORK_DIR, "matching_log.txt")

# ── Column Definitions ─────────────────────────────────────────────────────
SCORE_COLS = ["Score", "TLR", "RPC", "GO", "OI", "Perception"]

CLEANED_COL_ORDER = [
    "Year", "Category",
    "Institute_ID", "Base_ID",
    "Name", "Name_Standardized", "Name_Display",
    "City", "State",
    "Rank", "Score",
    "TLR", "RPC", "GO", "OI", "Perception",
    "Rank_Withdrawn", "Scores_Missing",
    "Has_Rank_Tie", "In_Top100", "In_Top50",
]

UNIFIED_COL_ORDER = [
    "Year", "Category", "Unified_ID", "Name_Unified", "Name_Display",
    "City_Unified", "State_Unified",
    "Institute_ID", "Base_ID", "Name", "City", "State",
    "Rank", "Score", "TLR", "RPC", "GO", "OI", "Perception",
    "Rank_Withdrawn", "Scores_Missing", "Has_Rank_Tie", "In_Top100", "In_Top50",
]

# ── Stage 1: Cleaning Maps ─────────────────────────────────────────────────
STATE_MAP = {
    "Jammu And Kashmir": "Jammu and Kashmir",
    "Pondicherry": "Puducherry",
}

CATEGORY_MAP = {
    "OPENUNIVERSITY": "Open University",
    "SKILLUNIVERSITY": "Skill University",
    "STATEPUBLICUNIVERSITY": "State Public University",
    "SDGInstitutions": "SDG Institutions",
}

CITY_CLEAN_MAP = {
    # Official renames
    "Calcutta": "Kolkata",
    "Calcutta-16": "Kolkata",
    "Mysore": "Mysuru",
    "Mangalore": "Mangaluru",
    "Belgaum": "Belagavi",
    "Ootacamund": "Ooty",
    "Nilgiri": "Ooty",
    "Baroda": "Vadodara",
    # Misspellings
    "Bhubneshwar": "Bhubaneswar",
    "Bhuabaneswar": "Bhubaneswar",
    "Bengluru": "Bengaluru",
    "Mengaluru": "Mangaluru",
    # Casing
    "HYDERABAD": "Hyderabad",
    "MEERUT": "Meerut",
    # Placeholder
    "Select City": pd.NA,
}

# ── Stage 2: Unification Normalization & Overrides ─────────────────────────
ABBREVIATIONS = {
    r"\biit\b": "indian institute of technology",
    r"\bnit\b": "national institute of technology",
    r"\biim\b": "indian institute of management",
    r"\biiit\b": "indian institute of information technology",
    r"\biiser\b": "indian institute of science education and research",
    r"\baiims\b": "all india institute of medical sciences",
    r"\bniper\b": "national institute of pharmaceutical education and research",
    r"\biisc\b": "indian institute of science",
    r"\bbhu\b": "banaras hindu university",
    r"\bism\b": "indian school of mines",
    r"\bamu\b": "aligarh muslim university",
    r"\bjnu\b": "jawaharlal nehru university",
    r"\bdu\b": "university of delhi",
}

CAMPUS_CODES = {
    "b": "bombay", "d": "delhi", "m": "madras", "k": "kanpur", "kgp": "kharagpur",
    "r": "roorkee", "g": "guwahati", "h": "hyderabad",
}

CITY_ALIASES = {
    "trichur": "thrissur", "calicut": "kozhikode", "trivandrum": "thiruvananthapuram",
    "tiruchirapalli": "tiruchirappalli", "trichy": "tiruchirappalli",
    "bangalore": "bengaluru", "bengluru": "bengaluru", "mysore": "mysuru",
    "mangalore": "mangaluru", "belgaum": "belagavi", "calcutta": "kolkata",
    "bombay": "mumbai", "madras": "chennai", "cochin": "kochi", "quilon": "kollam",
    "visakapatnam": "visakhapatnam", "vizag": "visakhapatnam",
    "gurgaon": "gurugram", "new delhi": "delhi", "allahabad": "prayagraj",
    "kurushetra": "kurukshetra", "hissar": "hisar", "pondicherry": "puducherry",
    "baroda": "vadodara", "poona": "pune", "ootacamund": "ooty", "nilgiri": "ooty",
    "bhubneshwar": "bhubaneswar", "Bhuabaneswar": "bhubaneswar", "bhuabaneswar": "bhubaneswar",
    "kanchipuram": "kancheepuram", "virudhnagar": "virudhunagar",
    "gautam budh nagar": "greater noida", "noida": "greater noida",
}

NOISE_PATTERNS = [
    r"\bdeemed[\s-]*to[\s-]*be[\s-]*(a\s+)?university\b",
    r"\bdeemed university\b", r"\bdeemed\b",
    r"\bautonomous\b", r"\bformerly\b.*$",
    r"\bthe\b",
]

GENERIC_PREFIXES = {
    "indian institute of technology", "national institute of technology",
    "indian institute of management", "indian institute of information technology",
    "indian institute of science education and research",
    "all india institute of medical sciences", "university", "college",
    "govt college", "govt arts college",
    "national institute of pharmaceutical education and research",
}

# 2017 Base_ID → 2018+ Base_ID
MANUAL_2017 = {
    "U-624": "U-0363",          # Siksha'O' Anusandhan University → Siksha 'O' Anusandhan
    "U-661": "I-1486",          # Sri Ramachandra University → Sri Ramachandra Inst. of Higher Edu & Research
    "U-299": "U-0222",          # Jagadguru Sri Shivarathreeshwara Univ → JSS Academy of Higher Edu & Research
    "U-2813959492": "I-1480",   # Thapar University → Thapar Institute of Engg & Tech
    "U-18342": "U-0463",        # Madurai Kamraj → Madurai Kamaraj University
    "U-18607": "U-0251",        # Calicut University
    "U-15637": "S-132",         # XLRI → XLRI - Xavier School of Management
    "U-NEW5": "S-8931",         # NITIE Mumbai → IIM Mumbai (renamed 2023)
    "U-18710": "S-8937",        # Rajiv Gandhi IIM → IIM Shillong
    "U-18257": "U-0105",        # IIIT New Delhi (IIIT Delhi) → Indraprastha Institute of Information Technology
    "U-21078": "U-0329",        # Symbiosis International University → Symbiosis International
    "U-18407": "U-0239",        # NITTE University → NITTE
    "U-17868": "I-1280",        # Dept. of Pharma Sciences, MDU → Maharshi Dayanand University (Pharmacy)
    "U-17931": "U-0143",        # Faculty of Tech & Engg, MSU Baroda → Maharaja Sayajirao University (Engineering)
    "U-18023": "U-0078",        # University Institute of Pharma Sciences → Panjab University (Pharmacy)
    "U-2809541361": "U-1257",   # College of Engineering, Pune → COEP Technological University
    "C-29130": "C-6401",        # Shaheed Bhagat Singh College (Evening Classes) → SBSC (Evening)
    "U-12411": "C-16547",       # Sri Sai Ram Engg College → Sri Sairam Engg College
    "U-216": "U-0162",          # Guru Jambeshwar → Guru Jambheshwar Univ of Sci & Tech
    "C-19427": "C-43975",       # Justice Baseer/Basher Ahmed Sayeed College
}

# 2018+ Base_ID → canonical 2018+ Base_ID (same institute, ID changed)
MANUAL_POST = {
    "C-41593": "U-1257",        # College of Engineering Pune → COEP Technological University
}

# (2017 Base_ID, 2018+ Base_ID) pairs that look alike but are DIFFERENT institutes
REJECT_PAIRS = {
    ("U-570", "U-0392"),        # Rajasthan University ≠ Central University of Rajasthan
    ("U-18446", "U-0392"),
    ("U-18551", "U-0524"),      # Allahabad ≠ Lucknow
    ("U-18356", "C-43760"),     # Mahatma Gandhi University ≠ Mahatma Gandhi College
    ("U-N001", "U-0037"),       # Sri Krishnadevaraya ≠ Sri Venkateswara
    ("C-15615", "U-0473"),      # SRM Arts & Science College ≠ SRM IST
    ("U-11112", "U-0474"),      # Vel Tech ≠ Sathyabama
    ("C-30622", "C-43902"),     # Shasun Jain ≠ Ethiraj
    ("C-19380", "C-41100"),     # Sri Ramakrishna College of Arts & Sci FOR WOMEN ≠ the co-ed college
    ("U-2811763720", "N-354"),  # Xavier Inst. of Mgmt & Entrepreneurship (Bengaluru) ≠ XIMB (Bhubaneswar)
}

# Different institutes that share a name+city and must NEVER be merged inside 2018+
DO_NOT_MERGE_POST = {
    frozenset({"I-1093", "I-1256"}),   # NIET engineering vs NIET pharmacy institute
}

