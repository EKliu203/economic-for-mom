"""
Trading Skills Integration Module.
Wraps the claude-trading-skills for use within the Streamlit app.

Supported skills:
  - sector-analyst: Sector rotation analysis (free, no API key)
  - economic-calendar-fetcher: Economic calendar (requires FMP_API_KEY)
  - market-environment-analysis: Market environment report
  - market-news-analyst: Market news impact analysis
"""

import os
import sys
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="[Skills] %(message)s")
logger = logging.getLogger(__name__)

SKILLS_BASE = os.path.expanduser("~/.claude/skills/claude-trading-skills/skills")


def _get_sector_analyzer():
    """Import the sector rotation analysis module from trading skills."""
    sector_scripts = os.path.join(SKILLS_BASE, "sector-analyst", "scripts")
    if sector_scripts not in sys.path:
        sys.path.insert(0, sector_scripts)
    # The script is named analyze_sector_rotation.py
    import importlib
    return importlib.import_module("analyze_sector_rotation")


def run_sector_analysis() -> Dict:
    """Run sector rotation analysis. Returns structured results dict.

    Uses TraderMonty's public CSV data (free, no API key required).
    """
    try:
        mod = _get_sector_analyzer()
        # Run the analysis
        raw_rows = mod.fetch_csv(mod.SECTOR_CSV_URL)
        mod.validate_columns(raw_rows)
        sectors = mod.parse_sector_rows(raw_rows)
        freshness = mod.check_freshness(mod.UPTREND_CSV_URL)

        if not sectors:
            return {"error": "No sector data available", "success": False}

        ranking = mod.rank_sectors(sectors)
        groups = mod.analyze_groups(sectors)
        overbought, oversold = mod.identify_overbought_oversold(sectors)
        trends = mod.analyze_trends(sectors)
        cycle = mod.estimate_cycle_phase(sectors)

        return {
            "success": True,
            "generated_at": datetime.now().isoformat(),
            "freshness": freshness,
            "risk_regime": {
                "regime": groups.get("regime", "unknown"),
                "score": groups.get("score", 50),
                "cyclical_avg_pct": groups.get("cyclical_avg_pct", 0),
                "defensive_avg_pct": groups.get("defensive_avg_pct", 0),
                "difference_pct": groups.get("difference_pct", 0),
                "late_cycle_flag": groups.get("late_cycle_flag", False),
                "divergence_flag": groups.get("divergence_flag", False),
            },
            "cycle_phase": cycle,
            "ranking": ranking[:6],  # Top 6 sectors
            "overbought": overbought,
            "oversold": oversold,
            "trends": trends,
            "full_report": mod.format_human(ranking, groups, overbought, oversold, trends, cycle, freshness),
        }
    except Exception as e:
        logger.error(f"Sector analysis failed: {e}")
        return {"error": str(e), "success": False}


def run_economic_calendar(days: int = 7) -> Dict:
    """Fetch economic calendar events (requires FMP_API_KEY)."""
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        # Try secrets
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".streamlit", "secrets.toml"
        )
        if os.path.exists(secrets_path):
            try:
                import tomllib
                with open(secrets_path, "rb") as f:
                    s = tomllib.load(f)
                    api_key = s.get("FMP_API_KEY", "")
            except Exception:
                pass

    if not api_key:
        return {"error": "FMP_API_KEY not configured. Set in .streamlit/secrets.toml or environment.", "success": False}

    from_date = date.today().strftime("%Y-%m-%d")
    to_date = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        cal_scripts = os.path.join(SKILLS_BASE, "economic-calendar-fetcher", "scripts")
        if cal_scripts not in sys.path:
            sys.path.insert(0, cal_scripts)
        import importlib
        mod = importlib.import_module("get_economic_calendar")
        events = mod.fetch_economic_calendar(from_date, to_date, api_key)

        # Filter high-impact events
        high_impact = [e for e in events if e.get("impact", "") in ("High", "high", "HIGH")]
        medium_impact = [e for e in events if e.get("impact", "") in ("Medium", "medium", "MEDIUM")]

        return {
            "success": True,
            "from_date": from_date,
            "to_date": to_date,
            "total_events": len(events),
            "high_impact": high_impact,
            "medium_impact": medium_impact,
            "all_events": events[:50],
        }
    except Exception as e:
        logger.error(f"Economic calendar fetch failed: {e}")
        return {"error": str(e), "success": False}


def get_sector_analysis_prompt() -> str:
    """Get the sector analysis skill knowledge as a system prompt addition."""
    return """## Sector Rotation Analysis Framework

You have access to sector rotation analysis capabilities. When analyzing sectors:

1. **Risk Regime Score (0-100)**:
   - 90+: Strong Risk-On — cyclicals dominate, aggressive positioning
   - 70-89: Risk-On — cyclical tilt, growth favored
   - 45-69: Balanced — mixed signals, maintain diversification
   - 20-44: Defensive Tilt — defensives leading, reduce risk
   - 0-19: Strong Risk-Off — deep defensive rotation, capital preservation

2. **Market Cycle Phases**:
   - Early: Technology, Consumer Cyclical, Industrials lead
   - Mid: Technology, Industrials, Consumer Cyclical, Energy lead
   - Late: Energy, Basic Materials, Healthcare lead
   - Recession: Utilities, Consumer Defensive, Healthcare lead

3. **Key Thresholds**:
   - Overbought: Uptrend ratio > 37%
   - Oversold: Uptrend ratio < 9.7%

4. **Group Analysis**:
   - Cyclical sectors: Technology, Consumer Cyclical, Communication Services, Financial, Industrials
   - Defensive sectors: Utilities, Consumer Defensive, Healthcare, Real Estate
   - Commodity sectors: Energy, Basic Materials

When asked about sector rotation or market cycles, always reference this framework."""


def get_market_environment_prompt() -> str:
    """Get the market environment analysis knowledge as system prompt."""
    return """## Market Environment Analysis Framework

When analyzing market conditions, assess:

### Key Indicators
- **VIX**: 10-15 (low vol), 15-20 (normal), 20-30 (caution), 30+ (panic)
- **US 10Y Yield**: Critical for equity valuations — 3.5%, 4.0%, 4.5%, 5.0% key levels
- **Gold**: Safe haven — 1900, 2000, 2100 key levels
- **Crude (WTI)**: Inflation indicator — 70, 80, 90, 100 key levels
- **USD/CNY**: Critical for A-share foreign flows

### Risk-On vs Risk-Off Assessment
- Check: VIX level, bond yields, sector rotation, currency flows
- Risk-On: Cyclicals leading, low VIX, USD weakening, credit spreads tightening
- Risk-Off: Defensives leading, VIX spiking, USD strengthening, credit spreads widening

### Inter-Market Analysis
- Bonds up + Stocks down = Defensive rotation (flight to safety)
- Bonds up + Stocks up = Goldilocks (soft landing expectations)
- Bonds down + Stocks down = Liquidity crisis (correlation to 1)
- Bonds down + Stocks up = Reflation trade (growth optimism)

Always provide multi-dimensional analysis: policy, liquidity, sentiment, fundamentals."""


def get_market_news_prompt() -> str:
    """Get the market news analysis patterns as system prompt."""
    return """## Market News Impact Analysis Framework

When analyzing news impact on markets, use this framework:

### Central Bank Policy
- **Rate Hikes**: Negative for growth/tech, positive for financials initially. USD strengthens, gold weakens.
- **Rate Cuts**: Positive for growth stocks, negative for USD. Gold and commodities strengthen.
- **QE**: Strong positive for all risk assets. USD weakens, commodities rise.
- **QT**: Negative liquidity pressure. USD strengthens, risk assets underperform.
- **Hawkish tone**: Risk-off, USD up, yields up
- **Dovish tone**: Risk-on, USD down, yields down

### PBOC Specific Tools
- LPR adjustments (1Y and 5Y+)
- RRR (reserve requirement ratio) cuts
- MLF rate and volume
- Reverse repo operations
- Pledged Supplemental Lending (PSL)

### Geopolitical Events
- Trade tensions: Negative for exporters, positive for domestic-focused sectors
- Sanctions: Supply chain disruption, commodity price spikes
- Military conflicts: Oil/gold spike, risk-off rotation

### Earnings Impact
- Mega-cap earnings (Apple, Microsoft, NVIDIA, Tesla) can move entire indices
- Guidance matters more than results
- Sector bellwethers set tone for entire industries

### A-Share Specific
- Northbound capital flows (北向资金)
- Margin trading balance (两融余额)
- IPO pace and regulation
- Major shareholder behavior (增持/减持)

When news breaks, always assess: magnitude, duration, sectors affected, and whether market has already priced it in."""


# ==================== 每日定时分析 ====================

TRADING_SESSIONS = {
    "morning": {
        "label": "上午盘前分析",
        "time": "09:00",
        "focus": "A股开盘前市场环境",
        "topics": ["隔夜美股表现", "亚太市场早盘", "重大政策/新闻", "今日关注板块"],
    },
    "afternoon": {
        "label": "下午盘后分析",
        "time": "15:30",
        "focus": "A股收盘后复盘总结",
        "topics": ["今日涨跌复盘", "板块轮动", "资金流向", "明日展望"],
    },
}

DAILY_ANALYSIS_TEMPLATE = """
## {label} ({date})

{market_summary}

### 主要关注点
{key_points}

### 建议操作方向
{recommendation}

---
*基于实时新闻数据 & 交易技能框架自动生成*
"""
