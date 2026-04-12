#!/usr/bin/env python
"""执行决策分析模块的数据库初始化"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='192.168.1.225',
        port=5432,
        user='postgres',
        password='admin123',
        database='dev_metric'
    )
    cur = conn.cursor()

    # 1. Add category column
    cur.execute("""
        ALTER TABLE prompt_configs ADD COLUMN IF NOT EXISTS category VARCHAR(32) DEFAULT 'general'
    """)
    print('[OK] category column added')

    # 2. Create embedding table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decision_analysis_template_embeddings (
            id SERIAL PRIMARY KEY,
            template_id INT REFERENCES prompt_configs(id),
            embedding_id INT,
            name VARCHAR(64),
            keywords TEXT,
            category VARCHAR(32),
            prompt_preview TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    print('[OK] embedding table created')

    # 3. Insert template
    template_sql = """
    INSERT INTO prompt_configs (name, prompt_text, category, status) VALUES
    ('amazon_ad_analysis',
    '# Amazon Advertising Analysis Template

    ## Industry Benchmarks

    | Metric | Excellent | Good | Average | Poor |
    |-------|-----------|-------|---------|------|
    | ROAS | >4.0 | 3.0-4.0 | 2.0-3.0 | <2.0 |
    | ACOS | <15% | 15%-20% | 20%-25% | >25% |
    | CPC | <1.5 | 1.5-2.5 | 2.5-3.5 | >3.5 |
    | CTR | >1.5% | 1.0%-1.5% | 0.5%-1.0% | <0.5% |

    ## Optimization Suggestions

    - Low ROAS: Optimize keywords, adjust bids, improve landing pages
    - High ACOS: Lower bids, optimize Targeting, adjust budget allocation
    - Low CTR: Optimize ad creative (images/titles), adjust product卖点
    - High CPC: Optimize keyword quality score, adjust match types

    ## Required Insights
    {insights: ["trend", "anomaly", "cycle"]}

    ## Key Metrics
    - ROAS (last {m_time_range}): {metric_roas}
    - ACOS (last {m_time_range}): {metric_acos}%
    - CPC (last {m_time_range}): {metric_cpc}
    - CTR (last {m_time_range}): {metric_ctr}%

    ## Analysis Dimensions
    1. Overall Performance
       - ROAS Analysis: {insight_trend_roas} (based on industry benchmark)
       - ACOS Analysis: {insight_anomaly_acos}

    2. Trend Analysis
       - ROAS Trend: {insight_trend_roas_detail}
       - Anomaly Detection: {insight_anomaly_detail}

    3. Optimization Suggestions
       - Provide actionable recommendations based on metrics and industry benchmarks
    ',
    'decision_analysis',
    1)
    """
    cur.execute(template_sql)
    print('[OK] template inserted')

    conn.commit()
    cur.close()
    conn.close()
    print('\n[Done] All operations completed!')

if __name__ == '__main__':
    main()
