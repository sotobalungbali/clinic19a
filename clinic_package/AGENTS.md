# Codex Boundary — clinic_package

Codex is not the architect for this addon.

Permitted:
- implement a defect with an explicit root cause and acceptance criteria;
- preserve all existing enterprise functions;
- update tests/evidence for that defect.

Forbidden:
- remove/simplify models, fields, methods, views, buttons, security, integrations, dependencies, or workflows to make tests pass;
- change model ownership;
- convert hard business controls into UI-only controls;
- introduce forward/circular dependency;
- retry indefinitely.

Retry limit: at most 2 bounded implementation attempts and at most 1 repetition of the same root cause. Then STOP and return to architecture/root-cause review.
