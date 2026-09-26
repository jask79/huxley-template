"""
Trade compliance data and calculation functions for Sourcerer.

Provides US import compliance intelligence including:
  - Section 301 tariff rates by HS chapter (China -> US)
  - MFN (Most Favored Nation) base duty rates
  - Product category compliance requirements (FCC, CPSC, FDA, etc.)
  - Incoterms 2020 reference
  - Duty estimation functions

All data structures are pure constants. All functions are pure (no side effects,
no database access, no network calls).

Dependencies: None (stdlib only).
"""

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Section 321 De Minimis Threshold
# ---------------------------------------------------------------------------
DE_MINIMIS_THRESHOLD = 800  # USD — shipments under this value are duty-free

# ---------------------------------------------------------------------------
# Section 301 Tariffs (China -> US additional tariffs)
# ---------------------------------------------------------------------------
# HS 2-digit chapter -> Section 301 list assignment and additional tariff rate.
# These are ADDITIONAL tariffs on top of the standard MFN duty rate.
# Rates as of early 2024; some List 3/4A rates were reduced from 25% to 7.5%.
# WARNING: Rates may have changed. Post-May 2024 USTR increases raised solar
# panels (25%->50%), EVs (25%->100%), steel/aluminum (25%->50%), semiconductors
# (25%->50%), batteries (7.5%->25%). Verify current rates at hts.usitc.gov.

SECTION_301_TARIFFS: Dict[str, Dict[str, Any]] = {
    # List 1 — 25% additional tariff
    "84": {
        "list": "1", "rate": 0.25,
        "description": "Machinery, mechanical appliances",
        "notes": "Nuclear reactors, boilers, machinery, and mechanical appliances",
    },
    "85": {
        "list": "1", "rate": 0.25,
        "description": "Electrical machinery, equipment",
        "notes": "Electrical machinery and equipment, sound recorders/reproducers, TV",
    },
    "86": {
        "list": "1", "rate": 0.25,
        "description": "Railway/tramway locomotives, rolling stock",
        "notes": "Railway track fixtures and fittings; signal equipment",
    },
    "87": {
        "list": "1", "rate": 0.25,
        "description": "Vehicles other than railway/tramway",
        "notes": "Motor vehicles, bicycles, parts and accessories",
    },
    "88": {
        "list": "1", "rate": 0.25,
        "description": "Aircraft, spacecraft",
        "notes": "Aircraft, spacecraft, and parts thereof",
    },
    "90": {
        "list": "1", "rate": 0.25,
        "description": "Optical, photographic, measuring instruments",
        "notes": "Optical, photographic, cinematographic, measuring, checking instruments",
    },
    "91": {
        "list": "1", "rate": 0.25,
        "description": "Clocks and watches",
        "notes": "Clocks, watches, and parts thereof",
    },

    # List 2 — 25% additional tariff
    "39": {
        "list": "2", "rate": 0.25,
        "description": "Plastics and articles thereof",
        "notes": "Plastics and articles of plastics",
    },
    "72": {
        "list": "2", "rate": 0.25,
        "description": "Iron and steel",
        "notes": "Iron and steel base products",
    },
    "73": {
        "list": "2", "rate": 0.25,
        "description": "Iron/steel articles",
        "notes": "Articles of iron or steel",
    },
    "76": {
        "list": "2", "rate": 0.25,
        "description": "Aluminum and articles thereof",
        "notes": "Aluminum and articles of aluminum",
    },
    "28": {
        "list": "2", "rate": 0.25,
        "description": "Inorganic chemicals",
        "notes": "Inorganic chemicals; compounds of precious metals",
    },
    "29": {
        "list": "2", "rate": 0.25,
        "description": "Organic chemicals",
        "notes": "Organic chemicals",
    },

    # List 3 — reduced from 25% to 7.5%
    "42": {
        "list": "3", "rate": 0.075,
        "description": "Leather goods, handbags, travel goods",
        "notes": "Leather articles, saddlery, travel goods, handbags. Reduced from 25% to 7.5%.",
    },
    "61": {
        "list": "3", "rate": 0.075,
        "description": "Knitted or crocheted apparel",
        "notes": "Articles of apparel, knitted or crocheted. Reduced from 25% to 7.5%.",
    },
    "62": {
        "list": "3", "rate": 0.075,
        "description": "Woven apparel",
        "notes": "Articles of apparel, not knitted or crocheted. Reduced from 25% to 7.5%.",
    },
    "63": {
        "list": "3", "rate": 0.075,
        "description": "Other textile articles, worn clothing",
        "notes": "Other made-up textile articles; sets; worn clothing. Reduced to 7.5%.",
    },
    "64": {
        "list": "3", "rate": 0.075,
        "description": "Footwear, gaiters",
        "notes": "Footwear, gaiters, and the like. Reduced from 25% to 7.5%.",
    },
    "65": {
        "list": "3", "rate": 0.075,
        "description": "Headgear",
        "notes": "Headgear and parts thereof. Reduced from 25% to 7.5%.",
    },
    "94": {
        "list": "3", "rate": 0.075,
        "description": "Furniture, bedding, lighting",
        "notes": "Furniture, bedding, mattresses, lamps, prefab buildings. Reduced to 7.5%.",
    },
    "95": {
        "list": "3", "rate": 0.075,
        "description": "Toys, games, sports equipment",
        "notes": "Toys, games, and sports requisites. Reduced from 25% to 7.5%.",
    },
    "96": {
        "list": "3", "rate": 0.075,
        "description": "Miscellaneous manufactured articles",
        "notes": "Pens, buttons, lighters, combs, etc. Reduced from 25% to 7.5%.",
    },
    "66": {
        "list": "3", "rate": 0.075,
        "description": "Umbrellas, walking sticks",
        "notes": "Umbrellas, sun umbrellas, walking sticks. Reduced to 7.5%.",
    },

    # List 4A — 7.5% additional tariff
    "44": {
        "list": "4A", "rate": 0.075,
        "description": "Wood and articles of wood",
        "notes": "Wood and articles of wood; wood charcoal",
    },
    "69": {
        "list": "4A", "rate": 0.075,
        "description": "Ceramic products",
        "notes": "Ceramic products",
    },
    "70": {
        "list": "4A", "rate": 0.075,
        "description": "Glass and glassware",
        "notes": "Glass and glassware",
    },
    "48": {
        "list": "4A", "rate": 0.075,
        "description": "Paper, paperboard, articles",
        "notes": "Paper and paperboard; articles of paper pulp",
    },
    "68": {
        "list": "4A", "rate": 0.075,
        "description": "Stone, plaster, cement articles",
        "notes": "Articles of stone, plaster, cement, asbestos, mica",
    },
    "71": {
        "list": "4A", "rate": 0.075,
        "description": "Jewelry, precious metals/stones",
        "notes": "Natural/cultured pearls, precious stones, precious metals, jewelry",
    },
    "40": {
        "list": "4A", "rate": 0.075,
        "description": "Rubber and articles thereof",
        "notes": "Rubber and articles of rubber",
    },
    "83": {
        "list": "4A", "rate": 0.075,
        "description": "Base metal miscellaneous articles",
        "notes": "Miscellaneous articles of base metal",
    },
    "46": {
        "list": "4A", "rate": 0.075,
        "description": "Straw/basketwork manufactures",
        "notes": "Manufactures of straw, esparto, or other plaiting materials",
    },
}

# ---------------------------------------------------------------------------
# MFN (Most Favored Nation) Duty Rates — base rates before Section 301
# ---------------------------------------------------------------------------
# HS 2-digit chapter -> typical MFN duty range for consumer goods.
# "low" and "high" are the range across subheadings; "typical" is the
# most common rate for popular consumer items.

MFN_DUTY_RATES: Dict[str, Dict[str, Any]] = {
    "39": {
        "low": 0.0, "high": 0.065, "typical": 0.03,
        "description": "Plastics and articles thereof",
    },
    "40": {
        "low": 0.0, "high": 0.065, "typical": 0.025,
        "description": "Rubber and articles thereof",
    },
    "42": {
        "low": 0.03, "high": 0.20, "typical": 0.08,
        "description": "Leather goods, handbags, travel goods",
    },
    "44": {
        "low": 0.0, "high": 0.10, "typical": 0.032,
        "description": "Wood and articles of wood",
    },
    "48": {
        "low": 0.0, "high": 0.065, "typical": 0.0,
        "description": "Paper and paperboard articles",
    },
    "61": {
        "low": 0.10, "high": 0.32, "typical": 0.19,
        "description": "Knitted or crocheted apparel",
    },
    "62": {
        "low": 0.10, "high": 0.32, "typical": 0.19,
        "description": "Woven apparel",
    },
    "63": {
        "low": 0.06, "high": 0.14, "typical": 0.10,
        "description": "Other textile articles",
    },
    "64": {
        "low": 0.0, "high": 0.48, "typical": 0.12,
        "description": "Footwear",
    },
    "65": {
        "low": 0.0, "high": 0.08, "typical": 0.065,
        "description": "Headgear",
    },
    "69": {
        "low": 0.0, "high": 0.11, "typical": 0.06,
        "description": "Ceramic products",
    },
    "70": {
        "low": 0.0, "high": 0.10, "typical": 0.05,
        "description": "Glass and glassware",
    },
    "71": {
        "low": 0.0, "high": 0.14, "typical": 0.065,
        "description": "Jewelry, precious metals/stones",
    },
    "73": {
        "low": 0.0, "high": 0.08, "typical": 0.035,
        "description": "Iron/steel articles",
    },
    "76": {
        "low": 0.0, "high": 0.065, "typical": 0.03,
        "description": "Aluminum and articles thereof",
    },
    "83": {
        "low": 0.0, "high": 0.08, "typical": 0.04,
        "description": "Base metal miscellaneous articles",
    },
    "84": {
        "low": 0.0, "high": 0.05, "typical": 0.02,
        "description": "Machinery, mechanical appliances",
    },
    "85": {
        "low": 0.0, "high": 0.05, "typical": 0.02,
        "description": "Electrical machinery, equipment",
    },
    "87": {
        "low": 0.0, "high": 0.025, "typical": 0.025,
        "description": "Vehicles other than railway",
    },
    "90": {
        "low": 0.0, "high": 0.065, "typical": 0.02,
        "description": "Optical, measuring instruments",
    },
    "91": {
        "low": 0.0, "high": 0.065, "typical": 0.04,
        "description": "Clocks and watches",
    },
    "94": {
        "low": 0.0, "high": 0.05, "typical": 0.0,
        "description": "Furniture, bedding, lighting",
    },
    "95": {
        "low": 0.0, "high": 0.068, "typical": 0.0,
        "description": "Toys, games, sports equipment",
    },
    "96": {
        "low": 0.0, "high": 0.065, "typical": 0.05,
        "description": "Miscellaneous manufactured articles",
    },
}

# ---------------------------------------------------------------------------
# Product Compliance Requirements (US import)
# ---------------------------------------------------------------------------

PRODUCT_COMPLIANCE: Dict[str, Dict[str, Any]] = {
    "electronics": {
        "requirements": [
            {
                "agency": "FCC",
                "type": "Part 15 certification",
                "cost_range": "$5,000-15,000",
                "timeline_weeks": (4, 8),
                "mandatory": True,
            },
            {
                "agency": "UL",
                "type": "Safety listing (UL 60950/62368)",
                "cost_range": "$8,000-25,000",
                "timeline_weeks": (8, 16),
                "mandatory": False,
            },
            {
                "agency": "DOE",
                "type": "Energy efficiency (if applicable)",
                "cost_range": "$3,000-8,000",
                "timeline_weeks": (4, 8),
                "mandatory": False,
            },
        ],
        "labeling": [
            "FCC ID",
            "Country of origin",
            "Brand/importer name and address",
        ],
        "warnings": [
            "Products with WiFi/Bluetooth need FCC intentional radiator certification",
            "Lithium battery products require UN38.3 testing for shipping",
            "Products with AC mains connection need NRTL listing for most retailers",
        ],
    },
    "children_products": {
        "requirements": [
            {
                "agency": "CPSC",
                "type": "CPSIA compliance (lead/phthalate testing)",
                "cost_range": "$1,500-5,000",
                "timeline_weeks": (3, 6),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "ASTM F963 toy safety testing",
                "cost_range": "$3,000-10,000",
                "timeline_weeks": (4, 8),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "Children's Product Certificate (CPC)",
                "cost_range": "$500-1,000",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "Tracking label registration",
                "cost_range": "$0",
                "timeline_weeks": (1, 1),
                "mandatory": True,
            },
        ],
        "labeling": [
            "Age grading (CPSC guidelines)",
            "Choking hazard warning (if applicable)",
            "Tracking label (manufacturer, production date, batch)",
            "Country of origin",
            "Importer name and address",
        ],
        "warnings": [
            "ALL products for children under 12 must comply with CPSIA",
            "Third-party testing at CPSC-accepted lab required before import",
            "Small parts = choking hazard warning mandatory for ages 3+",
            "Failure to comply: product seizure, civil penalties up to $100K per violation",
        ],
    },
    "food_contact": {
        "requirements": [
            {
                "agency": "FDA",
                "type": "Food facility registration",
                "cost_range": "$0 (free registration)",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
            {
                "agency": "FDA",
                "type": "Food contact substance notification (FCN)",
                "cost_range": "$5,000-20,000",
                "timeline_weeks": (8, 26),
                "mandatory": False,
                "note": "Required only for novel materials not already FDA-authorized (most common food-contact materials are pre-authorized)",
            },
            {
                "agency": "California",
                "type": "Proposition 65 testing",
                "cost_range": "$2,000-5,000",
                "timeline_weeks": (2, 4),
                "mandatory": False,
            },
        ],
        "labeling": [
            "FDA compliant labeling",
            "Country of origin",
            "Material composition",
            "Prop 65 warning (if selling in California)",
        ],
        "warnings": [
            "FDA may detain food contact materials at port without prior notice",
            "Prop 65 litigation risk is high for California sales",
            "BPA-free claims must be substantiated",
        ],
    },
    "textiles": {
        "requirements": [
            {
                "agency": "FTC",
                "type": "Fiber content labeling (Textile Act)",
                "cost_range": "$0 (self-compliance)",
                "timeline_weeks": (0, 0),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "Flammability testing (16 CFR 1610/1611)",
                "cost_range": "$500-2,000",
                "timeline_weeks": (2, 4),
                "mandatory": True,
            },
            {
                "agency": "CBP",
                "type": "Country of origin marking",
                "cost_range": "$0 (self-compliance)",
                "timeline_weeks": (0, 0),
                "mandatory": True,
            },
        ],
        "labeling": [
            "Fiber content (generic fiber names, percentages)",
            "Country of origin",
            "Manufacturer/importer identity (RN or WPL number)",
            "Care instructions (ASTM D5489 symbols or text)",
        ],
        "warnings": [
            "Quota restrictions may apply to some textile categories",
            "AAFA (American Apparel & Footwear Association) Restricted Substances List",
            "Children's sleepwear has strict flammability requirements",
        ],
    },
    "cosmetics": {
        "requirements": [
            {
                "agency": "FDA",
                "type": "Cosmetic facility registration (MoCRA)",
                "cost_range": "$0 (free registration)",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
            {
                "agency": "FDA",
                "type": "Product listing (MoCRA)",
                "cost_range": "$0",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
            {
                "agency": "FDA",
                "type": "Safety substantiation",
                "cost_range": "$5,000-20,000",
                "timeline_weeks": (4, 12),
                "mandatory": True,
            },
        ],
        "labeling": [
            "Ingredient listing (INCI names, descending order)",
            "Net quantity",
            "Product identity",
            "Distributor/manufacturer name and address",
            "Warning statements (as applicable)",
        ],
        "warnings": [
            "Color additives must be FDA approved for intended use",
            "No pre-market approval, but FDA can take action on unsafe products",
            "SPF/sunscreen claims make a product a drug (requires NDA/monograph compliance)",
            "MoCRA (2022) added new mandatory requirements for cosmetic facilities",
        ],
    },
    "toys": {
        "requirements": [
            {
                "agency": "CPSC",
                "type": "ASTM F963 testing",
                "cost_range": "$3,000-10,000",
                "timeline_weeks": (4, 8),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "CPSIA lead/phthalate testing",
                "cost_range": "$1,500-5,000",
                "timeline_weeks": (3, 6),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "Children's Product Certificate (CPC)",
                "cost_range": "$500-1,000",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
        ],
        "labeling": [
            "Age grading",
            "Choking hazard warning",
            "Tracking label",
            "Country of origin",
            "Importer name and address",
        ],
        "warnings": [
            "ALL toys for children under 12 are children's products under CPSIA",
            "Magnets: CPSC high-powered magnet sets ban (ASTM F963-23)",
            "Battery compartments must be child-resistant",
        ],
    },
    "batteries": {
        "requirements": [
            {
                "agency": "UN",
                "type": "UN38.3 transport testing",
                "cost_range": "$3,000-8,000",
                "timeline_weeks": (4, 8),
                "mandatory": True,
            },
            {
                "agency": "DOT",
                "type": "Hazmat shipping compliance",
                "cost_range": "$500-2,000",
                "timeline_weeks": (1, 4),
                "mandatory": True,
            },
            {
                "agency": "IEC",
                "type": "IEC 62133 safety testing",
                "cost_range": "$5,000-15,000",
                "timeline_weeks": (6, 12),
                "mandatory": False,
            },
            {
                "agency": "UL",
                "type": "UL 2054/2580 listing",
                "cost_range": "$8,000-20,000",
                "timeline_weeks": (8, 16),
                "mandatory": False,
            },
        ],
        "labeling": [
            "UN38.3 test summary (shipped with product)",
            "Battery chemistry and capacity",
            "Warning labels per DOT requirements",
            "Country of origin",
        ],
        "warnings": [
            "Lithium batteries are classified as dangerous goods for shipping",
            "Air freight has strict limits on lithium battery quantities",
            "Many carriers refuse lithium batteries without proper documentation",
            "State laws (e.g. California) may have additional requirements",
        ],
    },
    "supplements": {
        "requirements": [
            {
                "agency": "FDA",
                "type": "Dietary supplement facility registration",
                "cost_range": "$0",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
            {
                "agency": "FDA",
                "type": "cGMP compliance (21 CFR 111)",
                "cost_range": "$10,000-50,000",
                "timeline_weeks": (12, 52),
                "mandatory": True,
            },
            {
                "agency": "FDA",
                "type": "New Dietary Ingredient (NDI) notification",
                "cost_range": "$50,000-200,000",
                "timeline_weeks": (26, 52),
                "mandatory": False,
            },
        ],
        "labeling": [
            "Supplement Facts panel",
            "Ingredient list (including other ingredients)",
            "Net quantity",
            "Manufacturer/distributor name and address",
            "FDA disclaimer statement",
        ],
        "warnings": [
            "Must NOT make disease claims (drug claims trigger NDA requirement)",
            "Import alerts: FDA frequently detains supplement imports",
            "Third-party testing (NSF, USP) strongly recommended for market credibility",
            "Prop 65 heavy metal testing recommended for California sales",
        ],
    },
    "jewelry": {
        "requirements": [
            {
                "agency": "CPSC",
                "type": "Lead content testing (children's jewelry: 100ppm)",
                "cost_range": "$500-2,000",
                "timeline_weeks": (2, 4),
                "mandatory": True,
            },
            {
                "agency": "CPSC",
                "type": "Cadmium testing (children's jewelry)",
                "cost_range": "$500-1,500",
                "timeline_weeks": (2, 4),
                "mandatory": True,
            },
            {
                "agency": "California",
                "type": "Proposition 65 (lead/cadmium/nickel)",
                "cost_range": "$1,000-3,000",
                "timeline_weeks": (2, 4),
                "mandatory": False,
            },
        ],
        "labeling": [
            "Country of origin",
            "Metal content (if making precious metal claims)",
            "Karat marking (FTC guidelines for gold)",
            "Importer name",
        ],
        "warnings": [
            "Children's jewelry has strict 100ppm total lead limit",
            "Nickel limits apply for EU sales (REACH regulation)",
            "Prop 65 is the top litigation risk for jewelry in California",
        ],
    },
    "general_consumer": {
        "requirements": [
            {
                "agency": "CBP",
                "type": "Country of origin marking (19 CFR 134)",
                "cost_range": "$0 (self-compliance)",
                "timeline_weeks": (0, 0),
                "mandatory": True,
            },
            {
                "agency": "CBP",
                "type": "Importer of record / customs bond",
                "cost_range": "$250-500/year (continuous bond)",
                "timeline_weeks": (1, 2),
                "mandatory": True,
            },
        ],
        "labeling": [
            "Country of origin (indelible, conspicuous, in English)",
            "Importer/distributor name and address",
        ],
        "warnings": [
            "Country of origin marking is required on all imported goods",
            "Mislabeled goods subject to 10% marking duties + possible seizure",
        ],
    },
}

# ---------------------------------------------------------------------------
# Incoterms 2020
# ---------------------------------------------------------------------------

INCOTERMS: Dict[str, Dict[str, str]] = {
    "EXW": {
        "name": "Ex Works",
        "risk_transfers": "at seller's premises",
        "seller_pays": "nothing (goods made available at their premises)",
        "buyer_pays": "all transport, insurance, export/import clearance, duties",
        "modes": "any",
        "use_when": "buyer has strong logistics capability and local agent in origin country",
        "risk_level": "high_for_buyer",
    },
    "FCA": {
        "name": "Free Carrier",
        "risk_transfers": "when goods delivered to carrier at named place",
        "seller_pays": "delivery to carrier, export clearance",
        "buyer_pays": "main carriage, import clearance, duties",
        "modes": "any",
        "use_when": "containerized cargo; buyer arranges main transport",
        "risk_level": "moderate_for_buyer",
    },
    "FAS": {
        "name": "Free Alongside Ship",
        "risk_transfers": "when goods placed alongside vessel at port",
        "seller_pays": "transport to port, export clearance",
        "buyer_pays": "loading, ocean freight, import clearance, duties",
        "modes": "sea/inland waterway only",
        "use_when": "bulk or heavy cargo; buyer has freight contract",
        "risk_level": "moderate_for_buyer",
    },
    "FOB": {
        "name": "Free On Board",
        "risk_transfers": "when goods loaded on vessel at port of shipment",
        "seller_pays": "transport to port, loading, export clearance",
        "buyer_pays": "ocean freight, insurance, import clearance, duties",
        "modes": "sea/inland waterway only",
        "use_when": "most common for China sourcing. Good balance of cost visibility.",
        "risk_level": "moderate_for_buyer",
    },
    "CFR": {
        "name": "Cost and Freight",
        "risk_transfers": "when goods loaded on vessel (risk) but seller pays freight",
        "seller_pays": "transport to port, loading, ocean freight, export clearance",
        "buyer_pays": "insurance, import clearance, duties, destination transport",
        "modes": "sea/inland waterway only",
        "use_when": "seller has better freight rates; buyer wants to avoid freight negotiation",
        "risk_level": "moderate_for_buyer",
    },
    "CIF": {
        "name": "Cost, Insurance and Freight",
        "risk_transfers": "when goods loaded on vessel (risk) but seller pays freight+insurance",
        "seller_pays": "transport to port, loading, ocean freight, minimum insurance, export clearance",
        "buyer_pays": "import clearance, duties, destination transport",
        "modes": "sea/inland waterway only",
        "use_when": "common for first-time importers. Simple — seller handles most logistics.",
        "risk_level": "low_for_buyer",
    },
    "CPT": {
        "name": "Carriage Paid To",
        "risk_transfers": "when goods delivered to first carrier (risk) but seller pays carriage",
        "seller_pays": "carriage to named destination, export clearance",
        "buyer_pays": "insurance, import clearance, duties",
        "modes": "any",
        "use_when": "multimodal transport; air freight or containerized cargo",
        "risk_level": "moderate_for_buyer",
    },
    "CIP": {
        "name": "Carriage and Insurance Paid To",
        "risk_transfers": "when goods delivered to first carrier (risk) but seller pays carriage+insurance",
        "seller_pays": "carriage to destination, insurance (110% all-risks), export clearance",
        "buyer_pays": "import clearance, duties",
        "modes": "any",
        "use_when": "multimodal; buyer wants seller to handle insurance (Incoterms 2020: all-risks minimum)",
        "risk_level": "low_for_buyer",
    },
    "DAP": {
        "name": "Delivered At Place",
        "risk_transfers": "when goods available for unloading at destination",
        "seller_pays": "all transport to destination, export clearance",
        "buyer_pays": "unloading, import clearance, duties",
        "modes": "any",
        "use_when": "seller has logistics infrastructure in destination country",
        "risk_level": "low_for_buyer",
    },
    "DPU": {
        "name": "Delivered at Place Unloaded",
        "risk_transfers": "when goods unloaded at destination",
        "seller_pays": "all transport + unloading at destination, export clearance",
        "buyer_pays": "import clearance, duties",
        "modes": "any",
        "use_when": "previously DAT; seller responsible for unloading (e.g. at terminal/warehouse)",
        "risk_level": "low_for_buyer",
    },
    "DDP": {
        "name": "Delivered Duty Paid",
        "risk_transfers": "when goods available at buyer's premises, duty paid",
        "seller_pays": "everything — all transport, insurance, export/import clearance, duties",
        "buyer_pays": "nothing (just unload at their own premises)",
        "modes": "any",
        "use_when": "maximum convenience for buyer. Common in e-commerce/dropship.",
        "risk_level": "very_low_for_buyer",
    },
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def get_total_duty_rate(
    hs_code: str,
    origin: str = "CN",
    dest: str = "US",
) -> Dict[str, Any]:
    """
    Calculate total estimated duty rate for an HS code.

    Combines MFN base rate with Section 301 additional tariff (if applicable).
    Only CN->US Section 301 tariffs are currently supported.

    Args:
        hs_code: HS code (at least 2 digits for chapter lookup).
        origin: Origin country ISO code (default: CN).
        dest: Destination country ISO code (default: US).

    Returns:
        Dict with mfn_rate, section_301_rate, total_rate, list, and notes.
    """
    # Extract 2-digit chapter — validate input
    if not hs_code or not hs_code.strip():
        return {
            "hs_code": hs_code,
            "chapter": "",
            "mfn_rate": 0.0,
            "mfn_description": "",
            "section_301_rate": 0.0,
            "section_301_list": "",
            "total_rate": 0.0,
            "notes": "Invalid HS code: empty or blank",
            "valid": False,
        }
    chapter = hs_code[:2].zfill(2)

    result: Dict[str, Any] = {
        "hs_code": hs_code,
        "chapter": chapter,
        "mfn_rate": 0.0,
        "mfn_description": "",
        "section_301_rate": 0.0,
        "section_301_list": "",
        "total_rate": 0.0,
        "notes": "",
    }

    # MFN rate lookup
    mfn = MFN_DUTY_RATES.get(chapter)
    if mfn:
        result["mfn_rate"] = mfn["typical"]
        result["mfn_description"] = mfn["description"]
        result["notes"] = f"MFN range: {mfn['low']:.1%}-{mfn['high']:.1%}"
    else:
        result["notes"] = "HS chapter not in MFN database; using 0% MFN estimate"

    # Section 301 (only for CN->US)
    if origin.upper() == "CN" and dest.upper() == "US":
        s301 = SECTION_301_TARIFFS.get(chapter)
        if s301:
            result["section_301_rate"] = s301["rate"]
            result["section_301_list"] = s301["list"]
            s301_note = f"Section 301 List {s301['list']}: {s301['rate']:.1%}"
            if s301.get("notes"):
                s301_note += f". {s301['notes']}"
            result["notes"] += f" | {s301_note}" if result["notes"] else s301_note

    result["total_rate"] = result["mfn_rate"] + result["section_301_rate"]

    return result


def get_compliance_requirements(category: str) -> Dict[str, Any]:
    """
    Get US import compliance requirements for a product category.

    Args:
        category: Product category key (e.g. 'electronics', 'toys').

    Returns:
        Dict with requirements, labeling, and warnings. Empty dict if
        category not found.
    """
    return PRODUCT_COMPLIANCE.get(category.lower(), {})


def get_incoterm(term: str) -> Dict[str, str]:
    """
    Get Incoterm details by code.

    Args:
        term: Incoterm code (e.g. 'FOB', 'CIF', 'DDP').

    Returns:
        Dict with name, risk_transfers, seller_pays, buyer_pays, modes,
        use_when, risk_level. Empty dict if term not found.
    """
    return INCOTERMS.get(term.upper(), {})


def estimate_total_duties(
    hs_code: str,
    goods_value: float,
    origin: str = "CN",
    dest: str = "US",
) -> Dict[str, Any]:
    """
    Estimate total duty amounts for a shipment.

    Args:
        hs_code: HS code (at least 2 digits).
        goods_value: Total declared value of goods in USD.
        origin: Origin country ISO code (default: CN).
        dest: Destination country ISO code (default: US).

    Returns:
        Dict with mfn_duty, section_301_duty, total_duty, and rate_breakdown.
    """
    # Guard against invalid inputs
    if goods_value < 0:
        return {
            "goods_value": goods_value,
            "mfn_duty": 0.0,
            "section_301_duty": 0.0,
            "total_duty": 0.0,
            "rate_breakdown": {},
            "error": "Goods value cannot be negative",
        }

    # Section 321 de minimis: shipments under threshold are duty-free
    if goods_value <= DE_MINIMIS_THRESHOLD:
        rates = get_total_duty_rate(hs_code, origin, dest)
        return {
            "goods_value": goods_value,
            "mfn_duty": 0.0,
            "section_301_duty": 0.0,
            "total_duty": 0.0,
            "rate_breakdown": rates,
            "de_minimis": True,
            "note": f"Section 321 de minimis: shipment under ${DE_MINIMIS_THRESHOLD} is duty-free",
        }

    rates = get_total_duty_rate(hs_code, origin, dest)

    mfn_duty = goods_value * rates["mfn_rate"]
    s301_duty = goods_value * rates["section_301_rate"]
    total_duty = mfn_duty + s301_duty

    return {
        "goods_value": goods_value,
        "mfn_duty": round(mfn_duty, 2),
        "section_301_duty": round(s301_duty, 2),
        "total_duty": round(total_duty, 2),
        "rate_breakdown": rates,
        "de_minimis": False,
    }
