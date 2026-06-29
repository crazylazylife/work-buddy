# Work Buddy Agent Skills

These repo-native skills document the specialist capabilities used by the ADK sub-agents. They are intentionally small and composable so they can be copied into Antigravity/Codex-style skill systems or converted into provider-specific skill packages later.

Each skill defines:

- purpose
- when to use it
- expected inputs
- required tool calls
- safety/failure behavior

The ADK implementation wires these capabilities through specialist sub-agents in `app/sub_agents.py`.
