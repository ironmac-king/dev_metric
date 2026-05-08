#!/usr/bin/env python3
"""Test 50 query questions for the AI ask service"""

import requests
import json
import sys

def test_query(question, session_id):
    url = 'http://localhost:8081/api/v1/ask'
    data = {'question': question, 'session_id': session_id}
    try:
        response = requests.post(url, json=data, timeout=120)
        result = response.json()
        sql = result.get('sql', 'N/A')
        answer = result.get('answer', 'N/A')
        # Check for errors in answer
        has_error = False
        if not answer or len(answer) < 5:
            has_error = True
        error_keywords = ['ERROR', '错误', '异常', '失败', '抱歉', '无法', '出错']
        for kw in error_keywords:
            if kw.lower() in answer.lower():
                has_error = True
                break
        status = 'ERROR' if has_error else 'OK'
        return status, sql, answer, None
    except Exception as e:
        return 'EXCEPTION', None, None, str(e)

# 50 test questions
questions = [
    ("今年一季度广告花费整体变化趋势", "test-01"),
    ("2026年3月份B2B APP的会话量总计是多少？", "test-02"),
    ("截止到2026年一季度末，我们的广告花费总额达到了多少？", "test-03"),
    ("2026年3月网页端页面访问量环比2月份有增长吗？", "test-04"),
    ("2026年第一季度B2B渠道的总销量是多少件？", "test-05"),
    ("2026年3月份B2B业务的退货订单量总共有多少单？", "test-06"),
    ("截止到2026年3月31日，全平台的总退货订单共有多少笔？", "test-07"),
    ("2026年前三个月，网页端的总会话量趋势如何？", "test-08"),
    ("2026年3月份APP端页面访问量最高的是哪一天？", "test-09"),
    ("2026年第一季度B2B APP端页面访问量总计多少？", "test-10"),
    ("截止到2026年3月底，B2B网页端页面访问量累计是多少？", "test-11"),
    ("2026年3月份通过广告带来的平均客单价是多少？", "test-12"),
    ("2026年第一季度B2B网页端会话量占整体会话量的比例是多少？", "test-13"),
    ("2026年3月份我们在各平台的黄金购物车占比平均是多少？", "test-14"),
    ("截止到2026年3月底，今年的累计总销售额是多少？", "test-15"),
    ("2026年第一季度的整体广告产出比(ROAS)表现如何？", "test-16"),
    ("2026年3月份全平台广告的总点击量是多少？", "test-17"),
    ("2026年前三个月的平均单次转化成本(CPA)是多少？", "test-18"),
    ("2026年3月份的广告销售成本比(ACOS)的具体数值是多少？", "test-19"),
    ("截止到2026年3月底，整体的点击转化率达到了百分之多少？", "test-20"),
    ("2026年第一季度由广告直接带动的销售额有多少？", "test-21"),
    ("2026年3月份广告的平均单次点击成本(CPC)是多少？", "test-22"),
    ("2026年前三个月通过广告渠道共获取了多少笔订单？", "test-23"),
    ("2026年3月份全平台的总页面访问量是多少？", "test-24"),
    ("截止到2026年3月底，今年累计的总会话量是多少？", "test-25"),
    ("2026年第一季度B2B渠道总共贡献了多少销售额？", "test-26"),
    ("2026年3月份的整体广告转化率是多少？", "test-27"),
    ("截止到2026年3月底，B2B业务线带来的总会话量是多少？", "test-28"),
    ("2026年第一季度各渠道的平均点击转化率是多少？", "test-29"),
    ("2026年3月份APP端的日均会话量是多少？", "test-30"),
    ("截止到2026年3月底，今年全平台的总销量达到了多少？", "test-31"),
    ("2026年3月份全平台总共产生了多少笔订单？", "test-32"),
    ("2026年前三个月B2B业务的总订单量是多少？", "test-33"),
    ("2026年第一季度不含税产品成本累计是多少？", "test-34"),
    ("截止到2026年3月底，今年累计产生的关税总额是多少？", "test-35"),
    ("2026年3月份我们支出的化学税是多少？", "test-36"),
    ("2026年3月全渠道的含税总收入达到了多少？", "test-37"),
    ("2026年第一季度发生的退款总金额是多少？", "test-38"),
    ("2026年3月份的快递费支出比2月份增加了吗？", "test-39"),
    ("截止到2026年3月底，今年的咨询服务费总计支出多少？", "test-40"),
    ("2026年第一季度各业务线的地方消费税汇总数值是多少？", "test-41"),
    ("2026年3月份单笔订单的平均包装物成本是多少？", "test-42"),
    ("2026年3月份总共有多少笔退款数量？", "test-43"),
    ("截止到2026年3月底，今年累计的运输费用是多少？", "test-44"),
    ("2026年第一季度我们支付了多少售后服务费？", "test-45"),
    ("2026年3月份产生的进口消费税总额是多少？", "test-46"),
    ("2026年第一季度媒体推广费的月度分配情况如何？", "test-47"),
    ("截止到2026年3月底，今年实际支出的垃圾处理费有多少？", "test-48"),
    ("2026年第一季度预缴的所得税总额是多少？", "test-49"),
    ("2026年3月份平台扣除的佣金总计是多少？", "test-50"),
]

results = []
for i, (question, session_id) in enumerate(questions, 1):
    print(f'[{i}/50] Testing: {question[:40]}...', end=' ')
    sys.stdout.flush()
    status, sql, answer, error = test_query(question, session_id)
    results.append((i, question, status, sql, answer, error))
    if status == 'OK':
        print(f'[{status}]')
    else:
        print(f'[{status}]')
        if error:
            print(f'  Error: {error[:100]}')
        elif answer:
            try:
                print(f'  Answer preview: {answer[:150]}')
            except UnicodeEncodeError:
                print(f'  Answer preview: (Unicode error)')
        if sql:
            print(f'  SQL: {sql[:100] if sql else "N/A"}')

# Summary
ok_count = sum(1 for r in results if r[2] == 'OK')
error_count = sum(1 for r in results if r[2] == 'ERROR')
exception_count = sum(1 for r in results if r[2] == 'EXCEPTION')

print('\n' + '='*60)
print(f'TEST SUMMARY: OK={ok_count}, ERROR={error_count}, EXCEPTION={exception_count}')
print('='*60)

# List errors
if error_count > 0 or exception_count > 0:
    print('\nFailed tests:')
    for i, question, status, sql, answer, error in results:
        if status != 'OK':
            print(f'  [{i}] {question[:50]} - {status}')
            if error:
                print(f'      Error: {error[:100]}')
            if sql:
                print(f'      SQL: {sql[:100] if sql else "N/A"}')
