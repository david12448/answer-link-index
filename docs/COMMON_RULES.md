# Common governance snapshot

Canonical source: `david12448/project-common-rules/COMMON_RULES.md` (pending PR #1).

1. Protect internal assets: keep raw source registries, collectors, parser rules, credentials and private mappings off public interfaces. Publish only required normalized results; use server-side access controls, pagination and reasonable rate limits. URL hiding alone is not security. Preserve attribution and lawful access.
2. Learn from verified failures: record symptoms, reproduction, root cause, fixes, verification and prevention in `docs/TROUBLESHOOTING.md`. Never invent past incidents.
3. Preserve existing functionality and files; propose changes through PRs, validate before merge. No automatic progress notifications.

This snapshot is NOT automatically synchronized yet. Central updates require separate tested PR automation.
