# Version 6 changes from version 5

Persistent shopping state across customer turns, history truncation and conversation resume. Tool results maintain draft/product facts; the same model response supplies validated preference updates. Twelve tools remain registered.

## Modified

- [CHANGED_FILES.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/CHANGED_FILES.md)
- [CUSTOMER_CONVERSATIONS.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/CUSTOMER_CONVERSATIONS.md)
- [TESTING.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/TESTING.md)
- [WORKFLOWS.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/WORKFLOWS.md)
- [agent/billing_agent.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/agent/billing_agent.py)
- [api/main.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/api/main.py)
- [context/context_manager.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/context/context_manager.py)
- [tests/test_admin.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/tests/test_admin.py)
- [tests/test_api.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/tests/test_api.py)

## Added

- [SHOPPING_MEMORY.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/SHOPPING_MEMORY.md)
- [agent/shopping_policy.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/agent/shopping_policy.py)
- [context/shopping_state.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/context/shopping_state.py)
- [tests/test_shopping_state.py](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/outputs/version_6_latest/tests/test_shopping_state.py)

## Removed

None.

The billing database and existing data/configuration files are unchanged from archived version 5. Startup adds shopping_states to the conversation database; old messages are retained. There are no new dependencies, tools, UI panels or additional model calls for memory extraction.

Workspace [AGENTS.md](C:/Users/vamsi/Documents/Codex/2026-10-05/bu/AGENTS.md) now identifies version_6_latest. No source ZIP or duplicate project copy was placed in the latest folder. See TESTING.md for validation details.
