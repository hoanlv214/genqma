# NPM Release Checklist & Publication Flow

This document defines the process for publishing `@qma/agents` to the public npm registry.

## 1. Tooling Integration: Changesets
Instead of manually editing `package.json` version numbers, we use [Changesets](https://github.com/changesets/changesets).

**Setup:**
1. Run `npx @changesets/cli init` in the repository root.
2. When making a PR that affects the SDK, developers run `npx changeset`.
3. They follow the prompt to select `@qma/agents` and specify if the change is `patch`, `minor`, or `major` (Semantic Versioning).
4. This creates a markdown file in `.changeset/` which is committed with the PR.

## 2. Semantic Versioning Policy
- **MAJOR (`1.0.0`)**: Incompatible API changes (e.g., removing exports, changing `QmaAgent.run` signature, renaming `SessionPolicy` keys).
- **MINOR (`0.1.0`)**: Adding functionality in a backwards-compatible manner (e.g., adding a new Wallet Adapter, adding a new event type).
- **PATCH (`0.0.1`)**: Backwards-compatible bug fixes (e.g., fixing a crash in `loop.ts`, typo in error messages).

## 3. GitHub Actions Release Workflow
We automate the release process using GitHub Actions.

**Workflow File:** `.github/workflows/release.yml`

```yaml
name: Release
on:
  push:
    branches:
      - main
jobs:
  release:
    name: Release
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          registry-url: 'https://registry.npmjs.org'
      - run: npm ci
      - run: npm run build --workspace=@qma/agents
      - name: Create Release Pull Request or Publish to npm
        uses: changesets/action@v1
        with:
          publish: npm run publish-packages
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

**How it works:**
1. When code is merged to `main`, the action runs.
2. If there are unreleased changesets, it creates a "Version Packages" PR.
3. When the team merges the "Version Packages" PR, the action runs again.
4. This time, it deletes the changesets, tags the commit, creates a GitHub Release, and runs `npm publish`.

## 4. Manual Publish Flow (Fallback)
If CI fails, a maintainer can publish locally:
1. `npm ci`
2. `npm run build`
3. Verify `dist/` contains `.js` and `.d.ts` files.
4. `npx changeset version` (Updates package.json and CHANGELOG.md)
5. `npm install` (Updates package-lock.json)
6. `git commit -am "chore: release"`
7. `npx changeset publish` (Uploads to npm)
8. `git push --follow-tags`

## 5. Pre-Flight Checklist
Before cutting the `v1.0.0` or public `v0.1.0` release, verify:
- [ ] `@qma/agents` is available on npm (if first time, create organization).
- [ ] `.npmignore` is configured (exclude `src/`, include `dist/`).
- [ ] `package.json` has `"private": false` or removed completely.
- [ ] `README.md` is accurate and links to GitHub.
- [ ] `LICENSE` is present (MIT/Apache).
- [ ] `npm pack` dry-run shows only necessary files in the tarball.
