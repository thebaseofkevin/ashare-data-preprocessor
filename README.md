# AShare-Finance-Enricher

本项目使用 `baostock` 获取 A 股基础信息，再用 `yfinance` 补充 Yahoo Finance 指标，并保存到 SQLite 数据库。
同时提供统一入口 `main.py` 便于一键执行。

## 组件说明

- **`baostock_fetch.py`**：拉取 A 股基础信息（code、name、industry 等），保存到 `{日期}_stocks_name.db`（表名：`stocks`）
- **`yahoo_enrich.py`**：读取输入数据库，补充 Yahoo 指标（website、PE、PB、现金流等），并计算 `value_lt_15`。仅将 `market_cap <= 260亿元`（或 `market_cap` 缺失）的股票写入输出库；`market_cap > 260亿元` 会跳过。输出到 `YYYY-MM-DD_HHMMSS_stocks_info.db`（表名：`stocks`）
- **`main.py`**：统一入口，选择执行 `baostock` 或 `yahoo`

## 环境安装

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 使用方法（推荐）

1. 先获取基础股票列表（输出数据库：`{日期}_stocks_name.db`）
   ```bash
   python main.py baostock
   ```

2. 再用 Yahoo Finance 补充数据（可选 `--limit` 仅处理前 N 行用于测试）
   ```bash
   python main.py yahoo --input-db 2026-03-13_stocks_name.db
   ```
   输出示例：`2026-03-13_153012_stocks_info.db`

## 使用方法（直接脚本）

1. 先获取基础股票列表（输出数据库：`{日期}_stocks_name.db`）  
   ```bash
   python baostock_fetch.py
   ```

2. 再用 Yahoo Finance 补充数据（可选 `--limit` 仅处理前 N 行用于测试）  
   ```bash
   python yahoo_enrich.py --input-db 2026-03-13_stocks_name.db
   ```
   输出示例：`2026-03-13_153012_stocks_info.db`，这个数据库的结构如下：
   ``` csv
   "code",        # 股票代码
   "code_name",   # 股票名称
   "ipoDate",     # IPO时间
   "industry",    # 所属行业
   "website",     # 公司官网
   "total_share", # 总股本
   "market_cap",  # 市值
   "price",       # 当前股价
   "pe",          # 市盈率
   "pb",          # 市净率
   "roe",         # ROE
   "eps",         # 每股收益
   "bps",         # 每股净资产
   "cash",        # 现金
   "short_term_borrowing", # 短期借款（兼容多个标签）
   "gross_profit_margin",  # 毛利率（百分比字符串，例如 20%）
   "net_profit",           # 净利润
   "operating_expense",    # 营业费用
   "research_and_development", # 研发费用
   "operating_cash_flow",  # 经营现金流
   "investment_cash_flow", # 投资现金流（兼容多个标签）
   "financing_cash_flow",  # 筹资现金流（兼容多个标签）
   "value_lt_15",          # ((market_cap-(cash-short_term_borrowing))/分母) <= 15
   ```

## 输出字段

- **来自 Baostock**：`code`、`code_name`、`industry` 等基础字段  
- **来自 Yahoo**：`website`、`total_share`、`market_cap`、`price`、`pe`、`pb`、`roe`、`eps`、`bps`、`cash`、  
  `short_term_borrowing`、`gross_profit_margin`、`net_profit`、`operating_expense`、  
  `research_and_development`、`operating_cash_flow`、`investment_cash_flow`、  
  `financing_cash_flow`、`value_lt_15`

## 注意事项

- 需要 Baostock 账号才能登录接口。
- `yfinance` 未安装时会提示 `yfinance not installed`，无法完成 Yahoo 指标补充。
- `sqlalchemy` 未安装时会提示 `sqlalchemy is required for database storage`。
- Yahoo Finance 可能出现 401/Invalid Crumb 等拒绝情况，程序内置重试与退避逻辑，但仍可能部分股票无数据。
- 输出过滤规则：`market_cap > 260亿元人民币` 的股票会跳过，不写入输出数据库。
- `value_lt_15` 计算规则：`((market_cap - (cash - short_term_borrowing)) / 分母) < 15`。分母默认使用 `net_profit`，当 `net_profit <= 0`（或缺失）时改用 `operating_cash_flow`；分母不可用或为 0 时结果为 `NULL`。
- 输出数据库采用当前“秒级时间戳”命名，方便多次运行区分。
