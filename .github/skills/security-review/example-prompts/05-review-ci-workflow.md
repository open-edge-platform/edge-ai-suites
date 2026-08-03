# Review a GitHub Actions workflow for supply-chain risk

Review this CI workflow change for development-time security. Check that actions
are pinned to full commit SHAs (not tags), `persist-credentials` is disabled
unless required, token permissions are least-privilege, and no secrets are
echoed. Report findings with severity and confidence and give the exact fix for
each line.

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: true
- run: echo "${{ secrets.NPM_TOKEN }}"
permissions: write-all
```
