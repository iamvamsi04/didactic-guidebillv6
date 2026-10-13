import json
import sqlite3
import pytest
from config import settings
from database.connection import transaction
from mcp_server.access import scoped_tool
from mcp_server.tools.database import execute_sql_query
from mcp_server.tools.billing_tools import request_order, place_order
from mcp_server.tools.shopping_tools import compare_products
from mcp_server.charts import chart_from_result


def read(query, **kwargs):
    return scoped_tool(execute_sql_query)(query, execution_mode='admin', **kwargs)


def test_generic_attributes_relations_and_current_prices():
    with transaction() as conn:
        conn.execute("INSERT INTO product_details VALUES ('ITEM001','keyboards','Demo',?)",(json.dumps({'connection':'wired','weight':10}),))
        conn.execute("INSERT INTO product_attributes VALUES ('ITEM001','weight',NULL,1.5,'kg')")
        conn.execute("INSERT INTO product_relations VALUES ('ITEM001','ITEM002','accessory','Verified pair')")
        conn.execute("INSERT INTO price_history(item_code,unit_price,effective_from) VALUES ('ITEM001',70,'2000-01-01')")
    result = read("SELECT attribute,text_value,number_value,unit FROM product_features WHERE item_code='ITEM001' ORDER BY attribute")
    assert result['ok'], result
    assert result['rows'] == [['connection','wired',None,None],['weight',None,1.5,'kg']]
    result = read('SELECT unit_price FROM catalogue_current WHERE item_code=?',parameters=['ITEM001'])
    assert result['ok'], result
    assert result['rows'] == [[70]]
    assert read("SELECT related_item_code FROM product_relations WHERE item_code='ITEM001' AND relation_type='accessory'")['rows'] == [['ITEM002']]
    assert read("SELECT * FROM product_relations WHERE item_code='ITEM002'")['rows'] == []
    comparison = compare_products(['ITEM001','ITEM002'])
    assert comparison['products'][0]['features']['weight'] == 1.5
    assert comparison['products'][0]['feature_units']['weight'] == 'kg'
    with pytest.raises(sqlite3.IntegrityError), transaction() as conn:
        conn.execute("INSERT INTO product_attributes VALUES ('MISSING','capacity',NULL,50,'GB')")


def test_invoice_views_do_not_multiply_money_and_remain_scoped():
    order = request_order('CUST001',[{'item_code':'ITEM001','quantity':2}],'ONE')
    assert place_order(order['order_id'],'CUST001')['ok']
    with transaction() as conn:
        for i,amount in enumerate([1000,2000]):
            conn.execute("INSERT INTO payments(payment_id,order_id,amount_cents,currency,received_date,reference,method) VALUES (?,'ONE',?,'USD','2026-01-01',?,'cash')",(f'P{i}',amount,f'REF{i}'))
        for i,amount in enumerate([100,200]):
            conn.execute("INSERT INTO credit_notes(credit_id,order_id,amount_cents,currency,reason) VALUES (?,'ONE',?,'USD','adjustment')",(f'C{i}',amount))
    row = read('SELECT recorded_payments,credits,amount_due FROM invoice_summary')
    assert row['ok'], row
    assert row['rows'] == [[30,3,126.8]]
    assert read('SELECT SUM(line_total) FROM sales_lines')['rows'] == [[159.8]]
    customer = scoped_tool(execute_sql_query)
    assert customer('SELECT * FROM invoice_summary',execution_customer_id='CUST002')['rows'] == []
    assert customer('SELECT * FROM sales_lines',execution_customer_id='CUST002')['rows'] == []
    assert customer('SELECT * FROM product_features',execution_customer_id='CUST001')['ok']


@pytest.mark.parametrize('kind',['bar','line','area','pie','scatter'])
def test_valid_charts_are_materialized_from_executed_rows(kind):
    result = read("SELECT 1 period,10 amount,'USD' currency UNION ALL SELECT 2,20,'USD'",
                  chart={'type':kind,'x':'period','y':['amount'],'title':'Actual query'})
    assert result['ok'] and 'chart' in result, result
    chart = chart_from_result(result)
    assert chart['currency']=='USD' and [r['amount'] for r in chart['data']]==[10,20]
    assert 'data' not in result['chart']  # Avoid duplicating rows in the model tool result.


@pytest.mark.parametrize('query,spec',[
    ("SELECT 'A' x,2 y UNION ALL SELECT 'A',3", {'type':'bar','x':'x','y':['y']}),
    ("SELECT 'A' x,-2 y", {'type':'pie','x':'x','y':['y']}),
    ("SELECT 'A' x,NULL y", {'type':'bar','x':'x','y':['y']}),
    ("SELECT 'A' x,2 y,'USD' currency UNION ALL SELECT 'B',3,'EUR'", {'type':'bar','x':'x','y':['y']}),
    ("SELECT 'A' x,2 y", {'type':'bar','x':'x','y':['invented']}),
    ("SELECT 'A' x,2 y", {'type':'bar','x':'x','y':['y'],'url':'https://invalid.example'}),
])
def test_invalid_charts_preserve_query_results_but_never_attach(query,spec):
    result = read(query,chart=spec)
    assert result['ok'] and 'chart_error' in result and 'chart' not in result


def test_truncation_and_customer_chart_request_rejected(monkeypatch):
    spec = {'type':'bar','x':'x','y':['y']}
    query = "SELECT 'A' x,2 y UNION ALL SELECT 'B',3"
    monkeypatch.setattr(settings,'SQL_MAX_ROWS',1)
    result = read(query,chart=spec)
    assert result['truncated'] and 'chart_error' in result
    assert not scoped_tool(execute_sql_query)(query,chart=spec,execution_customer_id='CUST001')['ok']
