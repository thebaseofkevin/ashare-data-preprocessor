# AShare-Finance-Enricher

本项目使用 `baostock` 获取 A 股基础信息，再用 `yfinance` 补充 Yahoo Finance 指标，并保存到 SQLite 数据库。

## 组件说明

- **`baostock_fetch.py`**：拉取 A 股基础信息（code、name、industry 等），保存到 `{日期}_stocks_name.db`
- **`yahoo_enrich.py`**：读取输入数据库，补充 Yahoo 指标（website、PE、PB、现金流等），输出到 `YYYY-MM-DD_HHMMSS_stocks_info.db`

## 环境安装

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 使用方法

1. 先获取基础股票列表（输出数据库：`{日期}_stocks_name.db`）  
   ```bash
   python baostock_fetch.py
   ```

2. 再用 Yahoo Finance 补充数据  
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
   "gross_profit_margin",  # 毛利率
   "net_profit",           # 净利润
   "operating_cash_flow",  # 经营现金流
   "investment_cash_flow", # 投资现金流（兼容多个标签）
   ```

## 输出字段

- **来自 Baostock**：`code`、`code_name`、`industry` 等基础字段  
- **来自 Yahoo**：`website`、`total_share`、`pe`、`pb`、`roe`、`eps`、`bps`、`cash`、  
  `short_term_loan`、`short_term_borrowing`、`gross_profit_margin`、`net_profit`、  
  `operating_cash_flow`、`investment_cash_flow`

## 注意事项

- 需要 Baostock 账号才能登录接口。
- Yahoo Finance 可能出现 401/Invalid Crumb 等拒绝情况，程序内置重试与退避逻辑，但仍可能部分股票无数据。
- 输出数据库采用当前“秒级时间戳”命名，方便多次运行区分。
