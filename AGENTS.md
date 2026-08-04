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
8. Watch the pull-request checks to completion.
9. Merge safe checkpoints with squash after every required check passes.
10. Update the governing GitHub issue with the commit, tests, PR, merge result and next checkpoint.

## Required merge commands

After pushing and opening the PR, first try GitHub native auto-merge:

```bash
gh pr merge --auto --squash --delete-branch
```

If repository auto-merge is disabled, do not stop at the PR. Watch the checks and merge the safe checkpoint directly after they pass:

```bash
gh pr checks --watch
gh pr merge --squash --delete-branch
```

A completed checkpoint is not delivered until it is pushed and either merged or explicitly marked review-required.

## Changes that may merge automatically after green checks

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
