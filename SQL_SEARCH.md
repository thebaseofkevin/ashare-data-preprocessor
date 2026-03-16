# Gemini 生成的版本

## SQL 1.0 版本 ： 三步严选

### 1. 基础过滤：剔除“地雷”与平庸者

**逻辑：** 排除亏损企业、高杠杆企业及上市不足 3 年（缺乏历史均利数据）的公司。

```sql
WITH cleaned AS (
    SELECT
        code,
        code_name,
        ipoDate,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num
    FROM stocks
)
SELECT code, code_name, market_cap_num AS market_cap, price_num AS price, pe_num AS pe, roe_pct AS roe
FROM cleaned
WHERE 
    -- 1. 盈利性门槛：ROE 必须大于 10%，确保生意本身是赚钱的
    roe_pct > 10
    -- 2. 估值门槛：PE 在 0 到 18 之间（拒绝泡沫，剔除亏损）
    AND pe_num > 0 AND pe_num < 18
    -- 3. 规模门槛：市值处于 30 亿至 200 亿之间（典型的小市值成长股区间）
    AND market_cap_num BETWEEN 3000000000 AND 20000000000
    -- 4. 经营安全性：经营现金流必须为正
    AND operating_cf_num > 0
    -- 5. 时间维度：上市时间超过 3 年，确保有历史数据支撑估值计算
    AND date(ipoDate) < date('now', '-3 years');

```

---

### 2. 核心估值：成长式的“净现金”筛选

**逻辑：** 寻找“账面现金充足”的公司。如果 **(市值 - 净现金) / 利润** 极低，说明市场几乎白送了该公司的商业经营部分。

```sql
WITH cleaned AS (
    SELECT
        code,
        code_name,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(cash, ',', '') AS REAL) AS cash_num,
        CAST(REPLACE(short_term_borrowing, ',', '') AS REAL) AS stb_num,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num,
        CAST(REPLACE(REPLACE(gross_profit_margin, '%', ''), ',', '') AS REAL) AS gpm_pct
    FROM stocks
)
SELECT 
    code, 
    code_name, 
    price_num AS price,
    market_cap_num AS market_cap,
    -- 计算净现金 (Net Cash Position)
    (cash_num - COALESCE(stb_num, 0)) AS net_cash,
    -- 计算 L 值：剔除现金后的实际估值倍数
    (market_cap_num - (cash_num - COALESCE(stb_num, 0))) / NULLIF(net_profit_num, 0) AS L_value,
    gpm_pct AS gross_profit_margin
FROM cleaned
WHERE 
    -- 护城河指标：毛利率需大于 30%（代表具备一定的定价权或成本优势）
    gpm_pct > 30
    -- 盈利质量：净利润必须为正，避免 L 值被负利润扭曲
    AND net_profit_num > 0
    -- 规模基本盘：市值必须为正
    AND market_cap_num > 0
    -- 财务稳健：现金必须覆盖短期借款
    AND cash_num > COALESCE(stb_num, 0)
    -- 价值洼地：L 值小于 12（即剔除净现金后，仅需12年利润即可收回成本）
    AND (market_cap_num - (cash_num - COALESCE(stb_num, 0))) / NULLIF(net_profit_num, 0) < 12
ORDER BY L_value ASC;

```

---

### 3. 终极研选：威科夫“超跌+黄金坑”潜力池

**逻辑：** 结合 PB（账面价值）与现金流，寻找那些价格接近净资产但依然在创造现金的“被冷落者”，这通常是威科夫 **Phase C (Spring)** 容易发生的区域。

```sql
WITH cleaned AS (
    SELECT
        code,
        code_name,
        industry,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(pb, ',', '') AS REAL) AS pb_num,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num
    FROM stocks
)
SELECT 
    code, 
    code_name, 
    price_num AS price, 
    pb_num AS pb,
    (operating_cf_num / NULLIF(net_profit_num, 0)) AS earnings_quality -- 利润含金量
FROM cleaned
WHERE 
    -- 价格底线：PB 处于 0.8 到 1.5 之间（极高的安全边际）
    pb_num BETWEEN 0.8 AND 1.5
    AND pb_num > 0
    -- 盈利与现金流为正，避免负值比值误伤
    AND net_profit_num > 0
    AND operating_cf_num > 0
    -- 盈利质量：经营现金流 / 净利润 > 1（赚的是真钱，不是应收账款）
    AND (operating_cf_num / NULLIF(net_profit_num, 0)) >= 1.0
    -- 行业选择：排除过度拥挤的赛道（示例：排除银行金融等重资产行业，专注制造业/消费）
    AND industry NOT LIKE '%银行%' AND industry NOT LIKE '%保险%'
ORDER BY pb_num ASC;

```

---

### 特别提示 (Guardrails)

1. **关于 $L < R$ 的警示：** SQL 只能帮你筛出 $L$ (当前估值)，但 $R$ (行业合理中枢) 需要你调取所属行业的平均 PE。在执行我的【第二阶段】协议时，若 $L$ 显著低于行业平均 $R$，且公司**毛利率没有下滑**，那就是绝佳的左侧机会。
2. **不买理由排查：** 即使 SQL 结果完美，若 `investment_cash_flow` (投资现金流) 连续多年大幅流出且未见营收增长，需警惕“资本黑洞”。
3. **威科夫共振：** 请观察筛选出股票的 **60 月线**。若股价在 60 月线附近缩量横盘（无量震荡），配合上述财务指标，往往就是机构吸筹完成的 **Phase C** 阶段。


以下是基于当前 `stocks` 表可用字段的 **SQL 2.0 可用版**（移除了 `net_profit_growth`、`accounts_receivable`、`fixed_assets` 等当前库中不存在的字段，侧重现金流与估值安全）：

---

## SQL 2.0 版本 ：防雷+成长进化

```sql
WITH cleaned AS (
    SELECT
        code,
        code_name,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(REPLACE(gross_profit_margin, '%', ''), ',', '') AS REAL) AS gpm_pct,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(cash, ',', '') AS REAL) AS cash_num,
        CAST(REPLACE(short_term_borrowing, ',', '') AS REAL) AS stb_num
    FROM stocks
)
SELECT 
    code, 
    code_name, 
    price_num AS price,
    market_cap_num AS market_cap,
    -- 计算 L 值：(总市值 - 净现金) / 净利润
    (market_cap_num - (cash_num - COALESCE(stb_num, 0))) / NULLIF(net_profit_num, 0) AS L_value,
    roe_pct AS roe,
    gpm_pct AS gross_profit_margin
FROM cleaned
WHERE 
    -- 1. 估值与规模：寻找 30亿-200亿 市值的“小巨人”，PE 处于理性区间
    market_cap_num BETWEEN 3000000000 AND 20000000000
    AND pe_num > 0 AND pe_num < 25
    
    -- 2. 商业护城河：毛利率 > 30% 且 ROE > 10% (段永平最看重的盈利质量)
    AND gpm_pct > 30
    AND roe_pct > 10
    
    -- 3. 现金流安全：经营现金流必须为正，且账面现金覆盖短期负债
    AND operating_cf_num > 0
    AND cash_num > COALESCE(stb_num, 0)
    -- 4. 盈利为正，避免 L 值失真
    AND net_profit_num > 0
    
ORDER BY L_value ASC;

```

---

1. **关于应收账款与利润增长：** 当前 `stocks` 表未包含 `accounts_receivable`、`fixed_assets`、`net_profit_growth` 等字段，若需要“回款质量”和“增长性”筛选，请先扩充数据源或在入库阶段补齐字段。
2. **威科夫视角下的 SQL 结果：**
这些被筛出的公司，往往正处于 **Phase C（Spring 弹簧）** 之后的 **LPS（最后支撑点）**。此时，浮动筹码已被洗净，基本面的韧性将成为股价重回 **Phase D** 上升通道的唯一动力。

---

# Claude 生成的版本

### 一、Phase 0 — 数据完整性预检（先跑这条）

```sql
-- 目的：排除数据残缺的标的，降级标记缺失项
-- 对应：V3.1 Phase 0 信息校验
WITH cleaned AS (
    SELECT
        *,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(pb, ',', '') AS REAL) AS pb_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(cash, ',', '') AS REAL) AS cash_num,
        CAST(REPLACE(short_term_borrowing, ',', '') AS REAL) AS stb_num
    FROM stocks
)
SELECT
    code,
    code_name,
    industry,
    price_num AS price,
    market_cap_num AS market_cap,
    pe_num AS pe,
    pb_num AS pb,
    roe_pct AS roe,
    net_profit_num AS net_profit,
    operating_cf_num AS operating_cash_flow,
    cash_num AS cash,
    stb_num AS short_term_borrowing,
    -- 数据完整性评分（满分6分）
    (
        CASE WHEN price_num              IS NOT NULL AND price_num > 0              THEN 1 ELSE 0 END +
        CASE WHEN market_cap_num         IS NOT NULL AND market_cap_num > 0         THEN 1 ELSE 0 END +
        CASE WHEN net_profit_num         IS NOT NULL                                THEN 1 ELSE 0 END +
        CASE WHEN operating_cf_num       IS NOT NULL                                THEN 1 ELSE 0 END +
        CASE WHEN cash_num               IS NOT NULL AND cash_num >= 0              THEN 1 ELSE 0 END +
        CASE WHEN roe_pct                IS NOT NULL                                THEN 1 ELSE 0 END
    ) AS data_score,
    -- 缺失字段预警（对应报告中的[数据受限]标注）
    CASE WHEN investment_cash_flow IS NULL THEN '[缺:投资CF]' ELSE '' END ||
    CASE WHEN short_term_borrowing IS NULL THEN '[缺:短期借款]' ELSE '' END ||
    CASE WHEN gross_profit_margin  IS NULL THEN '[缺:毛利率]' ELSE '' END
    AS data_warning
FROM cleaned
WHERE price_num > 0
  AND market_cap_num > 0
ORDER BY data_score DESC;
```

---

### 二、Phase 1 — 护城河初筛（段氏排雷）

```sql
-- 目的：对应 Phase 1.3 段氏排雷清单中可量化的项
-- 核心逻辑：FCF质量 + 盈利能力 + 毛利率壁垒

WITH cleaned AS (
    SELECT
        code,
        code_name,
        industry,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(REPLACE(gross_profit_margin, '%', ''), ',', '') AS REAL) AS gpm_pct,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(investment_cash_flow, ',', '') AS REAL) AS investment_cf_num
    FROM stocks
)
SELECT
    code,
    code_name,
    industry,
    price_num AS price,
    market_cap_num AS market_cap,
    roe_pct AS roe,
    gpm_pct AS gross_profit_margin,
    net_profit_num AS net_profit,
    operating_cf_num AS operating_cash_flow,
    investment_cf_num AS investment_cash_flow,

    -- FCF 推算（保守近似：经营CF + 投资CF）
    -- 注：投资CF通常为负值，相加即为简化版FCF
    (operating_cf_num + COALESCE(investment_cf_num, 0)) AS fcf_approx,

    -- FCF质量比（对应排雷清单第一条：FCF/净利润 > 80%）
    CASE
        WHEN net_profit_num > 0
        THEN ROUND(
            (operating_cf_num + COALESCE(investment_cf_num, 0)) / net_profit_num * 100,
            1
        )
        ELSE NULL
    END AS fcf_quality_pct,

    -- 护城河信号：毛利率分层
    CASE
        WHEN gpm_pct >= 50 THEN '高壁垒(≥50%)'
        WHEN gpm_pct >= 30 THEN '中等护城河'
        WHEN gpm_pct >= 15 THEN '低护城河'
        ELSE '红旗:毛利率过低'
    END AS moat_signal

FROM cleaned
WHERE
    price_num > 0
    AND net_profit_num > 0                    -- 排除亏损股（初筛）
    AND roe_pct > 8                           -- ROE低于8%护城河存疑
    AND operating_cf_num > 0                  -- 经营现金流为正（盈利质量基础门槛）
    -- 段氏排雷：FCF/净利润 粗筛，过滤盈利注水嫌疑
    AND (operating_cf_num + COALESCE(investment_cf_num, 0)) / NULLIF(net_profit_num, 0) > 0.5

ORDER BY roe_pct DESC, gpm_pct DESC;
```

---

### 三、Phase 2 — 动态估值筛选（三档价格体系）

```sql
-- 目的：对应 Phase 2.2-2.4，计算净现金、EV、EV/FCF，输出三档价格信号
-- 核心约束：现有数据只有短期借款，净现金为保守近似

WITH cleaned AS (
    SELECT
        code,
        code_name,
        industry,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(pb, ',', '') AS REAL) AS pb_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(eps, ',', '') AS REAL) AS eps_num,
        CAST(REPLACE(cash, ',', '') AS REAL) AS cash_num,
        CAST(REPLACE(short_term_borrowing, ',', '') AS REAL) AS stb_num,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(investment_cash_flow, ',', '') AS REAL) AS investment_cf_num,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num
    FROM stocks
)
SELECT
    code,
    code_name,
    industry,
    price_num AS price,
    market_cap_num AS market_cap,
    pe_num AS pe,
    pb_num AS pb,
    roe_pct AS roe,
    eps_num AS eps,

    -- ① 净现金（保守版，仅减短期借款；长期债务未知，结果偏乐观）
    (cash_num - COALESCE(stb_num, 0)) AS net_cash,

    -- ② 含金量EV
    (market_cap_num - (cash_num - COALESCE(stb_num, 0))) AS ev_approx,

    -- ③ FCF 年化近似
    (operating_cf_num + COALESCE(investment_cf_num, 0)) AS fcf_approx,

    -- ④ EV/FCF（核心估值倍数，对应数据看板）
    CASE
        WHEN (operating_cf_num + COALESCE(investment_cf_num, 0)) > 0
        THEN ROUND(
            (market_cap_num - (cash_num - COALESCE(stb_num, 0)))
            / (operating_cf_num + COALESCE(investment_cf_num, 0)),
            1
        )
        ELSE NULL
    END AS ev_fcf_ratio,

    -- ⑤ 三档价格信号（基于当前PE与行业常态对比）
    -- 保守安全价：基于净利润 × 12倍PE
    ROUND(eps_num * 12, 2) AS conservative_price,
    -- 合理估值价：基于净利润 × 20倍PE（消费/科技中轴）
    ROUND(eps_num * 20, 2) AS fair_price,
    -- 高估警戒价：基于净利润 × 30倍PE
    ROUND(eps_num * 30, 2) AS caution_price,

    -- ⑥ 当前安全边际（相对保守安全价）
    CASE
        WHEN eps_num > 0 AND price_num > 0
        THEN ROUND((eps_num * 12 - price_num) / price_num * 100, 1)
        ELSE NULL
    END AS margin_of_safety_pct,

    -- ⑦ 估值区间裁决
    CASE
        WHEN pe_num <= 12                          THEN '🟢 深度低估区'
        WHEN pe_num <= 20                          THEN '🟡 合理估值区'
        WHEN pe_num <= 30                          THEN '🟠 偏高需谨慎'
        WHEN pe_num > 30                           THEN '🔴 高估警戒区'
        ELSE '无法判断'
    END AS valuation_zone

FROM cleaned
WHERE
    price_num > 0
    AND net_profit_num > 0
    AND eps_num > 0
    -- 只看EV/FCF低于35倍的标的（对应Phase 2.2动态乘数上限）
    AND (operating_cf_num + COALESCE(investment_cf_num, 0)) > 0

ORDER BY (ev_fcf_ratio IS NULL), ev_fcf_ratio ASC;
```

---

### 四、Phase 2 进阶 — 按行业类型分类估值

```sql
-- 目的：对应 Phase 2.1 估值工具选择矩阵，不同行业用不同估值逻辑

WITH cleaned AS (
    SELECT
        code,
        code_name,
        industry,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(pb, ',', '') AS REAL) AS pb_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(REPLACE(gross_profit_margin, '%', ''), ',', '') AS REAL) AS gpm_pct,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(investment_cash_flow, ',', '') AS REAL) AS investment_cf_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num
    FROM stocks
)
-- 【金融类】用 PB + ROE 筛选（对应矩阵：金融 → PB+ROE均值回归）
SELECT
    code, code_name, industry, price_num AS price, pe_num AS pe, pb_num AS pb, roe_pct AS roe,
    '金融类-PB估值' AS valuation_method,
    CASE
        WHEN pb_num < 1.0 AND roe_pct > 10 THEN '🟢 PB低估+高ROE'
        WHEN pb_num < 1.5 AND roe_pct > 8  THEN '🟡 合理区间'
        ELSE '偏贵或ROE不足'
    END AS signal
FROM cleaned
WHERE industry IN ('银行', '保险', '证券', '多元金融')
  AND price_num > 0

UNION ALL

-- 【消费/品牌类】用 ROE + 毛利率筛选（对应矩阵：消费 → DCF+品牌溢价）
SELECT
    code, code_name, industry, price_num AS price, pe_num AS pe, pb_num AS pb, roe_pct AS roe,
    '消费类-ROE+毛利率' AS valuation_method,
    CASE
        WHEN roe_pct > 20
         AND gpm_pct > 40
         AND pe_num < 35
        THEN '🟢 高ROE+宽护城河'
        WHEN roe_pct > 15
         AND pe_num < 25
        THEN '🟡 合理成长定价'
        ELSE '性价比不足'
    END AS signal
FROM cleaned
WHERE industry IN ('白酒', '食品饮料', '家电', '医疗美容', '零售')
  AND price_num > 0

UNION ALL

-- 【科技/硬件类】用 FCF 筛选（对应矩阵：科技/硬件 → 远期FCF年化）
SELECT
    code, code_name, industry, price_num AS price, pe_num AS pe, pb_num AS pb, roe_pct AS roe,
    '科技类-FCF估值' AS valuation_method,
    CASE
        WHEN (operating_cf_num + COALESCE(investment_cf_num, 0)) > 0
         AND (operating_cf_num + COALESCE(investment_cf_num, 0)) / NULLIF(market_cap_num, 0) > 0.04
        THEN '🟢 FCF收益率>4%'
        ELSE '⚠ FCF不足或景气度待确认'
    END AS signal
FROM cleaned
WHERE industry IN ('半导体', '电子元器件', '通信设备', '计算机', '云计算', '人工智能')
  AND price_num > 0

ORDER BY industry, signal;
```

---

### 五、Phase 1+2 联合 — 综合评分筛选（最终候选池）

```sql
-- 目的：整合护城河 + 估值 + FCF质量，输出综合评分，形成候选股票池
-- 评分满分10分，直接对接 V3.1 最终裁决的仓位判断

WITH cleaned AS (
    SELECT
        code,
        code_name,
        industry,
        CAST(REPLACE(price, ',', '') AS REAL) AS price_num,
        CAST(REPLACE(market_cap, ',', '') AS REAL) AS market_cap_num,
        CAST(REPLACE(pe, ',', '') AS REAL) AS pe_num,
        CAST(REPLACE(REPLACE(roe, '%', ''), ',', '') AS REAL) AS roe_pct,
        CAST(REPLACE(REPLACE(gross_profit_margin, '%', ''), ',', '') AS REAL) AS gpm_pct,
        CAST(REPLACE(operating_cash_flow, ',', '') AS REAL) AS operating_cf_num,
        CAST(REPLACE(net_profit, ',', '') AS REAL) AS net_profit_num
    FROM stocks
)
SELECT
    code,
    code_name,
    industry,
    price_num AS price,
    market_cap_num AS market_cap,
    pe_num AS pe,
    roe_pct AS roe,
    gpm_pct AS gross_profit_margin,
    operating_cf_num AS operating_cash_flow,
    net_profit_num AS net_profit,

    -- 综合评分（满10分）
    (
        -- 盈利质量（最高3分）
        CASE WHEN net_profit_num > 0 AND operating_cf_num / NULLIF(net_profit_num,0) > 0.8 THEN 3
             WHEN net_profit_num > 0 AND operating_cf_num / NULLIF(net_profit_num,0) > 0.5 THEN 2
             WHEN net_profit_num > 0                                                       THEN 1
             ELSE 0 END

        -- 估值安全性（最高3分）
        + CASE WHEN pe_num > 0 AND pe_num < 12  THEN 3
               WHEN pe_num > 0 AND pe_num < 20  THEN 2
               WHEN pe_num > 0 AND pe_num < 30  THEN 1
               ELSE 0 END

        -- 护城河质量（最高2分，毛利率代理）
        + CASE WHEN COALESCE(gpm_pct, 0) >= 40 THEN 2
               WHEN COALESCE(gpm_pct, 0) >= 20 THEN 1
               ELSE 0 END

        -- ROE质量（最高2分）
        + CASE WHEN roe_pct >= 20 THEN 2
               WHEN roe_pct >= 12 THEN 1
               ELSE 0 END
    ) AS composite_score,

    -- 快速定性标签
    CASE
        WHEN (
            net_profit_num > 0
            AND operating_cf_num / NULLIF(net_profit_num,0) > 0.8
            AND pe_num < 20
            AND roe_pct > 15
        ) THEN '【强力候选】进入深度研究'
        WHEN (
            net_profit_num > 0
            AND pe_num < 30
            AND roe_pct > 10
        ) THEN '【关注候选】待进一步核查'
        ELSE '【暂不关注】'
    END AS research_priority

FROM cleaned
WHERE
    price_num > 0
    AND market_cap_num > 0
    AND net_profit_num > 0
    AND operating_cf_num > 0     -- 经营现金流必须为正
    AND roe_pct > 8              -- 最低ROE门槛

ORDER BY composite_score DESC, roe_pct DESC
LIMIT 50;  -- 控制候选池规模
```

---

### 附：数据局限性备忘

| V3.1 分析项 | 当前数据支持度 | 缺口与建议 |
|---|---|---|
| FCF 计算 | 约 70% | 缺 CAPEX 明细，用经营CF+投资CF近似 |
| 净现金 | 约 60% | 仅有短期借款，缺长期债，结果偏乐观，需标注 `[数据受限]` |
| 排雷清单 | 约 40% | 商誉、关联交易、研发资本化率均缺失 |
| 威科夫量价 | 0% | 需接入行情数据库（日K线 + 成交量） |
| 行业 CAPEX 增速 | 0% | 需接入行业数据或手工维护 |
| 管线/催化剂 | 0% | 医药类需单独数据源 |
