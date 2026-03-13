"""使用 baostock 拉取 A 股基础信息，并保存到 SQLite 数据库。"""
import os
import datetime
import baostock as bs
import pandas as pd

# 保存到 SQLite 需要 sqlalchemy，在导入阶段先检查是否可用
try:
    from sqlalchemy import create_engine
except ImportError:
    create_engine = None  # 后续使用时再抛出明确错误


def login():
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError("baostock login failed")


def logout():
    bs.logout()


def fetch_stock_list():
    """返回包含全部 A 股基础信息的 DataFrame。

    baostock 的基础接口返回 code/name，以及 IPO 日期、退市日期、类型、状态等字段。
    这里仅保留普通股票（type == "1" 且 status == "1"），
    然后再从行业接口补充 industry 字段。
    """
    login()
    rs = bs.query_stock_basic()
    df = rs.get_data()
    # 补充行业分类信息（另一个接口）
    rs2 = bs.query_stock_industry()
    df_ind = rs2.get_data()
    logout()

    # 仅保留正常上市的普通股票
    df = df[(df["type"] == "1") & (df["status"] == "1")]
    # 合并行业信息（大多数 code 能匹配上）
    if not df_ind.empty:
        df = df.merge(df_ind[["code", "industry"]], on="code", how="left")
    return df


def main():
    if create_engine is None:
        raise ImportError("sqlalchemy is required for database storage; install via pip")

    # 以当天日期生成数据库文件名
    today = datetime.date.today().isoformat()
    db_path = f"{today}_stocks_name.db"

    # 拉取基础信息
    basics = fetch_stock_list()

    # 保存到 SQLite
    engine = create_engine(f"sqlite:///{db_path}")
    basics.to_sql("stocks", engine, if_exists="replace", index=False)
    print(f"saved {len(basics)} rows to {db_path} (table 'stocks')")


if __name__ == '__main__':
    main()
