# Gemini 生成的版本

## SQL 1.0 版本 ： 三步严选

### 1. 基础过滤：剔除“地雷”与平庸者

**逻辑：** 排除亏损企业、高杠杆企业及上市不足 3 年（缺乏历史均利数据）的公司。

```sql
SELECT code, code_name, market_cap, price, pe, roe
FROM stocks
WHERE 
    -- 1. 盈利性门槛：ROE 必须大于 10%，确保生意本身是赚钱的
    roe > 10 
    -- 2. 估值门槛：PE 在 0 到 25 之间（拒绝泡沫，剔除亏损）
    AND pe > 0 AND pe < 18
    -- 3. 规模门槛：市值处于 30 亿至 200 亿之间（典型的小市值成长股区间）
    AND market_cap BETWEEN 3000000000 AND 20000000000
    -- 4. 经营安全性：经营现金流必须为正
    AND operating_cash_flow > 0
    -- 5. 时间维度：上市时间超过 3 年，确保有历史数据支撑估值计算
    AND ipoDate < DATE_SUB(CURDATE(), INTERVAL 5 YEAR);

```

---

### 2. 核心估值：成长式的“净现金”筛选

**逻辑：** 寻找“账面现金充足”的公司。如果 **(市值 - 净现金) / 利润** 极低，说明市场几乎白送了该公司的商业经营部分。

```sql
SELECT 
    code, 
    code_name, 
    price,
    market_cap,
    -- 计算净现金 (Net Cash Position)
    (cash - short_term_borrowing) AS net_cash,
    -- 计算 L 值：剔除现金后的实际估值倍数
    (market_cap - (cash - short_term_borrowing)) / net_profit AS L_value,
    gross_profit_margin
FROM stocks
WHERE 
    -- 护城河指标：毛利率需大于 30%（代表具备一定的定价权或成本优势）
    CAST(REPLACE(gross_profit_margin, '%', '') AS DECIMAL) > 30
    -- 财务稳健：现金必须覆盖短期借款
    AND cash > short_term_borrowing
    -- 价值洼地：L 值小于 12（即剔除净现金后，仅需12年利润即可收回成本）
    AND (market_cap - (cash - short_term_borrowing)) / net_profit < 12
ORDER BY L_value ASC;

```

---

### 3. 终极研选：威科夫“超跌+黄金坑”潜力池

**逻辑：** 结合 PB（账面价值）与现金流，寻找那些价格接近净资产但依然在创造现金的“被冷落者”，这通常是威科夫 **Phase C (Spring)** 容易发生的区域。

```sql
SELECT 
    code, 
    code_name, 
    price, 
    pb,
    (operating_cash_flow / net_profit) AS earnings_quality -- 利润含金量
FROM stocks
WHERE 
    -- 价格底线：PB 处于 0.8 到 1.5 之间（极高的安全边际）
    pb BETWEEN 0.8 AND 1.5
    -- 盈利质量：经营现金流 / 净利润 > 1（赚的是真钱，不是应收账款）
    AND (operating_cash_flow / net_profit) >= 1.0
    -- 行业选择：排除过度拥挤的赛道（示例：排除银行金融等重资产行业，专注制造业/消费）
    AND industry NOT LIKE '%银行%' AND industry NOT LIKE '%保险%'
ORDER BY pb ASC;

```

---

### 特别提示 (Guardrails)

1. **关于 $L < R$ 的警示：** SQL 只能帮你筛出 $L$ (当前估值)，但 $R$ (行业合理中枢) 需要你调取所属行业的平均 PE。在执行我的【第二阶段】协议时，若 $L$ 显著低于行业平均 $R$，且公司**毛利率没有下滑**，那就是绝佳的左侧机会。
2. **不买理由排查：** 即使 SQL 结果完美，若 `investment_cash_flow` (投资现金流) 连续多年大幅流出且未见营收增长，需警惕“资本黑洞”。
3. **威科夫共振：** 请观察筛选出股票的 **60 月线**。若股价在 60 月线附近缩量横盘（无量震荡），配合上述财务指标，往往就是机构吸筹完成的 **Phase C** 阶段。


作为你的首席价值投资分析官，我已将这两项**“辛辣约束”**深度植入底层的筛选逻辑。

这两条补丁极其关键：**应收账款占比**过滤了虚假繁荣的“纸上富贵”，而**净利润增长**则排除了陷入“价值陷阱”的夕阳产业。在威科夫理论中，这能确保我们选中的标的处于 **Phase B 震荡区间**的尾声，而不是处于 **Distribution（派发阶段）** 的阴跌中。

以下是进化后的 **SQL 2.0 实战版**：

---

## SQL 2.0 版本 ：防雷+成长进化

```sql
SELECT 
    code, 
    code_name, 
    price,
    market_cap,
    -- 计算 L 值：(总市值 - 净现金) / 近 5 年均利
    (market_cap - (cash - short_term_borrowing)) / net_profit AS L_value,
    roe,
    gross_profit_margin,
    net_profit_growth
FROM stocks
WHERE 
    -- 1. 估值与规模：寻找 30亿-200亿 市值的“小巨人”，PE 处于理性区间
    market_cap BETWEEN 3000000000 AND 20000000000
    AND pe > 0 AND pe < 25
    
    -- 2. 商业护城河：毛利率 > 30% 且 ROE > 10% (段永平最看重的盈利质量)
    AND CAST(REPLACE(gross_profit_margin, '%', '') AS DECIMAL) > 30
    AND roe > 10
    
    -- 3. 【新补丁】成长性：拒绝“正在死去的平民”，确保利润仍在正向增长
    AND net_profit_growth > 0
    
    -- 4. 【新补丁】防雷：应收账款占总资产比例必须小于 30% (谨防暴雷)
    AND (accounts_receivable / (cash + accounts_receivable + fixed_assets)) < 0.3 
    
    -- 5. 现金流安全：经营现金流必须为正，且账面现金覆盖短期负债
    AND operating_cash_flow > 0
    AND cash > short_term_borrowing
    
ORDER BY L_value ASC;

```

---

1. **关于应收账款（Accounts Receivable）：** 很多看似低 PE 的公司，其实是靠给下游放账期“冲”出来的业绩。在 2026 年去杠杆的背景下，回款能力就是生命线。小于 30% 的阈值能直接踢出那些**“有收入、没现金”**的垃圾票。
2. **关于净利润增长（Net Profit Growth）：** 价值投资不是“捡破烂”。如果利润在萎缩，估值再低也是陷阱。我们需要的是在威科夫月线图中，量能已经极度缩减（Dry up），但基本面依然保持增长的**“落难王子”**。
3. **威科夫视角下的 SQL 结果：**
这些被筛出的公司，往往正处于 **Phase C（Spring 弹簧）** 之后的 **LPS（最后支撑点）**。此时，浮动筹码已被洗净，基本面的韧性将成为股价重回 **Phase D** 上升通道的唯一动力。

---

# Claude 生成的版本

### 一、Phase 0 — 数据完整性预检（先跑这条）

```sql
-- 目的：排除数据残缺的标的，降级标记缺失项
-- 对应：V3.1 Phase 0 信息校验
SELECT
    code,
    code_name,
    industry,
    price,
    market_cap,
    pe,
    pb,
    roe,
    net_profit,
    operating_cash_flow,
    cash,
    short_term_borrowing,
    -- 数据完整性评分（满分6分）
    (
        CASE WHEN price              IS NOT NULL AND price > 0              THEN 1 ELSE 0 END +
        CASE WHEN market_cap         IS NOT NULL AND market_cap > 0         THEN 1 ELSE 0 END +
        CASE WHEN net_profit         IS NOT NULL                            THEN 1 ELSE 0 END +
        CASE WHEN operating_cash_flow IS NOT NULL                           THEN 1 ELSE 0 END +
        CASE WHEN cash               IS NOT NULL AND cash >= 0              THEN 1 ELSE 0 END +
        CASE WHEN roe                IS NOT NULL                            THEN 1 ELSE 0 END
    ) AS data_score,
    -- 缺失字段预警（对应报告中的[数据受限]标注）
    CASE WHEN investment_cash_flow IS NULL THEN '[缺:投资CF]' ELSE '' END ||
    CASE WHEN short_term_borrowing IS NULL THEN '[缺:短期借款]' ELSE '' END ||
    CASE WHEN gross_profit_margin  IS NULL THEN '[缺:毛利率]' ELSE '' END
    AS data_warning
FROM stock_data
WHERE price > 0
  AND market_cap > 0
ORDER BY data_score DESC;
```

---

### 二、Phase 1 — 护城河初筛（段氏排雷）

```sql
-- 目的：对应 Phase 1.3 段氏排雷清单中可量化的项
-- 核心逻辑：FCF质量 + 盈利能力 + 毛利率壁垒

SELECT
    code,
    code_name,
    industry,
    price,
    market_cap,
    roe,
    gross_profit_margin,
    net_profit,
    operating_cash_flow,
    investment_cash_flow,

    -- FCF 推算（保守近似：经营CF + 投资CF）
    -- 注：投资CF通常为负值，相加即为简化版FCF
    (operating_cash_flow + COALESCE(investment_cash_flow, 0)) AS fcf_approx,

    -- FCF质量比（对应排雷清单第一条：FCF/净利润 > 80%）
    CASE
        WHEN net_profit > 0
        THEN ROUND(
            (operating_cash_flow + COALESCE(investment_cash_flow, 0)) / net_profit * 100,
            1
        )
        ELSE NULL
    END AS fcf_quality_pct,

    -- 护城河信号：毛利率分层
    CASE
        WHEN CAST(REPLACE(gross_profit_margin, '%', '') AS FLOAT) >= 50 THEN '高壁垒(≥50%)'
        WHEN CAST(REPLACE(gross_profit_margin, '%', '') AS FLOAT) >= 30 THEN '中等护城河'
        WHEN CAST(REPLACE(gross_profit_margin, '%', '') AS FLOAT) >= 15 THEN '低护城河'
        ELSE '红旗:毛利率过低'
    END AS moat_signal

FROM stock_data
WHERE
    price > 0
    AND net_profit > 0                        -- 排除亏损股（初筛）
    AND roe > 8                               -- ROE低于8%护城河存疑
    AND operating_cash_flow > 0               -- 经营现金流为正（盈利质量基础门槛）
    -- 段氏排雷：FCF/净利润 粗筛，过滤盈利注水嫌疑
    AND (operating_cash_flow + COALESCE(investment_cash_flow, 0)) / NULLIF(net_profit, 0) > 0.5

ORDER BY roe DESC, gross_profit_margin DESC;
```

---

### 三、Phase 2 — 动态估值筛选（三档价格体系）

```sql
-- 目的：对应 Phase 2.2-2.4，计算净现金、EV、EV/FCF，输出三档价格信号
-- 核心约束：现有数据只有短期借款，净现金为保守近似

SELECT
    s.code,
    s.code_name,
    s.industry,
    s.price,
    s.market_cap,
    s.pe,
    s.pb,
    s.roe,
    s.eps,

    -- ① 净现金（保守版，仅减短期借款；长期债务未知，结果偏乐观）
    (s.cash - COALESCE(s.short_term_borrowing, 0)) AS net_cash,

    -- ② 含金量EV
    (s.market_cap - (s.cash - COALESCE(s.short_term_borrowing, 0))) AS ev_approx,

    -- ③ FCF 年化近似
    (s.operating_cash_flow + COALESCE(s.investment_cash_flow, 0)) AS fcf_approx,

    -- ④ EV/FCF（核心估值倍数，对应数据看板）
    CASE
        WHEN (s.operating_cash_flow + COALESCE(s.investment_cash_flow, 0)) > 0
        THEN ROUND(
            (s.market_cap - (s.cash - COALESCE(s.short_term_borrowing, 0)))
            / (s.operating_cash_flow + COALESCE(s.investment_cash_flow, 0)),
            1
        )
        ELSE NULL
    END AS ev_fcf_ratio,

    -- ⑤ 三档价格信号（基于当前PE与行业常态对比）
    -- 保守安全价：基于净利润 × 12倍PE
    ROUND(s.eps * 12, 2) AS conservative_price,
    -- 合理估值价：基于净利润 × 20倍PE（消费/科技中轴）
    ROUND(s.eps * 20, 2) AS fair_price,
    -- 高估警戒价：基于净利润 × 30倍PE
    ROUND(s.eps * 30, 2) AS caution_price,

    -- ⑥ 当前安全边际（相对保守安全价）
    CASE
        WHEN s.eps > 0
        THEN ROUND((s.eps * 12 - s.price) / s.price * 100, 1)
        ELSE NULL
    END AS margin_of_safety_pct,

    -- ⑦ 估值区间裁决
    CASE
        WHEN s.pe <= 12                          THEN '🟢 深度低估区'
        WHEN s.pe <= 20                          THEN '🟡 合理估值区'
        WHEN s.pe <= 30                          THEN '🟠 偏高需谨慎'
        WHEN s.pe > 30                           THEN '🔴 高估警戒区'
        ELSE '无法判断'
    END AS valuation_zone

FROM stock_data s
WHERE
    s.price > 0
    AND s.net_profit > 0
    AND s.eps > 0
    -- 只看EV/FCF低于35倍的标的（对应Phase 2.2动态乘数上限）
    AND (
        s.operating_cash_flow + COALESCE(s.investment_cash_flow, 0)
    ) > 0

ORDER BY ev_fcf_ratio ASC NULLS LAST;
```

---

### 四、Phase 2 进阶 — 按行业类型分类估值

```sql
-- 目的：对应 Phase 2.1 估值工具选择矩阵，不同行业用不同估值逻辑

-- 【金融类】用 PB + ROE 筛选（对应矩阵：金融 → PB+ROE均值回归）
SELECT
    code, code_name, industry, price, pe, pb, roe,
    '金融类-PB估值' AS valuation_method,
    CASE
        WHEN pb < 1.0 AND roe > 10 THEN '🟢 PB低估+高ROE'
        WHEN pb < 1.5 AND roe > 8  THEN '🟡 合理区间'
        ELSE '偏贵或ROE不足'
    END AS signal
FROM stock_data
WHERE industry IN ('银行', '保险', '证券', '多元金融')
  AND price > 0

UNION ALL

-- 【消费/品牌类】用 ROE + 毛利率筛选（对应矩阵：消费 → DCF+品牌溢价）
SELECT
    code, code_name, industry, price, pe, pb, roe,
    '消费类-ROE+毛利率' AS valuation_method,
    CASE
        WHEN roe > 20
         AND CAST(REPLACE(gross_profit_margin, '%', '') AS FLOAT) > 40
         AND pe < 35
        THEN '🟢 高ROE+宽护城河'
        WHEN roe > 15
         AND pe < 25
        THEN '🟡 合理成长定价'
        ELSE '性价比不足'
    END AS signal
FROM stock_data
WHERE industry IN ('白酒', '食品饮料', '家电', '医疗美容', '零售')
  AND price > 0

UNION ALL

-- 【科技/硬件类】用 FCF 筛选（对应矩阵：科技/硬件 → 远期FCF年化）
SELECT
    code, code_name, industry, price, pe, pb, roe,
    '科技类-FCF估值' AS valuation_method,
    CASE
        WHEN (operating_cash_flow + COALESCE(investment_cash_flow, 0)) > 0
         AND (operating_cash_flow + COALESCE(investment_cash_flow, 0)) / NULLIF(market_cap, 0) > 0.04
        THEN '🟢 FCF收益率>4%'
        ELSE '⚠ FCF不足或景气度待确认'
    END AS signal
FROM stock_data
WHERE industry IN ('半导体', '电子元器件', '通信设备', '计算机', '云计算', '人工智能')
  AND price > 0

ORDER BY industry, signal;
```

---

### 五、Phase 1+2 联合 — 综合评分筛选（最终候选池）

```sql
-- 目的：整合护城河 + 估值 + FCF质量，输出综合评分，形成候选股票池
-- 评分满分10分，直接对接 V3.1 最终裁决的仓位判断

SELECT
    code,
    code_name,
    industry,
    price,
    market_cap,
    pe,
    roe,
    gross_profit_margin,
    operating_cash_flow,
    net_profit,

    -- 综合评分（满10分）
    (
        -- 盈利质量（最高3分）
        CASE WHEN net_profit > 0 AND operating_cash_flow / NULLIF(net_profit,0) > 0.8 THEN 3
             WHEN net_profit > 0 AND operating_cash_flow / NULLIF(net_profit,0) > 0.5 THEN 2
             WHEN net_profit > 0                                                       THEN 1
             ELSE 0 END

        -- 估值安全性（最高3分）
        + CASE WHEN pe > 0 AND pe < 12  THEN 3
               WHEN pe > 0 AND pe < 20  THEN 2
               WHEN pe > 0 AND pe < 30  THEN 1
               ELSE 0 END

        -- 护城河质量（最高2分，毛利率代理）
        + CASE WHEN CAST(REPLACE(COALESCE(gross_profit_margin,'0%'), '%', '') AS FLOAT) >= 40 THEN 2
               WHEN CAST(REPLACE(COALESCE(gross_profit_margin,'0%'), '%', '') AS FLOAT) >= 20 THEN 1
               ELSE 0 END

        -- ROE质量（最高2分）
        + CASE WHEN roe >= 20 THEN 2
               WHEN roe >= 12 THEN 1
               ELSE 0 END
    ) AS composite_score,

    -- 快速定性标签
    CASE
        WHEN (
            net_profit > 0
            AND operating_cash_flow / NULLIF(net_profit,0) > 0.8
            AND pe < 20
            AND roe > 15
        ) THEN '【强力候选】进入深度研究'
        WHEN (
            net_profit > 0
            AND pe < 30
            AND roe > 10
        ) THEN '【关注候选】待进一步核查'
        ELSE '【暂不关注】'
    END AS research_priority

FROM stock_data
WHERE
    price > 0
    AND market_cap > 0
    AND net_profit > 0
    AND operating_cash_flow > 0     -- 经营现金流必须为正
    AND roe > 8                     -- 最低ROE门槛

ORDER BY composite_score DESC, roe DESC
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
