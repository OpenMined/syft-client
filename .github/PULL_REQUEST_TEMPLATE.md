## Summary

<!-- What does this PR do and why? One or two sentences. -->

## Changes

<!-- Key changes, bulleted. -->

-

## Testing

<!-- How did you verify this works? -->

- ***

### PR naming convention

All PR titles **must** follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type: description
type(scope): description
```

**Allowed types:**

| Type       | When to use                             |
| ---------- | --------------------------------------- |
| `feat`     | New feature or capability               |
| `fix`      | Bug fix                                 |
| `docs`     | Documentation only                      |
| `chore`    | Maintenance, deps, config               |
| `refactor` | Code restructuring (no behavior change) |
| `test`     | Adding or updating tests                |
| `ci`       | CI/CD workflow changes                  |
| `perf`     | Performance improvement                 |
| `build`    | Build system or dependency changes      |

**Examples:**

- `feat: add retry logic to job approval`
- `fix(syft-bg): handle timeout in notification sender`
- `docs: update syft-bg README`
- `chore: bump dependencies`

The `Validate PR title` check will block merging until the title matches this format.

### Auto-labeling

Labels are applied automatically based on:

- **PR title** — the type prefix maps to a label (e.g., `feat:` adds `feature`, `fix:` adds `bugfix`)
- **Changed files** — package labels like `pkg:syft-bg` or `pkg:syft-client` are added based on which directories the PR touches

These labels are used to auto-generate categorized release notes.
