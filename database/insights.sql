-- Additive schema: existing catalogue, orders and financial records are untouched.
CREATE TABLE IF NOT EXISTS product_attributes (
    item_code TEXT NOT NULL REFERENCES items(item_code),
    attribute TEXT NOT NULL COLLATE NOCASE CHECK(length(trim(attribute)) BETWEEN 1 AND 100),
    text_value TEXT CHECK(text_value IS NULL OR length(text_value)<=500),
    number_value REAL CHECK(number_value IS NULL OR abs(number_value)<=1e15),
    unit TEXT CHECK(unit IS NULL OR length(unit)<=30),
    PRIMARY KEY(item_code,attribute),
    CHECK((text_value IS NOT NULL AND number_value IS NULL AND unit IS NULL)
       OR (text_value IS NULL AND number_value IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_attributes_numeric ON product_attributes(attribute,unit,number_value);
CREATE INDEX IF NOT EXISTS ix_attributes_text ON product_attributes(attribute,text_value);
CREATE INDEX IF NOT EXISTS ix_orders_date ON orders(order_date);
CREATE TABLE IF NOT EXISTS product_relations (
    item_code TEXT NOT NULL REFERENCES items(item_code),
    related_item_code TEXT NOT NULL REFERENCES items(item_code),
    relation_type TEXT NOT NULL CHECK(relation_type IN ('substitute','compatible','accessory')),
    notes TEXT NOT NULL DEFAULT '' CHECK(length(notes)<=2000),
    PRIMARY KEY(item_code,related_item_code,relation_type),
    CHECK(item_code<>related_item_code)
);
-- Relations are directional; store the reverse explicitly when appropriate.
CREATE INDEX IF NOT EXISTS ix_relations_reverse ON product_relations(related_item_code,relation_type);

CREATE VIEW IF NOT EXISTS product_features AS
SELECT item_code,attribute,text_value,number_value,unit,'attribute' AS source FROM product_attributes
UNION ALL
SELECT d.item_code,j.key,
       CASE WHEN j.type='text' THEN CAST(j.value AS TEXT) WHEN j.type IN ('true','false') THEN j.type END,
       CASE WHEN j.type IN ('integer','real') THEN j.value END,
       NULL,'features_json'
FROM product_details d JOIN json_each(d.features_json) j
WHERE j.type IN ('text','true','false','integer','real')
AND NOT EXISTS (SELECT 1 FROM product_attributes a WHERE a.item_code=d.item_code AND a.attribute=j.key);

CREATE VIEW IF NOT EXISTS catalogue_current AS
WITH priced AS (
 SELECT i.sku,i.item_code,i.name,i.sellingprice,i.availablequantity,d.category,d.description,
 (SELECT COUNT(*) FROM price_history h WHERE h.item_code=i.item_code AND h.effective_from<=CURRENT_DATE
   AND (h.effective_to IS NULL OR h.effective_to>=CURRENT_DATE)) AS active_price_count,
 (SELECT h.unit_price FROM price_history h WHERE h.item_code=i.item_code AND h.effective_from<=CURRENT_DATE
   AND (h.effective_to IS NULL OR h.effective_to>=CURRENT_DATE) LIMIT 1) AS history_price
 FROM items i LEFT JOIN product_details d ON d.item_code=i.item_code
)
SELECT sku,item_code,name,availablequantity,category,description,
 CASE WHEN active_price_count=0 THEN sellingprice WHEN active_price_count=1 THEN history_price END AS unit_price,
 CASE WHEN active_price_count>1 THEN 'ambiguous' ELSE 'ok' END AS price_status,
 COALESCE((SELECT value FROM billing_config WHERE key='currency'),'USD') AS currency
FROM priced;

-- Exactly one row per invoice; separate aggregates avoid multiplying joined amounts.
CREATE VIEW IF NOT EXISTS invoice_summary AS
WITH balances AS (
 SELECT o.*,COALESCE(d.currency,(SELECT value FROM billing_config WHERE key='currency'),'USD') AS currency,
 d.due_date,
 COALESCE((SELECT SUM(amount_cents) FROM payments p WHERE p.order_id=o.order_id AND p.reversed=0),0)/100.0 AS recorded_payments,
 COALESCE((SELECT SUM(amount_cents) FROM credit_notes c WHERE c.order_id=o.order_id),0)/100.0 AS credits
 FROM orders o LEFT JOIN order_details d ON d.order_id=o.order_id
 WHERE o.order_invoice IS NOT NULL AND COALESCE(d.status,'active')<>'cancelled'
)
SELECT *,ROUND(charged_price-credits-COALESCE(refund_amount,0),2) AS adjusted_total,
 ROUND(MAX(charged_price-credits-COALESCE(refund_amount,0)-recorded_payments,0),2) AS amount_due,
 ROUND(MAX(recorded_payments-(charged_price-credits-COALESCE(refund_amount,0)),0),2) AS customer_credit
FROM balances;

CREATE VIEW IF NOT EXISTS sales_lines AS
SELECT l.id,l.order_id,o.order_date,o.customer_id,l.item_code,i.name,
 l.qty_billed,l.unit_price_billed,l.line_total,
 COALESCE(d.currency,(SELECT value FROM billing_config WHERE key='currency'),'USD') AS currency
FROM invoice_lines l JOIN orders o ON o.order_id=l.order_id JOIN items i ON i.item_code=l.item_code
LEFT JOIN order_details d ON d.order_id=o.order_id
WHERE o.order_invoice IS NOT NULL AND COALESCE(d.status,'active')<>'cancelled';
