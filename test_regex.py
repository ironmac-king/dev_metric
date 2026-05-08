import re

sql = """SELECT
        sum(SESSIONS_TOTAL) as `SESSIONS_TOTAL`
FROM dws.DWS_IMC_BUSINESSREPORT
WHERE 1=1"""

# Current regex
matches = re.findall(r'(?:sum\()?([\w]+)\)?(?:\s+as\s+[\w]+)?', sql, re.IGNORECASE)
print('Current regex matches:', matches)

# Fixed regex - handle backticks around alias
matches2 = re.findall(r'(?:sum\()?([\w]+)\)?(?:\s+as\s*`?([\w]+)`?)?', sql, re.IGNORECASE)
print('Fixed regex matches:', matches2)
