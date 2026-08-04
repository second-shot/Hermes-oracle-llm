# Hermes Agent Execution Contract

This repository must move forward through small, verified checkpoints. Do not stop after planning or testing when the requested checkpoint is complete.

## Required delivery loop

For every implementation checkpoint:

1. Inspect the current branch, working tree, issue and relevant tests.
2. Preserve unrelated user changes. Never use `git add -A` in a mixed worktree.
3. Implement the smallest complete checkpoint on the existing feature branch.
4. Run focused tests, then the relevant regression suite.
5. Commit only the checkpoint files with a clear message.
6. Push the branch immediately.
7. Create or update one pull request; do not create overlapping PRs for the same goal.
8. Enable GitHub native auto-merge with squash after checks pass for safe changes.
9. Continue to the next checkpoint only after the branch is pushed and the PR state is recorded.
10. Update the governing GitHub issue with the commit, tests, PR and next checkpoint.

## Native auto-merge command

After pushing and opening the PR:

```bash
gh pr merge --auto --squash --delete-branch
```

Use native auto-merge rather than a custom workflow that merges unverified code.

## Changes that may auto-merge after green checks

- local application logic;
- tests and fixtures;
- documentation;
- reversible local-only features;
- skill candidates that remain DRAFT, TESTED or SHADOW;
- refactors with unchanged permissions and external authority.

## Changes that require explicit review before merge

- `.github/workflows/**`;
- `policies/**` and security boundaries;
- provider, token, credit or credential handling;
- deployment, infrastructure and migrations;
- filesystem or network permission expansion;
- external posting, messaging, buying, selling or dispatch;
- destructive or privileged actions;
- automatic activation of external or privileged skills.

For review-required changes, still commit, push and open the PR automatically, but do not bypass the review boundary.

## Non-negotiable quality rules

- Never claim success without test evidence.
- Never merge a failing checkpoint.
- Never modify `main` directly.
- Never silently discard user work.
- Never create duplicate branches or modules when an active implementation already exists.
- Keep runtime state outside source control.
- Every active skill needs a manifest, tests, evaluation evidence and rollback target.
- If a regression appears after promotion, quarantine and roll back before further development.
