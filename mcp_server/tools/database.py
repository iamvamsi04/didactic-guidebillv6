"""SQLite parser/authorizer is the security boundary, not a keyword regex."""
import sqlite3
import time
from config import settings
from database.connection import connect

TABLES = {'billing_config', 'customers', 'items', 'promotions', 'orders',
          'order_requests', 'order_fulfilled', 'invoice_lines', 'price_history',
          'order_details', 'payments', 'credit_notes', 'billing_disputes', 'billing_audit',
          'product_details', 'product_attributes', 'product_relations', 'product_features',
          'catalogue_current', 'invoice_summary', 'sales_lines', 'json_each'}
FUNCTIONS = set('abs avg coalesce count date datetime glob group_concat hex ifnull '
                'instr julianday length like lower ltrim max min nullif printf replace '
                'round rtrim strftime substr substring sum time total trim typeof '
                'unicode upper row_number rank dense_rank lag lead first_value last_value '
                'json_extract json_type json_valid json_array_length current_date current_time current_timestamp'.split())


def authorize(action, arg1, arg2, db, trigger):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 in TABLES and db in ('main', None):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in FUNCTIONS:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and arg1 == 'table_info' and arg2 in TABLES:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def execute_sql_query(query: str, chart: dict | None = None, parameters: list | None = None) -> dict:
    """Answer flexible questions with one read-only SELECT/WITH or PRAGMA table_info(table).

    Join/filter/group permitted data instead of needing a tool per question. Prefer catalogue_current,
    product_features, product_relations, invoice_summary and sales_lines; inspect columns with PRAGMA.
    Use ? placeholders with parameters for user-provided values; never interpolate names into SQL.
    For requested admin visuals optionally pass chart={"type":"bar","title":"Revenue","x":"month","y":["revenue"]}.
    Types: bar,line,area,pie,scatter. x/y must be returned column aliases; aggregate duplicate x.
    Include a currency column for money and query ONE currency per chart. Order trends chronologically.
    No charts from truncated results. A chart_error leaves query rows usable; correct SQL/spec if needed.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 20000:
        return {'ok': False, 'error': 'Provide one SQL query of at most 20000 characters.'}
    if parameters is not None and (not isinstance(parameters,list) or len(parameters)>100 or
            any(value is not None and not isinstance(value,(str,int,float)) for value in parameters)):
        return {'ok':False,'error':'Parameters must be a list of up to 100 text, numeric or null values.'}
    from mcp_server.access import scope, customer_query_connection
    access = scope.get()
    if chart is not None and (not access or access['mode'] != 'admin'):
        return {'ok': False, 'error': 'Analytics charts require Admin mode.'}
    conn = (customer_query_connection(access['customer_id'])
            if access and access['mode'] == 'customer' else connect(readonly=True))
    try:
        conn.execute('PRAGMA query_only=ON')
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
        conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 20000)
        conn.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
        deadline = time.monotonic() + 2
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        conn.set_authorizer(authorize)
        cursor = conn.execute(query, parameters or [])
        rows = cursor.fetchmany(settings.SQL_MAX_ROWS + 1)
        result = {'ok': True, 'columns': [c[0] for c in cursor.description or []],
                'rows': [list(row) for row in rows[:settings.SQL_MAX_ROWS]],
                'row_count': min(len(rows), settings.SQL_MAX_ROWS),
                'truncated': len(rows) > settings.SQL_MAX_ROWS}
        if chart is not None:
            from mcp_server.charts import prepare_chart
            try:
                payload = prepare_chart(result['columns'],result['rows'],chart,result['truncated'])
                result['chart'] = {key:value for key,value in payload.items() if key != 'data'}
            except ValueError as exc:
                result['chart_error'] = str(exc)
        return result
    except sqlite3.Error as exc:
        return {'ok': False, 'error': f'Query rejected or failed: {exc}'}
    finally:
        conn.close()
