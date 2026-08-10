# CP-05 integration note: Superset gate-time refresh

`SupersetGateVerifier` is a read-only evidence producer. CP-05 should invoke it
inside `ProducerGateWorkflow._verify_ready_state`, after the fresh DataHub
inventory establishes current consumer membership and before the merged
evidence envelope is accepted. The verifier must receive the campaign-owned
Superset gate binding plus runtime-only `SupersetSettings` configured with
`allow_apply=False`; it must not receive an operator-selected native object.

The smallest integration hunk is conceptually:

```python
gate_now = parse_timestamp(trusted_now)
superset_observation = SupersetGateVerifier(
    settings=read_only_superset_settings,
    client=SupersetClient(read_only_superset_settings),
    clock=lambda: gate_now,
).verify(
    superset_gate_binding,
    trusted_now=gate_now,
    artifact_root=gate_verification_root / "superset",
)
current_envelope = merge_source_reconciliation_evidence(
    current_envelope,
    superset_observation["evidence_source"],
    baseline_source=baseline_superset,
)
```

CP-05 must then apply the existing deterministic scope, freshness, completeness,
and membership checks to the merged envelope. It must additionally bind the
current DataHub consumer entry to both the exact Superset dataset identity in
the accepted receipt and the same identity in `superset_observation`. A verifier
success is evidence, not a readiness decision; any `Refusal` propagates and no
producer action is attempted.

The DataHub and native observations remain complementary. Current DataHub
inventory proves graph membership and cross-system identity. Native Superset
SQL and forced chart execution prove the exact field mapping and semantic
state. The official connector's table-level lineage cannot replace the native
field fact, and a native match cannot replace the fresh graph inventory.

Inputs CP-05 must persist or resolve without secrets:

- the digest-verified accepted Superset plan, apply record, validation, and
  receipt used by `capture_superset_gate_binding`;
- the accepted DataHub URN and exact dataset, chart, and database IDs and UUIDs;
- the baseline Superset evidence-source scope from the reconciled envelope;
- a read-only principal's runtime credentials and trusted gate clock.

No change to `gate.py`, a shared schema, CLI, or MCP belongs in CP-02.
