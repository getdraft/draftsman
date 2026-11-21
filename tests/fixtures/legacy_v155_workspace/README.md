# Legacy v1.5.5-style workspace (#368 compatibility fixture)

Relationships authored before the listener model: `flow: bidirectional`, `flow: inbound` and free-text
`externalTarget`, and no `targetListener`. There is deliberately no `.draft/validation-baseline.yaml`:
`tests/test_legacy_relationship_compat.py` copies this workspace, runs `validate.py --write-baseline` as a framework
refresh would, and checks that the result is clean and that editing one relationship flags only that one.
