# Billing analytics in version 5

billing_analysis and billing_anomalies are included among the twelve tools and are exposed to authenticated Admin conversations. Customer conversations use the shopping tools and scoped SQL. app_analytics.py remains a compatible alternate entry point with the same mode enforcement; it does not bypass admin access. See WORKFLOWS.md for admin setup.

billing_analysis summarizes invoice face values, discounts, tax, shipping, ledger refunds, top customers/products and current-cost estimates. Filters are customer_id, order_id and inclusive order-date range. top_n limits only the displayed rankings. Drafts and cancelled orders do not contribute to financial totals.

billing_anomalies checks invoice arithmetic, quantities, refund metadata, unusually high invoice amounts and dated prices. It returns evidence and review suggestions for margin pressure, refunds or excess stock. It does not predict fraud or execute cost changes.

Costs use current baseprice; historical purchase cost and overhead are unavailable. Product revenue precedes order-level discounts, taxes, shipping and refunds. Legacy payments and credit notes are not included in face-value totals. These totals do not prove bank settlement. Mixed-currency selections require narrower filters.

Customer-facing replies must not reveal internal procurement costs or margins. Shopping comparisons use compare_products and find_cheaper_alternatives, which return public selling prices and recorded product facts. See WORKFLOWS.md and CUSTOMER_CONVERSATIONS.md.

## Pictorial analytics

When asked for a chart, the admin agent uses the existing execute_sql_query tool with chart metadata. For example:

```json
{
  "query": "SELECT strftime('%Y-%m',order_date) AS month, currency, ROUND(SUM(charged_price),2) AS billed_revenue FROM invoice_summary WHERE currency=? GROUP BY month,currency ORDER BY month",
  "parameters": ["USD"],
  "chart": {"type":"line","title":"Monthly billed revenue (USD)","x":"month","y":["billed_revenue"]}
}
```

Bar/line/area accept 1-4 numeric series; pie/scatter accept one. The chart contains only returned x/y values. Query errors, invalid chart specifications, empty results and truncated data never produce a fabricated chart. A chart validation error retains the ordinary query rows so the agent can correct the chart request or explain the issue. Charts appear in the assistant reply, can be inspected through View chart data, and are saved in the existing conversation response_json. Raw chart data is excluded from future model history to reduce token overhead. User-visible chat resume restores it after the normal admin authorization check.

Use invoice_summary for one-row-per-invoice totals and current local balances. It aggregates receipts and credits independently before calculating balances, avoiding duplicated values from joining two one-to-many tables. Balances are current ledger values, not historical settlement or bank cash flow. Use sales_lines for product-level billed quantities and merchandise revenue before order-level adjustments. These views exclude drafts/cancelled records. Currency snapshots are used where present; legacy records fall back to billing_config.currency.

Always group monetary queries by currency and return one currency per chart. The validator rejects mixed currencies when returned in the currency column; it cannot infer a currency omitted or incorrectly combined by a SQL expression. Query correctness and labeling remain necessary. Top-N charts show the requested subset and should say so in their title. Time labels preserve SQL row order, so trend queries must sort chronologically.
