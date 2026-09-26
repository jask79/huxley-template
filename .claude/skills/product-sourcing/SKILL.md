---
name: product-sourcing
description: "E-commerce product sourcing intelligence -- search suppliers, score and rank, calculate landed costs (w/ Section 301 tariffs), check compliance, assess supply chain risk, negotiate, compare quotes, and track RFQs"
when: "product sourcing, supplier search, alibaba search, 1688 search, landed cost, OEM sourcing, supplier evaluation, RFQ tracking, import duty, freight cost, find supplier, find manufacturer, dhgate, wholesale, bulk order, factory search, section 301, tariff, compliance, trade compliance, hs code, incoterms, quality inspection, negotiation, supply chain risk, chinese holiday, made in china"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
metadata:
  version: "0.2.0"
  authority: "{{ORCHESTRATOR_NAME}}"
  script: "tools/product-sourcing/cli.py"
  scope: "Alibaba/1688/DHgate/MIC scraping, Easyship API, exchange rates, Section 301 tariffs, compliance, logistics, risk scoring, negotiation"
  last_updated: "2026-02-25"
---

# Product Sourcing Skill

CLI tool for e-commerce product sourcing intelligence across Chinese B2B platforms.

## Quick Reference

```bash
# Search for products
python3 tools/product-sourcing/cli.py search "silicone phone case" --platform alibaba
python3 tools/product-sourcing/cli.py search "手机壳" --platform 1688
python3 tools/product-sourcing/cli.py search "silicone phone case"  # all platforms

# Supplier intelligence
python3 tools/product-sourcing/cli.py supplier list --sort score
python3 tools/product-sourcing/cli.py supplier show ali:abc123
python3 tools/product-sourcing/cli.py supplier score ali:abc123

# Product tracking
python3 tools/product-sourcing/cli.py product show 42
python3 tools/product-sourcing/cli.py product prices 42

# Landed cost calculation (now with Section 301 tariffs)
python3 tools/product-sourcing/cli.py cost calculate --product-id 42 --qty 500 --hs-code 8507 --freight-mode sea
python3 tools/product-sourcing/cli.py cost hs-lookup "silicone phone case"
python3 tools/product-sourcing/cli.py cost exchange CNY USD

# Trade compliance
python3 tools/product-sourcing/cli.py compliance tariff 8507              # Tariff lookup w/ Section 301
python3 tools/product-sourcing/cli.py compliance requirements electronics  # Category compliance requirements
python3 tools/product-sourcing/cli.py compliance check 42                  # Check product compliance status
python3 tools/product-sourcing/cli.py compliance incoterms FOB             # Incoterms reference

# Supplier comparison
python3 tools/product-sourcing/cli.py compare suppliers ali:abc123 ali:def456 dh:ghi789
python3 tools/product-sourcing/cli.py compare products 42 43 44
python3 tools/product-sourcing/cli.py compare quotes 1 2 3

# Supply chain risk
python3 tools/product-sourcing/cli.py risk assess ali:abc123    # Supplier risk assessment
python3 tools/product-sourcing/cli.py risk report               # Portfolio risk summary
python3 tools/product-sourcing/cli.py risk concentration        # Concentration analysis
python3 tools/product-sourcing/cli.py risk scams ali:abc123     # Scam indicator check

# Negotiation intelligence
python3 tools/product-sourcing/cli.py negotiate template initial       # Get message template
python3 tools/product-sourcing/cli.py negotiate terms 5000             # Payment terms recommendation
python3 tools/product-sourcing/cli.py negotiate strategy first_order   # Strategy advice
python3 tools/product-sourcing/cli.py negotiate discount 0.85 --quantities "100,500,1000"

# Price alerts
python3 tools/product-sourcing/cli.py alert create --product 42 --type price --threshold 0.80
python3 tools/product-sourcing/cli.py alert list --active
python3 tools/product-sourcing/cli.py alert check

# RFQ tracking
python3 tools/product-sourcing/cli.py rfq create --supplier ali:abc123 --product-id 42 --qty 500 --target-price 0.85 --desc "Custom silicone case, pantone 485C"
python3 tools/product-sourcing/cli.py rfq list --status sent
python3 tools/product-sourcing/cli.py rfq update 1 --status responded --quote 0.92 --lead-time 25

# Export data
python3 tools/product-sourcing/cli.py export suppliers --format md --min-score 70
python3 tools/product-sourcing/cli.py export costs --format csv --output /tmp/cost-report.csv

# Configuration
python3 tools/product-sourcing/cli.py config check
python3 tools/product-sourcing/cli.py config stats
```

## Platforms Supported
- **Alibaba.com** -- international B2B, English, USD
- **1688.com** -- Chinese domestic B2B, Mandarin, CNY (30-60% cheaper)
- **DHgate.com** -- hybrid B2B/B2C, English, USD
- **Made-in-China.com** -- international B2B, English, USD (industrial strength)

## Scrapers (direct invocation)
```bash
python3 tools/product-sourcing/scrapers/alibaba.py search "query" --max-results 20 --output /tmp/results.json
python3 tools/product-sourcing/scrapers/ali1688.py search "query" --output /tmp/results.json
python3 tools/product-sourcing/scrapers/dhgate.py search "query" --output /tmp/results.json
python3 tools/product-sourcing/scrapers/mic.py search "query" --output /tmp/results.json
```

## Key Modules
- `compliance.py` -- Section 301 tariffs, MFN duty rates, product compliance requirements, Incoterms
- `logistics.py` -- Freight estimation, Chinese holidays, transit times, container optimization
- `risk.py` -- Supply chain risk scoring, geographic risk, scam detection
- `negotiation.py` -- Message templates, payment terms, negotiation strategies
- `market.py` -- Category margins, quote comparison, decision matrices
- `scoring.py` -- 7-factor supplier quality scoring with 12 red flag rules

## API Credentials
- `product-sourcing-easyship-token` (Keychain) -- for duty/tariff calculations (optional, local tariff tables used as fallback)
- Freightos and exchange rate APIs are free/no-auth

## Database
SQLite at `monitoring/product-sourcing.db` (auto-created on first use)
12 tables: suppliers, products, price_snapshots, search_history, rfqs, supplier_scores, cost_calculations, exchange_rates, supplier_communications, compliance_checks, risk_assessments, price_alerts
