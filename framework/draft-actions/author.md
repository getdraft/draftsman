# /draft author

**Purpose**: Create or update architecture content using the Draftsman.

**Instructions**:
1. Read the current workspace state via `.draft/workspace.yaml` and `.draft/framework.lock`.
2. Use the Draftsman role defined in `framework/docs/draftsman.md`.
3. Follow the standard authoring workflow for the requested intent.
4. Validate changes with `python3 framework/tools/validate.py` before committing.

Always prefer structural satisfaction over DecisionRecords unless documenting non-conformance.