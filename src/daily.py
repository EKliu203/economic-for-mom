"""
每日财经新闻数据读取模块。
从 reference/daily/ 目录读取 JSON 文件，提供按时间/板块/公司等维度筛选的接口。
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_DIR = os.path.join(BASE_DIR, "reference", "daily")


def get_latest_daily_data() -> List[Dict]:
    """获取最新一天的新闻数据。"""
    if not os.path.exists(DAILY_DIR):
        return []
    files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith(".json")], reverse=True)
    if not files:
        return []
    try:
        with open(os.path.join(DAILY_DIR, files[0]), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_all_recent_news(days: int = 7) -> List[Dict]:
    """获取近 N 天的所有新闻。"""
    all_news = []
    if not os.path.exists(DAILY_DIR):
        return []

    files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith(".json")], reverse=True)

    for file in files[:days]:
        path = os.path.join(DAILY_DIR, file)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_news.extend(data)
        except Exception as e:
            print(f"解析 {file} 失败: {e}")

    # 去重（按 title）
    seen = set()
    valid = []
    for n in all_news:
        title = n.get("title", "")
        if title and title not in seen:
            seen.add(title)
            valid.append(n)

    valid.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return valid


def get_news_by_sector(days: int = 7, sector: Optional[str] = None) -> List[Dict]:
    """按板块筛选新闻。"""
    all_news = get_all_recent_news(days)
    if not sector:
        return all_news
    return [n for n in all_news if sector in n.get("sector", [])]


def get_news_by_company(days: int = 7, company: Optional[str] = None) -> List[Dict]:
    """按公司筛选新闻。"""
    all_news = get_all_recent_news(days)
    if not company:
        return all_news
    return [n for n in all_news if company in n.get("companies", [])]


def get_news_by_sentiment(days: int = 7, sentiment: Optional[str] = None) -> List[Dict]:
    """按情绪筛选新闻 (positive/negative/neutral)。"""
    all_news = get_all_recent_news(days)
    if not sentiment:
        return all_news
    return [n for n in all_news if n.get("sentiment") == sentiment]


def get_weekly_summary(days: int = 7) -> Dict:
    """生成周度市场总结。"""
    news = get_all_recent_news(days)
    if not news:
        return {"total": 0, "days_with_data": 0, "sentiment_trend": "", "hot_sectors": {}, "hot_companies": []}

    # 按天统计
    daily_stats: Dict[str, Dict] = {}
    for n in news:
        day = n.get("date", "")[:10]
        if not day:
            continue
        if day not in daily_stats:
            daily_stats[day] = {"total": 0, "positive": 0, "negative": 0, "neutral": 0}
        daily_stats[day]["total"] += 1
        sentiment = n.get("sentiment", "neutral")
        daily_stats[day][sentiment] = daily_stats[day].get(sentiment, 0) + 1

    pos_total = sum(1 for n in news if n.get("sentiment") == "positive")
    neg_total = sum(1 for n in news if n.get("sentiment") == "negative")
    neu_total = sum(1 for n in news if n.get("sentiment") == "neutral")
    total = len(news)

    # 板块累计热度
    sector_count: Dict[str, int] = {}
    for n in news:
        for s in n.get("sector", []):
            sector_count[s] = sector_count.get(s, 0) + 1

    # 公司累计提及
    company_count: Dict[str, int] = {}
    for n in news:
        for c in n.get("companies", []):
            company_count[c] = company_count.get(c, 0) + 1

    # 按来源统计
    source_count: Dict[str, int] = {}
    for n in news:
        src = n.get("source", "unknown")
        source_count[src] = source_count.get(src, 0) + 1

    return {
        "total": total,
        "days_with_data": len(daily_stats),
        "positive": pos_total,
        "negative": neg_total,
        "neutral": neu_total,
        "sentiment_ratio": round(pos_total / max(neg_total, 1), 2),
        "pos_pct": round(pos_total / max(total, 1) * 100),
        "neg_pct": round(neg_total / max(total, 1) * 100),
        "daily_breakdown": dict(sorted(daily_stats.items())),
        "hot_sectors": dict(sorted(sector_count.items(), key=lambda x: x[1], reverse=True)[:8]),
        "hot_companies": [{"name": c, "mentions": cnt} for c, cnt in sorted(company_count.items(), key=lambda x: x[1], reverse=True)[:10]],
        "sources": dict(sorted(source_count.items(), key=lambda x: x[1], reverse=True)),
        "top_news": [{"title": n.get("title", ""), "source": n.get("source", ""), "sentiment": n.get("sentiment", ""), "url": n.get("url", "")} for n in sorted(news, key=lambda x: x.get("relevance_score", 0), reverse=True)[:5]],
    }


def get_market_summary(days: int = 1) -> Dict:
    """生成市场情绪摘要。"""
    news = get_all_recent_news(days)
    if not news:
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "sectors": {}, "top_companies": []}

    pos = sum(1 for n in news if n.get("sentiment") == "positive")
    neg = sum(1 for n in news if n.get("sentiment") == "negative")
    neu = sum(1 for n in news if n.get("sentiment") == "neutral")

    # 板块热度
    sector_count: Dict[str, int] = {}
    for n in news:
        for s in n.get("sector", []):
            sector_count[s] = sector_count.get(s, 0) + 1

    # 公司提及次数
    company_count: Dict[str, int] = {}
    for n in news:
        for c in n.get("companies", []):
            company_count[c] = company_count.get(c, 0) + 1

    top_companies = sorted(company_count.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total": len(news),
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "sentiment_ratio": round(pos / max(neg, 1), 2),
        "sectors": dict(sorted(sector_count.items(), key=lambda x: x[1], reverse=True)[:10]),
        "top_companies": [{"name": c, "mentions": cnt} for c, cnt in top_companies],
    }
