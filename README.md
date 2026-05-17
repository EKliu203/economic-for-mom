# 📊 金融云历程 — AI驱动的股市新闻分析平台

> 实时追踪财经新闻动态，AI驱动多维度市场分析与投资洞察。
> 基于每日新闻数据，结合大语言模型，为投资者提供智能化的市场分析助手。

**金融云历程** 是一个面向A股/港股/美股市场的AI新闻分析平台。它通过每日自动爬取主流财经媒体的新闻，结合RAG（检索增强生成）技术，为用户提供基于实时信息的市场分析、行业洞察和投资参考。

---

## ✨ 功能特点

- **📡 多源新闻聚合** — 自动爬取财联社、东方财富、新浪财经、华尔街见闻等主流媒体的每日财经新闻
- **🔍 智能检索** — 基于 ChromaDB + sentence-transformers 的向量知识库，精准检索相关资讯
- **💬 AI深度分析** — 基于 DeepSeek 大模型的对话式分析，覆盖政策面、资金面、情绪面、基本面
- **📊 市场情绪感知** — 自动识别利好/利空新闻，追踪板块热度和公司关注度
- **⏰ 定时更新** — 每天 08:00 和 20:00 自动执行新闻爬取

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd economic-test
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 编辑 secrets.toml，填入你的 DeepSeek API Key
```

### 3. 运行新闻爬虫（首次）

```bash
python src/crawler_agent.py
```

### 4. 启动应用

```bash
streamlit run streamlit_app.py
```

### 5. 启动定时爬取（可选）

```bash
./run_scheduler.sh
```

---

## 📁 项目结构

```
economic-test/
├── streamlit_app.py          # Streamlit 主界面
├── src/
│   ├── crawler_agent.py      # 多源新闻爬虫
│   ├── daily.py              # 每日新闻读取与筛选
│   ├── knowledge_base.py     # ChromaDB 向量知识库
│   └── scheduler.py          # 定时调度器
├── data/
│   └── financial_knowledge.md # 金融知识文档
├── reference/
│   └── daily/                # 每日新闻 JSON
├── .streamlit/
│   └── secrets.toml.example  # API Key 配置模板
└── requirements.txt
```

## ⚠️ 免责声明

本平台提供的信息和分析仅供学习参考，不构成任何投资建议。投资有风险，入市需谨慎。
