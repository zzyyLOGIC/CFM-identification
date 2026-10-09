## Assigned task

- Task ID:
- Setting / branch:

## What changed?

Briefly describe the implementation and the main files changed.

## Identification argument

### Target

What causal target does this task identify?

### Assumptions

Which assumptions are required, and where do they come from?

### Support

How is query-specific population support computed or verified?

### Identification conclusion

Why is the supported target POINT identified under the stated assumptions?
If this PR is not a POINT task, explain the intended status explicitly.

## Validation

- [ ] Normal case
- [ ] Small-N brute-force / exact oracle when applicable
- [ ] Boundary case
- [ ] Zero-support or invalid-input case
- [ ] `test_identification_integration.py` passes
- [ ] `test_pipeline_smoke.py` passes if shared contracts / handoff changed
- [ ] Notebook/demo runs if this PR changes a demo

Commands/results:

```text
paste the relevant test commands and short results here
```

## Files changed

List the main files and why each one changed.

## Scope check

- [ ] I did not modify Estimation / Policy implementation unless the assigned task explicitly required an interface compatibility fix.
- [ ] I did not commit checkpoints, outputs, caches, or notebook checkpoint files.
- [ ] If I changed `pfn_pipeline/contracts.py`, I explain the compatibility impact below.

Shared-contract impact (if any):

## Reusability

Which part of this PR should become shared Identification functionality rather than remain a task-specific implementation?
Which other settings could reuse it?

## Known limitations

What does this PR intentionally not solve?
