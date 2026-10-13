# Version 6 verification

Verified locally on October 13, 2026 with temporary SQLite databases and Python 3.13.

Local tests use the real MCP transport and deterministic replay for model responses.

The full run completed with 99 passed and one failure in a new test helper: its name argument conflicted with the customer name field before the application was called. After renaming the helper argument, both interrupted-action tests passed in a targeted rerun (22.86 seconds). All 100 distinct tests have passing results. Production code was unchanged after the full run; the full suite was not repeated after that test-only correction.

Coverage includes:
- Missing/incorrect admin keys, disabled admin configuration and rejection of reusing the shared API key.
- Authorization on admin conversation creation, reading, chatting, cached responses and invoice downloads.
- Customer SQL row scoping, hidden procurement costs and resistance to CTE/main-table bypass attempts.
- MCP rejection of admin writes and cross-customer writes; workbench replacement of forged scope arguments.
- Mode-specific tool schemas, real MCP integration and conversation-context separation.
- Legacy conversation migration, marking prior transcripts admin-only without deleting messages.
- Existing order, draft, promo, refund, invoice, shopping comparison, alternative selection and API behavior.
- UI mode switching/login/logout, clearing prior messages, pending work, credentials and selected conversation.
- Structured attributes, directional product relations, current prices, bound SQL parameters and reporting views that avoid multiplying joined financial amounts.
- Query-backed bar, line, area, pie and scatter charts; validation of invalid columns, numbers, categories, currencies and truncated results.
- Multiple tool calls in one turn, the six-chart limit, clearing artifacts between turns and persistence on authorized conversation resume.
- Chart data excluded from future model history and Streamlit rendering of all five chart types.
- Preference persistence, correction/removal, budget scope defaults and reset without cancelling drafts.
- Ordered displayed product IDs, comparison/selection tracking and rejection of invented references or another customer's draft.
- Pending proposals checked against visible replies, invalidated by changed draft contents and cleared after successful actions or unrelated replies.
- API conversation resume after engine restart, preferences surviving the 40-message history limit, and isolation between conversations using the same warmed agent.
- Real MCP draft creation/placement with persisted shopping state, cached request behavior and automatic checkpointing if the final model reply fails.
- New-customer association retained after an interrupted turn, state/reply transaction rollback and preservation of existing transcripts during migration.
- Invalid preference patches and malformed internal JSON; admin conversations have no shopping state.

The customer UI, admin chart rendering, and login/logout tests passed in the full run. Third-party deprecation warnings remain.

Tests use deterministic replay for Azure model responses. Real Azure credentials, language quality and model latency were not tested. Transport reuse remains; scoped customer SQL copies public catalogue and selected-customer rows into an isolated in-memory snapshot for each query.

The included billing database is unchanged from archived version 5; its file hash is checked during version 6 finalization. It retains 400 customers, 400 products, 350 orders, 450 request lines, 400 fulfillment lines, 400 invoice lines, 240 price-history entries, 12 promotions and 4 configuration entries. The new shopping_states table is added to CONTEXT_DB at startup. Its migration was tested on a temporary conversation database containing existing messages, including repeated initialization.

New product attributes and relationships contain no invented specifications. Reporting views expose 400 catalogue rows, 300 invoices and 400 sales lines in the included data. Initialization also applies previously pending operational/catalogue tables to older databases.

There is no separate model call for memory extraction; preference patches accompany the normal final reply. Tests verify saved state and injected context using scripted model replies, not real Azure interpretation of arbitrary language. Confirmation still depends on the established conversation policy and existing tool checks; remembered proposals are not approval. See SHOPPING_MEMORY.md for malformed-output behavior and the small cross-database crash window. This remains a local assisted-store console; selecting a customer ID is not customer identity authentication.
