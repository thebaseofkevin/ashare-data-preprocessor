"""使用 Yahoo Finance 补充股票数据，并保存到新的 SQLite 数据库。"""
import os
import datetime
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time
import shutil
import threading

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


def _baostock_to_yahoo(code: str) -> str:
    """把 baostock 代码（如 sh.600000）转换成 Yahoo 代码（如 600000.SS）。"""
    if code.startswith("sh."):
        return code[3:] + ".SS"
    elif code.startswith("sz."):
        return code[3:] + ".SZ"
    else:
        return code


def _sanitize_value(val):
    """对值做安全清洗：None/NaN/inf 统一转为 None。"""
    if val is None:
        return None
    # pandas handles its own NaN
    if isinstance(val, (float, int)):
        if pd.isna(val):
            return None
        if val == float("inf") or val == float("-inf"):
            return None
    return val


_YF_LOCK = threading.Lock()


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
    # 根据常见报错关键词判断是否应该重试
    return (
        "401" in msg
        or "unauthorized" in msg
        or "cookie" in msg
        or "crumb" in msg
        or "invalid crumb" in msg
        or "rate" in msg
    )


def fetch_yahoo(code: str):
    """使用 yfinance 从 Yahoo Finance 拉取补充指标。

    返回 (data, error)。data 是字段字典；失败时返回 ({}, error)。
    失败原因可能是网络拦截、Invalid Crumb、或 Yahoo 无该字段。
    """
    if yf is None:
        return {}, "yfinance not installed"
    ticker = _baostock_to_yahoo(code)
    max_retries = 3  # 最大重试次数
    base_backoff = 1.0  # 退避初始秒数
    last_err = None
    for attempt in range(max_retries):
        try:
            # 让 yfinance 自己管理会话（curl_cffi），避免 401/Invalid Crumb
            with _YF_LOCK:
                tk = yf.Ticker(ticker)
                if hasattr(tk, "get_info"):
                    info = tk.get_info() or {}
                else:
                    info = tk.info or {}
                # 拉取财报数据（资产负债表、利润表、现金流表）
                balance_sheet = tk.balance_sheet
                income_stmt = tk.financials
                cashflow = tk.cashflow
            if not info and balance_sheet.empty and income_stmt.empty and cashflow.empty:
                # 先访问一次历史数据“预热”，再重新取 info（可刷新 cookie/crumb）
                try:
                    with _YF_LOCK:
                        _ = tk.history(period="5d")
                        if hasattr(tk, "get_info"):
                            info = tk.get_info() or {}
                        else:
                            info = tk.info or {}
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

    result = {}
    # 映射需要的字段
    result["website"] = info.get("website")
    result["total_share"] = info.get("sharesOutstanding")
    result["pe"] = info.get("trailingPE")
    result["pb"] = info.get("priceToBook")
    result["roe"] = info.get("returnOnEquity")
    result["eps"] = info.get("trailingEps")
    result["bps"] = info.get("bookValue")
    result["cash"] = info.get("totalCash")
    # 短期借款：不同股票字段名可能不同，做多标签兼容
    if not balance_sheet.empty:
        short_term_labels = [
            "Short Term Debt",
            "Short Term Borrowings",
            "Short Term Loans",
            "Current Debt",
            "Short/Long Term Debt",
            "Short Long Term Debt",
            "Short Term Bank Debt",
        ]
        st_value = None
        for label in short_term_labels:
            if label in balance_sheet.index:
                st_value = balance_sheet.loc[label].iloc[0]
                break
        if st_value is not None:
            result["short_term_loan"] = st_value
            result["short_term_borrowing"] = st_value
    # 毛利率：从利润表计算（Gross Profit / Total Revenue）
    if not income_stmt.empty:
        if "Gross Profit" in income_stmt.index and "Total Revenue" in income_stmt.index:
            gross_profit = income_stmt.loc["Gross Profit"].iloc[0]
            total_revenue = income_stmt.loc["Total Revenue"].iloc[0]
            if total_revenue != 0:
                result["gross_profit_margin"] = gross_profit / total_revenue
        if "Net Income" in income_stmt.index:
            result["net_profit"] = income_stmt.loc["Net Income"].iloc[0]
    # 现金流：运营/投资现金流字段名称兼容
    if not cashflow.empty:
        if "Operating Cash Flow" in cashflow.index:
            result["operating_cash_flow"] = cashflow.loc["Operating Cash Flow"].iloc[0]
        investing_labels = [
            "Investing Cash Flow",
            "Total Cash From Investing Activities",
            "Net Cash From Investing Activities",
            "Net Investing Cash Flow",
            "Cash Flow From Investment",
            "Cash Flow From Investing Activities",
            "Cash Flow From Investing",
            "Capital Expenditures",
        ]
        for label in investing_labels:
            if label in cashflow.index:
                result["investment_cash_flow"] = cashflow.loc[label].iloc[0]
                break

    # 清洗结果，剔除不可用值
    clean = {}
    for k, v in result.items():
        sv = _sanitize_value(v)
        if sv is not None:
            clean[k] = sv
    if not clean:
        return {}, "empty yahoo data"
    return clean, None


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
    input_db = args.input_db
    output_db = f"{now.strftime('%Y-%m-%d_%H%M%S')}_stocks_info.db"

    if not os.path.exists(input_db):
        raise FileNotFoundError(f"Input database {input_db} not found. Run baostock_fetch.py first.")

    # 读取输入数据库
    engine_in = create_engine(f"sqlite:///{input_db}")
    df = pd.read_sql("SELECT * FROM stocks", engine_in)

    if args.limit:
        df = df.head(args.limit).copy()

    # 删除不需要的列（保持最终库简洁）
    df = df.drop(columns=["outDate", "type", "status"], errors="ignore")

    # 预先创建 Yahoo 字段，保证输出表结构包含这些列
    yahoo_cols = [
        "website",
        "total_share",
        "pe",
        "pb",
        "roe",
        "eps",
        "bps",
        "cash",
        "short_term_loan",
        "short_term_borrowing",
        "gross_profit_margin",
        "net_profit",
        "operating_cash_flow",
        "investment_cash_flow",
    ]
    for col in yahoo_cols:
        if col not in df.columns:
            df[col] = None

    # 数字格式化：支持数值与可转数字的字符串
    def _format_num(val):
        if pd.isna(val):
            return val
        # handle numeric-like strings as well as numbers
        if isinstance(val, str):
            try:
                num = float(val)
            except Exception:
                return val
            return f"{num:,}"
        try:
            return f"{val:,}"
        except Exception:
            return val

    # 多线程补充 Yahoo 数据
    def enrich_row(idx, row):
        code = row["code"]
        yahoo_data, err = fetch_yahoo(code)
        return idx, yahoo_data, err

    # 使用线程池并发拉取（并发数在 max_workers 控制）
    total = len(df)
    print(f"starting enrichment of {total} rows")

    # 先建立空表，定义输出结构
    engine_out = create_engine(f"sqlite:///{output_db}")
    # 如果表已存在则替换，先写入 0 行用于建表
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
            # update local copy
            for key, value in yahoo_data.items():
                try:
                    df.at[idx, key] = value
                except Exception:
                    pass
            # format numeric columns for this row
            row = df.loc[[idx]].copy()
            for col in row.columns:
                row[col] = row[col].apply(_format_num)
            # append to database
            row.to_sql("stocks", engine_out, if_exists="append", index=False)

            # 打印进度
            if processed % 100 == 0 or processed == total:
                print(f"processed {processed}/{total} rows")
            if processed % 200 == 0:
                print(f"processed {processed} rows, sleeping 30 seconds...")
                time.sleep(30)
            if processed % 1000 == 0:
                print(f"processed {processed} rows, sleeping 120 seconds...")
                time.sleep(60)

    for col in df.columns:
        df[col] = df[col].apply(_format_num)

    # 写入最终数据库
    engine_out = create_engine(f"sqlite:///{output_db}")
    df.to_sql("stocks", engine_out, if_exists="replace", index=False)
    print(f"yahoo data filled for {yahoo_hits}/{total} rows")
    if yahoo_errors:
        print("sample yahoo errors:")
        for code, err in yahoo_errors:
            print(f"{code}: {err}")
    print(f"enriched and saved {len(df)} rows to {output_db} (table 'stocks')")


if __name__ == '__main__':
    main()
