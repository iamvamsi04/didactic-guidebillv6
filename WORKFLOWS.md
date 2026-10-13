# Version 6: persistent shopping conversations

Start in this folder (version_6_latest). The assistant now saves needs, budget, features, product choices, current draft and pending proposals across customer turns and conversation resume. See SHOPPING_MEMORY.md for behavior and limits. The existing stack, chat layout, mode controls, warmed MCP process, pooled clients and cached schemas remain in use. Admin charts and composable tools are retained.

## Setup

1. Keep your local .env and database. For a fresh setup install requirements-lock.txt and copy .env.example to .env, then fill in Azure credentials.
2. Start the API with `python app.py`.
3. In another terminal run `python -m streamlit run ui/streamlit_app.py`.

Startup applies the additive schema automatically, including shopping_states in the conversation database. Existing billing records and transcripts are retained. No reseeding is needed. Version 5 is archived under outputs/previous_versions/version_5. No ZIP is needed.

The included billing database retains version 5's schema and records: 400 customers, 400 products and 350 orders. Product attribute and relationship tables start empty; add verified catalogue facts before asking questions that depend on specifications or compatibility. A database copied from an older installation receives the additive billing upgrade at startup. Version 6's new state table belongs to CONTEXT_DB.

## Flexible questions without extra tools

There are still twelve tools. execute_sql_query now accepts parameter bindings and optional chart metadata. It supports schema inspection, joined/filtered reads, aggregation and reusable reporting views. The agent can combine these reads with the existing comparison, order, promotion and invoice tools as appropriate. Financial changes retain their existing confirmations; Admin mode stays read-only.

For example, a shopper can ask for available products with a minimum capacity and a price limit, then compare shortlisted products and request an order draft. An admin can inspect a monthly trend, check anomalies and show a chart in the same turn. This uses the existing AutoGen tool loop, with a configurable MAX_TOOL_ITERATIONS upper bound of 12 by default (range 2-20). Simple answers stop sooner. No separate planning agent or extra model-routing call is introduced. This generalizes reads over available data; it cannot invent missing facts or implement an unsupported financial operation.

## Charts

In Admin mode ask, for example, "Show monthly billed revenue as a line chart in USD", "Plot the top 10 products by units billed", or "Show tax versus shipping by month as grouped bars". Available types are bar, line, area, pie and scatter. Charts include hover details and a View chart data expander, and survive conversation resume. They are snapshots of the saved query result, not live dashboards; ask again to refresh.

The renderer accepts only a fixed chart vocabulary backed by query results. It executes no generated code and loads no image URLs. Charts reject missing columns, invalid numbers, duplicate categories, truncated results and mixed returned currency values. The agent must include currency for monetary queries and query separate currencies. Up to six charts per turn and 200 data rows per chart are supported; pie charts allow at most twelve categories. See ANALYTICS.md for details and query examples.

## Admin setup and use

Add BILLING_ADMIN_API_KEY to your local .env. Use a unique random value of at least 16 characters, different from BILLING_API_KEY. Generate a value locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the generated value after `BILLING_ADMIN_API_KEY=` in .env, then restart the API. In the Streamlit sidebar select Admin, enter that value in the masked Admin key field, and click Unlock admin mode. Never paste this key into chat. Blank, too-short or shared-key-equal settings disable admin access.

Admin exposes execute_sql_query, billing_analysis, billing_anomalies and download_invoice. Ask for revenue, cost estimates, anomalies, customer/order records or an invoice PDF. This mode cannot edit catalogue data, customer details or financial records. Customer mode exposes the other shopping/billing tools plus scoped SQL and invoice downloads; analytics tools are admin-only. The application still registers twelve tools in total.

Changing modes or logging out clears the current visible messages, pending request and conversation selection. Saved chats have an immutable mode. Every API read/chat/invoice request against an admin conversation requires the admin key, including cached replies. Old conversations without a mode are migrated to admin-only access because they may contain broad store records; start a new customer conversation for shopping.

The admin key is checked by the API and never passed to the model. The private local MCP transport receives server-selected scope fields; model-supplied values are overwritten and omitted from model-visible schemas. Admin mutation calls are blocked by the tool server. Customer SQL runs against an isolated in-memory snapshot containing public catalogue columns (no baseprice) and only the selected customer's records.

## Exactly twelve tools

| Tool | Purpose |
| --- | --- |
| execute_sql_query | General read-only queries, schema inspection, parameter binding and requested admin charts. |
| request_order | Create an order draft with a full quote. |
| place_order | Place a confirmed draft, deduct stock and issue an invoice. |
| apply_promotion | Apply or replace a promotion on a draft. |
| download_invoice | Generate the customer's invoice PDF. |
| billing_analysis | Analyze invoice totals and estimated costs. |
| billing_anomalies | Check billing inconsistencies and suggest cost reviews. |
| manage_draft | Replace draft items or cancel the draft after confirmation. |
| manage_customer | Create or update customer information after confirmation. |
| process_refund | Record a full or partial ledger refund. |
| compare_products | Compare 2-5 products, price, stock, budget and recorded features. |
| find_cheaper_alternatives | Find cheaper available candidates with matching category/features. |

The other eight version-2 tools have been removed from the application and their Python implementations removed. Old database tables remain to preserve records and existing invoice/refund calculations. Both app.py and the compatible app_analytics.py launcher expose the same twelve tools.

## Customer flow

Browse without identifying a customer first. Ask about use, budget and quantity only when needed. Show a few actual options. Compare or find cheaper alternatives, then help the customer select. Obtain customer information when making the order, create a quote, apply requested promotions, confirm the final total, place the order and offer its invoice. Handle draft edits, invoice questions and refund requests using the same conversation history.

See CUSTOMER_CONVERSATIONS.md for examples and product data setup. Required features use exact recorded key/value matches, not a semantic or compatibility certification. Unknown features remain unknown. Product budgets cover merchandise before promotions, tax and shipping; a draft supplies the checkout total.

## Boundaries

This is a local assisted-store console. The admin key protects admin mode. Customer ID selection is still an operator assertion, not customer authentication: public deployment needs its own customer identity/access layer. Select the customer in the sidebar before starting personalized shopping; anonymous sessions can browse and create a new account. They cannot adopt an existing account through chat. Customer replies should not disclose other customers or internal costs/margins.

The application records orders, fulfillment quantities and ledger refunds. It does not charge cards, verify bank payments, transfer refunds, send email, track carriers or restock returns. It cannot create tickets, record payments, issue credit notes, edit due dates or send reminders. For unsupported requests it directs the customer to store staff without claiming the action was performed. Company refund eligibility and timelines must come from actual store policy.
