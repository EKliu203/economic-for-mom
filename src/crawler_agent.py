"""
财经新闻爬虫 — 从多个 RSS / API 源拉取每日财经新闻，
按关键词相关性评分筛选，保存为结构化 JSON。
"""

import time
import json
import os
import re
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
import feedparser
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_DIR = os.path.join(BASE_DIR, "reference", "daily")
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

os.makedirs(DAILY_DIR, exist_ok=True)

# ======================= 配置 =======================

MAX_ARTICLES = 200          # 每天最多保存篇数
MIN_RELEVANCE_SCORE = 2     # 最低相关性分数

# 相关性关键词权重体系
KEYWORD_WEIGHTS = {
    # 市场指数 — 权重 3
    "A股": 3, "沪深": 3, "上证": 3, "深证": 3, "创业板": 3,
    "科创板": 3, "北交所": 3, "大盘": 3, "指数": 2,
    "港股": 3, "恒生": 3, "港交所": 3,
    "美股": 3, "纳斯达克": 3, "标普": 3, "道琼斯": 3, "纽交所": 2,
    # 政策与宏观 — 权重 3
    "央行": 3, "降息": 3, "加息": 3, "降准": 3, "LPR": 3,
    "美联储": 3, "央行行长": 3, "货币政策": 3, "财政政策": 3,
    "GDP": 2, "CPI": 2, "PPI": 2, "PMI": 2, "通胀": 2,
    "汇率": 2, "人民币": 2, "逆回购": 2, "MLF": 2,
    # 板块 — 权重 2
    "新能源": 2, "光伏": 2, "锂电池": 2, "新能源汽车": 2,
    "半导体": 2, "芯片": 2, "人工智能": 2, "AI": 2,
    "医药": 2, "生物医药": 2, "创新药": 2,
    "消费": 2, "白酒": 2, "食品饮料": 2,
    "房地产": 2, "基建": 2, "建材": 2,
    "银行": 2, "证券": 2, "保险": 2, "金融": 2,
    "能源": 2, "煤炭": 2, "石油": 2,
    "军工": 2, "航天": 2,
    "黄金": 2, "贵金属": 2,
    # 公司行为 — 权重 2
    "财报": 2, "业绩": 2, "营收": 2, "净利润": 2,
    "IPO": 2, "上市": 2, "并购": 2, "重组": 2,
    "增持": 2, "减持": 2, "回购": 2, "分红": 2,
    "涨停": 2, "跌停": 2, "涨停板": 2, "跌停板": 2,
    # 一般财经 — 权重 1
    "股票": 1, "股市": 1, "基金": 1, "ETF": 1,
    "债券": 1, "期货": 1, "大宗商品": 1,
    "投资": 1, "交易": 1, "开盘": 1, "收盘": 1,
    "利好": 1, "利空": 1,
}

# RSS 源配置
RSS_SOURCES = [
    # 财联社 — 电报快讯
    {"name": "财联社", "url": "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6", "type": "api"},
    # 东方财富 — 7x24 快讯
    {"name": "东方财富", "url": "https://finance.eastmoney.com/a/czqyw.html", "type": "html"},
    # 新浪财经 — 宏观新闻
    {"name": "新浪财经", "url": "https://finance.sina.com.cn/china/", "type": "html"},
    # 华尔街见闻 RSS
    {"name": "华尔街见闻", "url": "https://wallstreetcn.com/rss", "type": "rss"},
    # 网易财经
    {"name": "网易财经", "url": "https://money.163.com/special/00251G8F/news_json.js", "type": "api"},
]


def get_deepseek_client():
    """尝试获取 DeepSeek API client。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and os.path.exists(SECRETS_PATH):
        try:
            import tomllib
            with open(SECRETS_PATH, "rb") as f:
                secrets = tomllib.load(f)
                api_key = secrets.get("DEEPSEEK_API_KEY")
        except Exception:
            try:
                import toml
                secrets = toml.load(SECRETS_PATH)
                api_key = secrets.get("DEEPSEEK_API_KEY")
            except Exception:
                pass

    if api_key and api_key != "sk-your-key-here":
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        except Exception:
            return None
    return None


# ======================= 新闻获取 =======================


def _fetch_cls() -> List[Dict]:
    """从财联社 API 获取快讯。"""
    articles = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.cls.cn/",
        }
        resp = requests.get(RSS_SOURCES[0]["url"], headers=headers, timeout=15)
        data = resp.json()
        items = data.get("data", {}).get("roll_data", []) or data.get("data", [])
        if not isinstance(items, list):
            items = []
        for item in items:
            title = item.get("title", "") or item.get("brief", "")
            content = item.get("content", "") or item.get("brief", "")
            ctime = item.get("ctime", 0)
            if ctime:
                date = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
            else:
                date = datetime.now().strftime("%Y-%m-%d")
            if title:
                articles.append({
                    "title": title.strip(),
                    "content": content.strip() if content else title.strip(),
                    "source": "财联社",
                    "date": date,
                    "url": item.get("shareurl", "") or f"https://www.cls.cn/detail/{item.get('id', '')}",
                })
    except Exception as e:
        logger.warning(f"财联社抓取失败: {e}")
    return articles


def _fetch_eastmoney() -> List[Dict]:
    """从东方财富页面抓取快讯。"""
    articles = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.eastmoney.com/",
        }
        resp = requests.get(RSS_SOURCES[1]["url"], headers=headers, timeout=15)
        resp.encoding = "gb2312" if "gb" in resp.apparent_encoding.lower() else resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "lxml")
        # 尝试找新闻列表
        items = soup.select(".news-item, .list-item, li a, .title a")
        seen = set()
        for item in items:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            if not title or not href or len(title) < 6:
                continue
            if title in seen:
                continue
            seen.add(title)
            articles.append({
                "title": title,
                "content": title,
                "source": "东方财富",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "url": href if href.startswith("http") else f"https://finance.eastmoney.com{href}",
            })
    except Exception as e:
        logger.warning(f"东方财富抓取失败: {e}")
    return articles


def _fetch_sina_finance() -> List[Dict]:
    """从新浪财经抓取新闻。"""
    articles = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        resp = requests.get(RSS_SOURCES[2]["url"], headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.select(".news-item h2 a, .list-item a, .ty-card-tt a, .feed-card-item h2 a, a[href]")
        seen = set()
        for item in items:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            if not title or not href or len(title) < 6:
                continue
            if "finance.sina.com.cn" not in href:
                continue
            if title in seen:
                continue
            seen.add(title)
            articles.append({
                "title": title,
                "content": title,
                "source": "新浪财经",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "url": href if href.startswith("http") else f"https:{href}",
            })
    except Exception as e:
        logger.warning(f"新浪财经抓取失败: {e}")
    return articles


def _fetch_rss(source: Dict) -> List[Dict]:
    """通用 RSS 抓取。"""
    articles = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:50]:
            title = entry.get("title", "").strip()
            content = entry.get("summary", "").strip() or entry.get("description", "").strip() or title
            published = entry.get("published", "") or entry.get("updated", "")
            link = entry.get("link", "")
            if not title or len(title) < 4:
                continue
            articles.append({
                "title": title,
                "content": _strip_html(content),
                "source": source["name"],
                "date": published or datetime.now().strftime("%Y-%m-%d"),
                "url": link,
            })
        logger.info(f"  {source['name']} RSS: {len(articles)} 篇")
    except Exception as e:
        logger.warning(f"  {source['name']} RSS 失败: {e}")
    return articles


def _fetch_wallstreetcn() -> List[Dict]:
    """华尔街见闻 RSS。"""
    return _fetch_rss({"name": "华尔街见闻", "url": "https://wallstreetcn.com/rss"})


def _fetch_163_money() -> List[Dict]:
    """网易财经 API。"""
    articles = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(RSS_SOURCES[4]["url"], headers=headers, timeout=15)
        # 网易财经的 JS 格式: var news = [...]
        text = resp.text
        match = re.search(r'var\s+\w+\s*=\s*(\[.*\])', text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            for item in data[:50]:
                title = item.get("title", "").strip()
                if not title or len(title) < 6:
                    continue
                articles.append({
                    "title": title,
                    "content": item.get("digest", title),
                    "source": "网易财经",
                    "date": item.get("time", datetime.now().strftime("%Y-%m-%d")),
                    "url": item.get("docurl", ""),
                })
        logger.info(f"  网易财经: {len(articles)} 篇")
    except Exception as e:
        logger.warning(f"网易财经抓取失败: {e}")
    return articles


# ======================= 筛选 & 评分 =======================


def compute_relevance(text: str) -> int:
    """根据关键词权重计算相关性分数。"""
    score = 0
    text_lower = text.lower()
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword.lower() in text_lower:
            score += weight
    return score


def compute_sentiment(text: str) -> str:
    """简单的基于词典的情绪判断。"""
    positive_words = [
        "利好", "大涨", "涨停", "突破", "创新高", "增长", "盈利", "回暖", "复苏",
        "增持", "回购", "分红", "降息", "降准", "放水", "刺激", "补贴",
        "业绩大增", "超预期", "净流入", "主力资金", "涨停板",
    ]
    negative_words = [
        "利空", "大跌", "跌停", "跌破", "新低", "亏损", "下滑", "衰退",
        "减持", "爆雷", "违约", "退市", "ST", "处罚", "调查",
        "贸易战", "制裁", "加息", "缩表", "资金流出", "恐慌",
        "踩踏", "熔断",
    ]
    pos_score = sum(1 for w in positive_words if w in text)
    neg_score = sum(1 for w in negative_words if w in text)

    if pos_score > neg_score:
        return "positive"
    elif neg_score > pos_score:
        return "negative"
    return "neutral"


def extract_companies(text: str) -> List[str]:
    """从文本中提取提及的公司/股票名称。"""
    # 常见A股公司简称
    patterns = [
        r"(贵州茅台|五粮液|宁德时代|比亚迪|隆基绿能|中国平安|招商银行|兴业银行|"
        r"万科|保利|格力|美的|海尔|恒瑞医药|药明康德|中芯国际|海康威视|"
        r"立讯精密|京东方|中兴通讯|腾讯|阿里巴巴|美团|百度|京东|拼多多|网易|"
        r"小米|华为|特斯拉|苹果|英伟达|微软|谷歌|亚马逊|Meta|"
        r"工商银行|建设银行|农业银行|中国银行|交通银行|邮储银行|"
        r"中国石油|中国石化|中国神华|长江电力|中国移动|中国电信|中国联通|"
        r"东方财富|中信证券|华泰证券|中金公司)"
    ]
    companies = []
    for pat in patterns:
        found = re.findall(pat, text)
        companies.extend(found)
    return list(set(companies))


def extract_sector(text: str) -> List[str]:
    """从文本中识别涉及的板块。"""
    sector_map = {
        "新能源": ["新能源", "光伏", "风电", "储能", "锂电池", "锂电", "钠电池", "固态电池"],
        "新能源汽车": ["新能源汽车", "电动车", "智能汽车", "自动驾驶"],
        "半导体": ["半导体", "芯片", "集成电路", "光刻"],
        "人工智能": ["人工智能", "AI", "大模型", "ChatGPT", "GPT", "机器学习"],
        "医药生物": ["医药", "生物医药", "创新药", "CXO", "医疗器械", "疫苗"],
        "大消费": ["消费", "白酒", "食品饮料", "家电", "零售", "免税"],
        "金融": ["银行", "证券", "保险", "券商", "信托"],
        "房地产": ["房地产", "地产", "楼市", "房价", "建材", "基建"],
        "能源": ["石油", "煤炭", "天然气", "能源", "电力"],
        "军工": ["军工", "国防", "航天", "航空"],
        "数字经济": ["数字经济", "数据要素", "信创", "国产软件", "云计算"],
        "黄金贵金属": ["黄金", "贵金属", "白银", "铜", "稀土"],
    }
    sectors = []
    for sector, keywords in sector_map.items():
        for kw in keywords:
            if kw in text:
                sectors.append(sector)
                break
    return list(set(sectors))


# ======================= 主流程 =======================


def _deduplicate(articles: List[Dict]) -> List[Dict]:
    """按标题哈希去重。"""
    seen = set()
    result = []
    for a in articles:
        h = hashlib.md5(a["title"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            result.append(a)
    return result


def run_agent():
    """执行每日新闻爬取主流程。"""
    logger.info(f"========== 财经新闻爬取开始 ({datetime.now().strftime('%Y-%m-%d')}) ==========")

    all_articles: List[Dict] = []

    # 1. 财联社
    logger.info("抓取财联社...")
    all_articles.extend(_fetch_cls())

    # 2. 东方财富
    logger.info("抓取东方财富...")
    all_articles.extend(_fetch_eastmoney())

    # 3. 新浪财经
    logger.info("抓取新浪财经...")
    all_articles.extend(_fetch_sina_finance())

    # 4. 华尔街见闻 RSS
    logger.info("抓取华尔街见闻...")
    all_articles.extend(_fetch_wallstreetcn())

    # 5. 网易财经
    logger.info("抓取网易财经...")
    all_articles.extend(_fetch_163_money())

    # 去重
    all_articles = _deduplicate(all_articles)
    logger.info(f"去重后共 {len(all_articles)} 篇候选新闻")

    # 评分与筛选
    results = []
    for art in all_articles:
        text = art["title"] + " " + art.get("content", "")
        score = compute_relevance(text)
        if score < MIN_RELEVANCE_SCORE:
            continue

        art["relevance_score"] = score
        art["sentiment"] = compute_sentiment(text)
        art["companies"] = extract_companies(text)
        art["sector"] = extract_sector(text)
        results.append(art)

    # 按相关性排序
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = results[:MAX_ARTICLES]

    # 保存
    filename = f"{datetime.now().strftime('%Y-%m-%d')}.json"
    filepath = os.path.join(DAILY_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"========== 完成：保存 {len(results)} 篇高相关性新闻到 {filename} ==========")

    # 统计
    pos_count = sum(1 for a in results if a.get("sentiment") == "positive")
    neg_count = sum(1 for a in results if a.get("sentiment") == "negative")
    neu_count = sum(1 for a in results if a.get("sentiment") == "neutral")
    logger.info(f"情绪分布：利好 {pos_count} | 利空 {neg_count} | 中性 {neu_count}")

    return results


if __name__ == "__main__":
    run_agent()
