import { format } from 'sql-formatter'

export function formatSQL(sql) {
  if (!sql) return ''
  return format(sql, {
    language: 'mysql',
    tabWidth: 2,
    keywordCase: 'upper',
  })
}
