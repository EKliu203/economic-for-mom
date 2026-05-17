import streamlit as st
from openai import OpenAI
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import daily
import knowledge_base as kb
import trading_skills as ts

st.set_page_config(
    page_title="金融云历程 — AI股市分析助手",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== CSS ==========
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); }
    div[data-testid="stToolbar"] { display: none; }
    footer { visibility: hidden; }
    [data-testid="stHorizontalBlock"] {
        background: rgba(255,255,255,0.06); backdrop-filter: blur(15px);
        border-radius: 25px; padding: 20px; margin-top: -30px;
    }
    .scroll-content {
        height: 380px; overflow: hidden; position: relative;
        background: rgba(255,255,255,0.06); border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .scroll-track {
        display: flex; flex-direction: column;
        animation: scrollUpDown 45s linear infinite; animation-play-state: paused;
    }
    .scroll-content:hover .scroll-track { animation-play-state: running; }
    @keyframes scrollUpDown {
        0%,5% { transform: translateY(0); }
        45%,55% { transform: translateY(calc(-100% + 380px)); }
        95%,100% { transform: translateY(0); }
    }
    .news-card {
        background: rgba(255,255,255,0.08); margin: 8px; padding: 12px;
        border-radius: 10px; border-left: 3px solid #d4af37;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .news-title { font-weight:600; font-size:0.85rem; line-height:1.4; color:#e0e0e0; margin-bottom:6px; }
    .news-title a { text-decoration:none; color:#d4af37; }
    .news-title a:hover { color:#f0c040; }
    .news-meta { display:flex; flex-wrap:wrap; gap:6px; font-size:0.7rem; color:#a0a0a0; }
    .score-badge {
        background: linear-gradient(135deg,#d4af37,#b8960f); color:#1a1a2e;
        padding:1px 7px; border-radius:20px; font-weight:700; font-size:0.65rem;
    }
    .sentiment-pos { color:#ef4444; }
    .sentiment-neg { color:#22c55e; }
    .sentiment-neu { color:#a0a0a0; }
    .source-tag { color:#60a5fa; }
    h2,h3,h4,p,label,div,.stMarkdown { color:#e0e0e0; }
    .stCaption { color:#a0a0a0 !important; }
    [data-testid="stChatMessage"] { background:rgba(255,255,255,0.06)!important; border-radius:12px!important; }
    .section-title { color:#d4af37 !important; font-size:0.9rem; font-weight:700; margin-top:12px; }
    .clickable { cursor:pointer; transition:all 0.2s; }
    .clickable:hover { background:rgba(212,175,55,0.15)!important; border-radius:8px; }
    .metric-box { background:rgba(255,255,255,0.06); border-radius:10px; padding:12px; margin:6px 0; }
    div.stButton > button {
        width:100%; border-radius:10px; background:rgba(212,175,55,0.15);
        color:#d4af37; border:1px solid rgba(212,175,55,0.3); font-size:0.85rem;
        padding:8px 16px; transition:all 0.2s;
    }
    div.stButton > button:hover { background:rgba(212,175,55,0.3); border-color:#d4af37; }
    </style>
    """, unsafe_allow_html=True)


# ========== Knowledge Base ==========
@st.cache_resource(show_spinner=False)
def init_knowledge_base():
    if not kb.is_indexed():
        with st.spinner("首次启动，构建知识库索引..."):
            kb.build_index()
    else:
        kb._get_embedding_model()
    return True


# ========== Helpers ==========
def _get_news_context(prompt: str) -> str:
    import re
    sector_map = {
        "新能源": ["新能源","光伏","风电","储能","锂电池","宁德时代","比亚迪"],
        "半导体": ["半导体","芯片","集成电路","光刻","中芯国际"],
        "人工智能": ["人工智能","AI","大模型","ChatGPT","算力"],
        "医药": ["医药","创新药","CXO","医疗器械","疫苗","恒瑞医药"],
        "消费": ["消费","白酒","食品","家电","茅台","五粮液"],
        "金融": ["银行","证券","保险","券商","中信","招商银行"],
        "房地产": ["房地产","地产","楼市","房价","万科","保利"],
        "能源": ["石油","煤炭","天然气","神华","长江电力"],
        "军工": ["军工","国防","航天","航空"],
        "黄金": ["黄金","贵金属","白银"],
    }
    target_sectors = []
    for sector, keywords in sector_map.items():
        for kw in keywords:
            if kw in prompt:
                target_sectors.append(sector)
                break
    all_news = daily.get_all_recent_news(days=3)
    if not all_news: return ""
    if not target_sectors:
        return _fmt_news(all_news[:12], "【近3天热门财经新闻】")
    filtered = [n for n in all_news if any(s in n.get("sector",[]) for s in target_sectors)]
    if not filtered:
        return f"【筛选结果】未找到与{'、'.join(target_sectors)}相关新闻。\n\n" + _fmt_news(all_news[:8], "近期热门新闻：")
    return _fmt_news(filtered[:15], f"【{'、'.join(target_sectors)}相关新闻 · {len(filtered)}条】")

def _fmt_news(news_list: list, header: str) -> str:
    lines = [header]
    s_map = {"positive":"利好","negative":"利空","neutral":"中性"}
    for n in news_list:
        sentiment = s_map.get(n.get("sentiment",""),"")
        sectors = "、".join(n.get("sector",[])) if n.get("sector") else ""
        companies = "、".join(n.get("companies",[])) if n.get("companies") else ""
        extra = f" | {sentiment}"
        if sectors: extra += f" | {sectors}"
        if companies: extra += f" | {companies}"
        lines.append(f"[{n.get('source','')} · {n.get('date','')}{extra}]\n{n.get('title','')}\n{n.get('content','')[:250]}")
    return "\n\n---\n\n".join(lines)

def render_sentiment_badge(sentiment: str) -> str:
    labels = {"positive": ("利好", "sentiment-pos"), "negative": ("利空", "sentiment-neg"), "neutral": ("中性", "sentiment-neu")}
    label, cls = labels.get(sentiment, ("中性", "sentiment-neu"))
    return f'<span class="{cls}">{label}</span>'


# ===================== MAIN UI =====================

col_left, col_mid, col_right = st.columns([1.3, 1.9, 0.9])

# ===== LEFT: Weekly Summary + News Feed =====
with col_left:
    st.markdown("### 📊 本周市场纵览")

    weekly = daily.get_weekly_summary(days=7)

    if weekly["total"] > 0:
        # Weekly metrics
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("周新闻", f"{weekly['total']}条", delta=f"{weekly['days_with_data']}天数据")
        with m2:
            st.metric("利好占比", f"{weekly['pos_pct']}%")
        with m3:
            ratio = weekly['sentiment_ratio']
            label = "偏乐观" if ratio >= 2 else ("偏悲观" if ratio < 0.5 else "中性")
            st.metric("多空比", f"{ratio}:1", delta=label)

        # Hot sectors - clickable
        st.markdown('<p class="section-title">🔥 本周热门板块</p>', unsafe_allow_html=True)
        if weekly.get("hot_sectors"):
            cols = st.columns(2)
            for i, (sector, count) in enumerate(list(weekly["hot_sectors"].items())[:8]):
                with cols[i % 2]:
                    if st.button(f"{sector} ({count})", key=f"sector_{sector}", help=f"查看{sector}板块分析"):
                        st.session_state.quick_prompt = f"请分析{sector}板块的最新动态和投资机会"
                        st.rerun()

        # Hot companies - clickable
        st.markdown('<p class="section-title">🏢 关注公司</p>', unsafe_allow_html=True)
        if weekly.get("hot_companies"):
            cols = st.columns(2)
            for i, comp in enumerate(weekly["hot_companies"][:6]):
                with cols[i % 2]:
                    if st.button(f"{comp['name']} ({comp['mentions']})", key=f"comp_{comp['name']}", help=f"查看{comp['name']}相关分析"):
                        st.session_state.quick_prompt = f"请分析{comp['name']}的最新动态和投资价值"
                        st.rerun()
    else:
        st.info("暂无周度数据。运行爬虫获取：`python src/crawler_agent.py`")

    st.divider()

    # Daily news scroll
    st.markdown("### 📡 今日财经快讯")
    today_news = daily.get_all_recent_news(days=1)
    if today_news:
        top_news = sorted(today_news, key=lambda x: x.get("relevance_score", 0), reverse=True)[:15]
        html = ""
        for item in top_news:
            title = item.get("title", "")
            source = item.get("source", "")
            score = item.get("relevance_score", 0)
            url = item.get("url", "")
            sentiment_badge = render_sentiment_badge(item.get("sentiment", "neutral"))
            companies = "、".join(item.get("companies", [])[:2])
            title_link = f'<a href="{url}" target="_blank">{title}</a>' if url else title
            card = f'<div class="news-card"><div class="news-title">📰 {title_link}</div><div class="news-meta"><span class="score-badge">热度{score}</span><span class="source-tag">📡{source}</span>{sentiment_badge}'
            if companies: card += f'<span>🏢{companies}</span>'
            card += '</div></div>'
            html += card
        st.write(f'<div class="scroll-content"><div class="scroll-track">{html}</div></div>', unsafe_allow_html=True)
    else:
        st.info("暂无今日数据")


# ===== MIDDLE: Chat =====
with col_mid:
    st.markdown("## 📊 金融云历程 — AI股市分析助手")
    st.caption("基于每日财经新闻 + 交易技能框架，提供多维度市场分析")

    init_knowledge_base()

    if "DEEPSEEK_API_KEY" not in st.secrets:
        st.error("请在 .streamlit/secrets.toml 中配置 DEEPSEEK_API_KEY")
        st.stop()

    client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

    SYSTEM_PROMPT = """你是一位资深金融市场分析师，拥有20年A股投资研究经验。

回答规则：
1. 优先基于【参考资料】中的每日财经新闻给出有依据的分析。
2. 分析维度：政策面、资金面、情绪面、基本面。
3. 关注板块轮动、风格切换、重大事件影响。
4. 当参考资料不足时，先说明「以下内容暂无最新新闻数据支撑，由AI基于自身知识回答：」再给出专业分析。
5. 重要提醒：分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。

""" + ts.get_sector_analysis_prompt() + "\n\n" + ts.get_market_news_prompt() + "\n\n" + ts.get_market_environment_prompt()

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if "quick_prompt" not in st.session_state:
        st.session_state.quick_prompt = ""

    chat_container = st.container(height=580, border=False)

    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.markdown(msg.get("display", msg["content"]))

    # Check for quick prompt
    if st.session_state.quick_prompt:
        prompt = st.session_state.quick_prompt
        st.session_state.quick_prompt = ""
    else:
        prompt = st.chat_input("输入您关心的市场问题（如：今天新能源汽车板块有什么动态？）")

    if prompt:
        with st.spinner("检索相关财经资讯..."):
            contexts = kb.query(prompt, n_results=8)
            news_ctx = _get_news_context(prompt)
            if news_ctx: contexts = [news_ctx] + contexts
        context_text = "\n\n---\n\n".join(contexts) if contexts else "暂无直接相关新闻。"

        augmented = f"【参考资料 · 每日财经新闻】\n\n{context_text}\n\n【用户问题】\n{prompt}"
        st.session_state.messages.append({"role": "user", "content": augmented, "display": prompt})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("分析中..."):
                    try:
                        msgs = st.session_state.messages[-11:]
                        if msgs[0]["role"] == "assistant":
                            msgs.insert(0, st.session_state.messages[0])
                        resp = client.chat.completions.create(
                            model="deepseek-chat", messages=msgs, stream=True
                        )
                        full = st.write_stream(resp)
                        st.session_state.messages.append({"role": "assistant", "content": full})
                    except Exception as e:
                        st.error(f"调用出错: {e}")
        st.rerun()


# ===== RIGHT: Trading Sessions & Skills =====
with col_right:
    st.markdown("## ⏰ 交易时段分析")

    # Morning / Afternoon session buttons
    now = datetime.now()
    session_label = "上午盘前" if now.hour < 12 else "下午盘后"

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("☀️ 上午盘前分析", key="morning_btn", help="A股开盘前市场环境分析"):
            st.session_state.quick_prompt = "请做A股上午盘前分析：总结隔夜美股表现、亚太早盘、重大政策新闻，并给出今日关注板块建议。"
            st.rerun()
    with col_b:
        if st.button("🌆 下午盘后分析", key="afternoon_btn", help="A股收盘后复盘总结"):
            st.session_state.quick_prompt = "请做A股下午收盘复盘：总结今日涨跌、板块轮动、资金流向，并给出明日展望。"
            st.rerun()

    st.divider()

    # Today's quick stats (clickable)
    st.markdown("### 📈 今日市场速览")
    summary = daily.get_market_summary(days=1)
    if summary["total"] > 0:
        pos_pct = round(summary["positive"] / max(summary["total"], 1) * 100)
        if st.button(f"📊 今日追踪 {summary['total']} 条新闻 | 利好占比 {pos_pct}%", key="today_stats", help="查看今日市场详情"):
            st.session_state.quick_prompt = "请基于今日财经新闻做完整的市场情绪分析报告"
            st.rerun()

        if summary.get("sectors"):
            for sector, count in list(summary["sectors"].items())[:5]:
                if st.button(f"🔥 {sector}: {count}条", key=f"ts_{sector}", help=f"查看{sector}板块"):
                    st.session_state.quick_prompt = f"请分析{sector}板块今日动态和投资机会"
                    st.rerun()
    else:
        st.caption("今日暂无数据")

    st.divider()

    # Trading Skills - Quick Actions
    st.markdown("### 🛠️ 交易技能分析")

    if st.button("🔄 板块轮动分析 (Sector Rotation)", key="skill_sector"):
        with st.spinner("正在获取板块轮动数据..."):
            result = ts.run_sector_analysis()
        if result.get("success"):
            regime = result["risk_regime"]
            phase_info = result["cycle_phase"]
            phase = phase_info.get("phase", "unknown").title()
            conf = phase_info.get("confidence", "N/A")

            prompt_text = f"""请基于以下板块轮动分析结果，给出A股投资策略建议：

**风险状态**: {regime['regime'].upper()} (评分: {regime['score']}/100)
**周期阶段**: {phase} (置信度: {conf})
**周期性板块均值**: {regime['cyclical_avg_pct']}%
**防御性板块均值**: {regime['defensive_avg_pct']}%
**差异**: {regime['difference_pct']}pp

**领先板块**:
{chr(10).join(f'- {r["sector"]}: {r["ratio_pct"]}%' for r in result.get('ranking', [])[:5])}

请分析当前市场风格并给出配置建议。"""
            st.session_state.quick_prompt = prompt_text
            st.success(f"板块数据已获取 (风险: {regime['regime']}, 阶段: {phase})")
            st.rerun()
        else:
            st.error(f"获取失败: {result.get('error', 'Unknown')}")

    if st.button("📅 经济日历 (Economic Calendar)", key="skill_calendar"):
        result = ts.run_economic_calendar(days=7)
        if result.get("success"):
            events = result.get("high_impact", [])
            prompt_text = "请分析未来7天重大经济事件对A股的影响：\n\n" + json.dumps(events[:10], ensure_ascii=False, indent=2)
            st.session_state.quick_prompt = prompt_text
            st.success(f"获取到 {result['total_events']} 个经济事件")
            st.rerun()
        else:
            st.error(f"需要在 .streamlit/secrets.toml 中配置 FMP_API_KEY")

    if st.button("🌍 市场环境分析 (Market Environment)", key="skill_env"):
        st.session_state.quick_prompt = """请做一次完整的市场环境分析，包括：
1. 当前全球主要股指表现（S&P 500、纳斯达克、上证、恒生）
2. VIX恐慌指数水平和市场情绪
3. 美债收益率和汇率（USD/CNY）对A股的影响
4. 风险偏好判断（Risk-On vs Risk-Off）
5. 当前市场阶段的投资策略建议"""
        st.rerun()

    if st.button("📰 新闻影响分析 (News Impact)", key="skill_news"):
        st.session_state.quick_prompt = """请基于近期财经新闻做系统性的新闻影响分析：
1. 按市场影响程度对近期重大新闻排序
2. 分析每类新闻对A股相关板块的具体影响
3. 识别潜在的投资机会和风险点
4. 评估市场是否已充分消化这些信息"""
        st.rerun()

    st.divider()
    st.caption("⚠️ **免责声明**：本助手分析仅供学习参考，不构成投资建议。投资有风险，入市需谨慎。")
