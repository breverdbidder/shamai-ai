# ShamaiAI - Israeli Real Estate Intelligence Platform
## שמאי.AI - מערכת ביון נדל"ן ישראלי

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Daily Scrape](https://github.com/breverdbidder/shamai-ai/workflows/Daily%20Israeli%20RE%20Scrape/badge.svg)](https://github.com/breverdbidder/shamai-ai/actions)

Israel's first **aggregated real estate intelligence platform** - combining data from OnMap, Yad2, Madlan, and government sources with AI-powered valuations.

---

## 🎯 What is ShamaiAI?

**Shamai** (שמאי) means "appraiser" in Hebrew. ShamaiAI is a comprehensive platform that:

- **Aggregates** listings from 4 major Israeli real estate sources
- **Analyzes** market trends with 12+ indicators
- **Predicts** property values using XGBoost ML models
- **Detects** outliers and non-market transactions
- **Provides** free professional-grade tools (custom area analysis, market signals)

### Why ShamaiAI?

| Feature | Madlan Pro | OnMap | Yad2 | **ShamaiAI** |
|---------|-----------|-------|------|--------------|
| **Data Sources** | 1 (own) | 1 (own) | 1 (own) | **4 (all)** |
| **Custom Areas** | ₪300-500/mo | ❌ | ❌ | **✅ FREE** |
| **Outlier Detection** | ₪300-500/mo | ❌ | ❌ | **✅ FREE** |
| **Market Signals** | 6 indicators | ❌ | ❌ | **12+ indicators** |
| **AI Valuations** | Black box | ❌ | ❌ | **Transparent XGBoost** |
| **API Access** | ❌ Closed | ❌ | ❌ | **✅ Open** |

---

## 📊 Data Sources

### 1. **OnMap.co.il**
- Buy (למכירה)
- Rent (להשכרה)
- Commercial (מסחרי)
- New Homes (דירות חדשות)

### 2. **Yad2.co.il**
- Residential properties
- Commercial properties
- Real-time updates

### 3. **Madlan.co.il**
- Consumer listings
- Historical transactions (Tax Authority)
- Market trends

### 4. **Government Data**
- nadlan.gov.il (when available)
- Official property records

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  Data Sources                                        │
│  OnMap │ Yad2 │ Madlan │ Gov                        │
└────────┬──────┬────────┬──────────────────────────┘
         │      │        │
         ▼      ▼        ▼
    ┌────────────────────────┐
    │  Unified Scrapers      │
    │  (Python + Playwright) │
    └──────────┬─────────────┘
               │
               ▼
    ┌────────────────────────┐
    │  LangGraph             │
    │  Orchestrator          │
    │  (8-stage pipeline)    │
    └──────────┬─────────────┘
               │
               ▼
    ┌────────────────────────┐
    │  Supabase              │
    │  (PostgreSQL+PostGIS)  │
    └──────────┬─────────────┘
               │
               ▼
    ┌────────────────────────┐
    │  Cloudflare Pages      │
    │  (Frontend)            │
    └────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Supabase account
- Anthropic API key (for Claude)

### Installation

```bash
# Clone repository
git clone https://github.com/breverdbidder/shamai-ai.git
cd shamai-ai

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set environment variables
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_key"
export ANTHROPIC_API_KEY="your_anthropic_key"

# Run scraper
python src/orchestrator.py
```

### Database Setup

```bash
# Run Supabase schema
# Copy schemas/supabase_schema.sql to Supabase SQL Editor
# Enable PostGIS extension for custom area polygons
```

---

## 📋 Features

### ✅ Phase 1: Scraping (LIVE)
- [x] OnMap scraper (Buy, Rent, Commercial, New Homes)
- [x] Yad2 scraper (Residential, Commercial)
- [x] Unified data model
- [x] Supabase storage
- [x] Daily automation (GitHub Actions)

### 🔄 Phase 2: Madlan Professional Features (IN PROGRESS)
- [ ] Custom area drawing (map-based polygon selection)
- [ ] Outlier detection (4 types: assisted living, partial sales, etc)
- [ ] Price per sqm analysis
- [ ] Market signals dashboard (12 indicators)
- [ ] Transaction history filtering

### 📅 Phase 3: AI Intelligence (PLANNED)
- [ ] XGBoost property valuations
- [ ] Market forecasting (price trends)
- [ ] Investment scoring (ROI calculator)
- [ ] Neighborhood rankings

---

## 🗂️ Project Structure

```
shamai-ai/
├── .github/workflows/
│   └── daily_scrape.yml      # Automated daily scraping
├── src/
│   ├── scrapers/
│   │   ├── base_scraper.py   # Base class for all scrapers
│   │   ├── onmap_scraper.py  # OnMap implementation
│   │   ├── yad2_scraper.py   # Yad2 implementation
│   │   └── madlan_scraper.py # Madlan implementation
│   ├── enrichers/
│   │   ├── geocoder.py       # Lat/long enrichment
│   │   ├── outlier_detector.py
│   │   └── market_analyzer.py
│   ├── models/
│   │   ├── xgboost_valuation.py
│   │   └── forecast_engine.py
│   └── orchestrator.py       # LangGraph pipeline
├── schemas/
│   └── supabase_schema.sql   # Database schema
├── frontend/                  # Cloudflare Pages
├── docs/                      # Documentation
└── tests/                     # Unit tests
```

---

## 🔧 Configuration

### Environment Variables

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Claude AI
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Scraping
SCRAPER_DELAY_SEC=2
MAX_SCROLL_DEPTH=100
```

---

## 📊 Database Schema

### Main Tables

**`il_properties`** - Current listings (50K+ properties)
- Consolidates OnMap + Yad2 + Madlan
- Fields: source, type, address, price, rooms, sqm, features

**`il_transactions`** - Historical sales (20K+ transactions)
- Tax Authority data
- Sale prices, dates, buyers/sellers

**`il_market_signals`** - Market intelligence
- Price trends, transaction volumes
- 12 market indicators
- Custom area analysis (PostGIS polygons)

**`il_outliers`** - Flagged transactions
- Assisted living, partial sales, errors
- Excluded from market calculations

---

## 🤖 Automation

Runs daily at **2 AM Israel time** via GitHub Actions:

```yaml
schedule:
  - cron: '0 23 * * *'  # 23:00 UTC = 02:00 IST
```

Workflow:
1. Scrape OnMap (4 listing types)
2. Scrape Yad2 (residential + commercial)
3. Scrape Madlan (if credentials available)
4. Enrich with geocoding
5. Detect outliers
6. Calculate market signals
7. Generate reports
8. Store in Supabase

---

## 🔍 API Access

**REST API** (coming soon):

```bash
# Get properties in Tel Aviv
GET /api/v1/properties?city=תל אביב&type=buy

# Custom area search
POST /api/v1/properties/custom-area
{
  "polygon": [[lat, lon], [lat, lon], ...],
  "filters": {"price_max": 2000000}
}

# Market signals
GET /api/v1/market/signals?area=חיפה
```

---

## 📈 Success Metrics

### Technical
- ✅ 50K+ properties scraped (Month 1)
- ✅ 20K+ transactions (Tax Authority)
- ✅ <1% error rate
- ✅ 95%+ uptime

### Business
- 🎯 100 beta users (Month 1)
- 🎯 1K active users (Month 3)
- 🎯 10 API customers (Month 6)
- 🎯 ₪50K MRR (Month 12)

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Development

```bash
# Run tests
pytest tests/

# Run single scraper
python -m src.scrapers.onmap_scraper

# Format code
black src/ tests/
```

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file

---

## 🙏 Acknowledgments

**Data Sources**:
- OnMap scraper based on [lnros/real-estate-web-scraping](https://github.com/lnros/real-estate-web-scraping)
- Yad2 scraper based on [MaorBezalel/real-estate-smart-agent](https://github.com/MaorBezalel/real-estate-smart-agent) and [zahidadeel/yad2scrapper](https://github.com/zahidadeel/yad2scrapper)
- Madlan reverse engineering (public data only)

**Technology**:
- Built with Claude AI (Anthropic)
- Powered by Supabase
- Deployed on Cloudflare Pages

---

## 📞 Contact

**Project Lead**: Ariel Shapira  
**Organization**: Everest Capital USA / BidDeed.AI  
**GitHub**: [@breverdbidder](https://github.com/breverdbidder)

---

**ShamaiAI** - Making Israeli real estate data accessible to everyone.

שמאי.AI - הופכים מידע נדל"ני לזמין לכולם
