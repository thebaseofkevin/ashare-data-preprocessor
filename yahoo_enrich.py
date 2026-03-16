"""使用 Yahoo Finance 补充股票数据，并保存到新的 SQLite 数据库。"""

import os
import datetime
import random
import time
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from pandas.api.types import is_scalar

# 可选依赖：用于从 Yahoo Finance 获取更多指标
try:
    import yfinance as yf
except ImportError:
    yf = None

# 保存到 SQLite 需要 sqlalchemy，在导入阶段先检查是否可用
try:
    from sqlalchemy import create_engine
except ImportError:
    create_engine = None  # 后续使用时再抛出明确错误


_YF_LOCK = threading.Lock()

# 标签映射（多名称兼容）
_SHORT_TERM_LOAN_LABELS = [
    "Short Term Loans",
    "Short Term Debt",
    "Current Debt",
    "Short Term Bank Debt",
    "Short/Long Term Debt",
    "Short Long Term Debt",
]
_SHORT_TERM_BORROWING_LABELS = [
    "Short Term Borrowings",
    "Short Term Debt",
    "Current Debt",
    "Short/Long Term Debt",
    "Short Long Term Debt",
]
_OPERATING_EXPENSE_LABELS = [
    "Operating Expense",
    "Operating Expenses",
    "Total Operating Expense",
    "Total Operating Expenses",
]
_RND_LABELS = [
    "Research And Development",
    "Research Development",
    "Research & Development",
    "R&D",
]
_INVESTING_CASH_FLOW_LABELS = [
    "Investing Cash Flow",
    "Total Cash From Investing Activities",
    "Net Cash From Investing Activities",
    "Net Investing Cash Flow",
    "Cash Flow From Investment",
    "Cash Flow From Investing Activities",
    "Cash Flow From Investing",
    "Capital Expenditures",
]
_FINANCING_CASH_FLOW_LABELS = [
    "Financing Cash Flow",
    "Total Cash From Financing Activities",
    "Net Cash From Financing Activities",
    "Net Financing Cash Flow",
    "Cash Flow From Financing Activities",
    "Cash Flow From Financing",
]

_YAHOO_COLS = [
    "website",     # 公司官网
    "total_share", # 总股本
    "market_cap",  # 市值
    "price",       # 当前股价
    "pe",          # 市盈率
    "pb",          # 市净率
    "roe",         # ROE
    "eps",         # 每股收益
    "bps",         # 每股净资产
    "cash",        # 现金总额
    "short_term_borrowing",  # 短期借款（兼容多个标签）
    "gross_profit_margin",   # 毛利率
    "net_profit",            # 净利润
    "operating_expense",     # 营业费用
    "research_and_development",  # 研发费用
    "operating_cash_flow",   # 经营现金流
    "investment_cash_flow",  # 投资现金流（兼容多个标签）
    "financing_cash_flow",   # 筹资现金流（兼容多个标签）
]


def _baostock_to_yahoo(code: str) -> str:
    """把 baostock 代码（如 sh.600000）转换成 Yahoo 代码（如 600000.SS）。"""
    if code.startswith("sh."):
        return code[3:] + ".SS"
    if code.startswith("sz."):
        return code[3:] + ".SZ"
    return code


def _sanitize_value(val):
    """对值做安全清洗：None/NaN/inf 统一转为 None。"""
    if val is None:
        return None
    if isinstance(val, (float, int)):
        if pd.isna(val):
            return None
        if val in (float("inf"), float("-inf")):
            return None
    return val


def _clear_yf_cache():
    """清理 yfinance 缓存，强制刷新 crumb/cookie（应对 Invalid Crumb）。"""
    cache_dirs = [
        os.path.expanduser("~/.cache/yfinance"),
        os.path.expanduser("~/.cache/py-yfinance"),
    ]
    for path in cache_dirs:
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
            except Exception:
                pass


def _should_retry(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "401" in msg
        or "unauthorized" in msg
        or "cookie" in msg
        or "crumb" in msg
        or "invalid crumb" in msg
        or "rate" in msg
    )


def _get_first_match(df: pd.DataFrame, labels):
    if df.empty:
        return None
    for label in labels:
        if label in df.index:
            return df.loc[label].iloc[0]
    return None


def fetch_yahoo(code: str):
    """使用 yfinance 从 Yahoo Finance 拉取补充指标。

    返回 (data, error)。data 是字段字典；失败时返回 ({}, error)。
    失败原因可能是网络拦截、Invalid Crumb、或 Yahoo 无该字段。
    """
    if yf is None:
        return {}, "yfinance not installed"

    ticker = _baostock_to_yahoo(code)
    max_retries = 3
    base_backoff = 1.0
    last_err = None

    for attempt in range(max_retries):
        try:
            with _YF_LOCK:
                tk = yf.Ticker(ticker)
                info = tk.get_info() if hasattr(tk, "get_info") else tk.info
                info = info or {}
                try:
                    _ = tk.fast_info
                except Exception:
                    pass
                balance_sheet = tk.balance_sheet
                income_stmt = tk.financials
                cashflow = tk.cashflow

            if not info and balance_sheet.empty and income_stmt.empty and cashflow.empty:
                try:
                    with _YF_LOCK:
                        _ = tk.history(period="5d")
                        info = tk.get_info() if hasattr(tk, "get_info") else tk.info
                        info = info or {}
                except Exception:
                    pass
            break
        except Exception as e:
            last_err = str(e)
            if "invalid crumb" in last_err.lower():
                _clear_yf_cache()
            if attempt < max_retries - 1 and _should_retry(e):
                sleep_s = min(30.0, base_backoff * (2 ** attempt)) + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                continue
            return {}, last_err
    else:
        return {}, last_err or "unknown error"

    result = {
        "website": info.get("website"),
        "total_share": info.get("sharesOutstanding"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "eps": info.get("trailingEps"),
        "bps": info.get("bookValue"),
        "price": info.get("currentPrice"),
    }

    # 现金总额：优先用资产负债表里的现金与现金等价物
    net_cash = _get_first_match(balance_sheet, ["Cash And Cash Equivalents"])
    if net_cash is None:
        net_cash = info.get("totalCash")
    result["cash"] = net_cash

    # 短期借款：不同股票字段名可能不同，做多标签兼容
    loan_value = _get_first_match(balance_sheet, _SHORT_TERM_LOAN_LABELS)
    borrowing_value = _get_first_match(balance_sheet, _SHORT_TERM_BORROWING_LABELS)
    chosen = loan_value if loan_value is not None else borrowing_value
    if chosen is not None:
        result["short_term_borrowing"] = chosen

    # 利润表
    if not income_stmt.empty:
        gross_profit = _get_first_match(income_stmt, ["Gross Profit"])
        total_revenue = _get_first_match(income_stmt, ["Total Revenue"])
        if gross_profit is not None and total_revenue not in (None, 0):
            result["gross_profit_margin"] = f"{gross_profit / total_revenue:.0%}"

        net_profit = _get_first_match(income_stmt, ["Net Income Continuous Operations"])
        if net_profit is not None:
            result["net_profit"] = net_profit

        op_expense = _get_first_match(income_stmt, _OPERATING_EXPENSE_LABELS)
        if op_expense is not None:
            result["operating_expense"] = op_expense

        rnd = _get_first_match(income_stmt, _RND_LABELS)
        if rnd is not None:
            result["research_and_development"] = rnd

    # 现金流
    if not cashflow.empty:
        operating_cf = _get_first_match(cashflow, ["Operating Cash Flow"])
        if operating_cf is not None:
            result["operating_cash_flow"] = operating_cf

        investing_cf = _get_first_match(cashflow, _INVESTING_CASH_FLOW_LABELS)
        if investing_cf is not None:
            result["investment_cash_flow"] = investing_cf

        financing_cf = _get_first_match(cashflow, _FINANCING_CASH_FLOW_LABELS)
        if financing_cf is not None:
            result["financing_cash_flow"] = financing_cf

    clean = {}
    for k, v in result.items():
        sv = _sanitize_value(v)
        if sv is not None:
            clean[k] = sv

    if not clean:
        return {}, "empty yahoo data"
    return clean, None


def _format_value(col, val):
    if not is_scalar(val):
        return val
    if pd.isna(val):
        return val
    if isinstance(val, str):
        try:
            num = float(val)
        except Exception:
            return val
        if col == "roe":
            return f"{num * 100:.2f}%"
        return f"{num:,}"
    try:
        if col == "roe":
            return f"{val * 100:.2f}%"
        return f"{val:,}"
    except Exception:
        return val


def main():
    if create_engine is None:
        raise ImportError("sqlalchemy is required for database storage; install via pip")

    import argparse

    parser = argparse.ArgumentParser(description="Enrich baostock list with Yahoo Finance data")
    parser.add_argument("--input-db", required=True, help="input SQLite db filename")
    parser.add_argument("--limit", type=int, help="only process the first N rows (for testing)")
    args = parser.parse_args()

    # 生成输出文件名（精确到秒）
    now = datetime.datetime.now()
    output_db = f"{now.strftime('%Y-%m-%d_%H%M%S')}_stocks_info.db"

    if not os.path.exists(args.input_db):
        raise FileNotFoundError(f"Input database {args.input_db} not found. Run baostock_fetch.py first.")

    engine_in = create_engine(f"sqlite:///{args.input_db}")
    df = pd.read_sql("SELECT * FROM stocks", engine_in)
    if args.limit:
        df = df.head(args.limit).copy()

    df = df.drop(columns=["outDate", "type", "status"], errors="ignore")

    for col in _YAHOO_COLS:
        if col not in df.columns:
            df[col] = None

    def enrich_row(idx, row):
        code = row["code"]
        yahoo_data, err = fetch_yahoo(code)
        return idx, yahoo_data, err

    total = len(df)
    print(f"starting enrichment of {total} rows")

    engine_out = create_engine(f"sqlite:///{output_db}")
    df.head(0).to_sql("stocks", engine_out, if_exists="replace", index=False)

    yahoo_hits = 0
    yahoo_empty = 0
    yahoo_errors = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(enrich_row, idx, row): idx for idx, row in df.iterrows()}
        processed = 0
        for future in as_completed(futures):
            idx, yahoo_data, err = future.result()
            processed += 1

            if yahoo_data:
                yahoo_hits += 1
            else:
                yahoo_empty += 1
                if err and len(yahoo_errors) < 5:
                    yahoo_errors.append((df.at[idx, "code"], err))

            for key, value in yahoo_data.items():
                try:
                    df.at[idx, key] = value
                except Exception:
                    pass

            row_df = df.loc[[idx]].copy()
            for col in row_df.columns:
                row_df[col] = row_df[col].apply(lambda v: _format_value(col, v))
            row_df.to_sql("stocks", engine_out, if_exists="append", index=False)

            if processed % 100 == 0 or processed == total:
                print(f"processed {processed}/{total} rows")
            if processed % 200 == 0:
                print(f"processed {processed} rows, sleeping 30 seconds...")
                time.sleep(30)
            if processed % 500 == 0:
                print(f"processed {processed} rows, sleeping 60 seconds...")
                time.sleep(60)

    print(f"yahoo data filled for {yahoo_hits}/{total} rows")
    if yahoo_errors:
        print("sample yahoo errors:")
        for code, err in yahoo_errors:
            print(f"{code}: {err}")
    print(f"enriched and saved {len(df)} rows to {output_db} (table 'stocks')")


if __name__ == '__main__':
    main()
