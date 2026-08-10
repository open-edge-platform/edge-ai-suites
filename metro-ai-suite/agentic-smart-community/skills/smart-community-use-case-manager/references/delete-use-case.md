# Deleting a Use Case

Read this on any delete/remove/drop request for a use case. The mandatory
cross-turn confirmation gate is defined in `SKILL.md`; this file holds the
operational detail.

## Display the real impact first

Fetch the real impact with `smart_community_use_case_register action=list` and
`smart_community_monitor_ctl action=list`, then display what deletion will do:

- remove `<use_case>` from the in-memory `use_case_dict` and the booted
  config (`persist: true`);
- move its artifacts to `<data_dir>/use-cases/.backup/<use_case>/`
  (recoverable);
- stop and unregister every monitor bound to it (list them by ID).

Ask the user to explicitly confirm the deletion, for example
`confirm delete <use_case>`, and end the turn without calling
`action=unregister`.

## Confirmation rules

- The initial delete request itself is never confirmation — even when it says
  "delete", "remove", or "drop" — because the user has not yet seen the
  cascade impact.
- Silence, a recommendation, or the agent's own summary is never confirmation.
- If the reply is ambiguous, ask again and end the turn; if the user declines,
  do not delete.

## Verify `cascaded_monitors` after unregister

- `db_row="deleted"` — the monitor was fully unregistered.
- `db_row="kept_offline"` — the row delete failed (e.g. existing alerts
  history) and it fell back to stop. Tell the user the monitor row remains
  offline, and that its monitors.yaml entry was kept with `enabled: false`
  (flip back to `true` to re-enable).
