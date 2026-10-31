# Dependency security review — 2026-10-31

This review covers the dependency locks at main commit
`d3706262207111125576af4de2d4ff34ba209765` (SEGB 1.3.0) and the frontend
remediation prepared in PR #48.

## Findings

The frontend npm audit reported four moderate package findings caused by two
advisories in development dependencies:

- [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4):
  glob may continue filesystem traversal after cancellation; fixed in 14.0.2.
- [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249):
  minimatch pattern amplification may consume excessive CPU or memory; fixed in 11.0.1.

Both were reached through `@vue/test-utils` → `js-beautify` → `glob` and
`editorconfig` → `minimatch`. All affected packages were marked as development
dependencies; `npm audit --omit=dev` reported zero vulnerabilities. The frontend
Docker build installs development dependencies in its build stage; the final nginx
image copies the build output. No exploit or production assessment was performed.

GitHub reported no open Dependabot alerts at review time. Separate `pip-audit`
checks of the exported root and semantic log generator Python locks reported zero
known vulnerabilities for 62 and 7 packages respectively on the audit platform;
environment markers mean other platforms were not covered.

## Remediation

The frontend lock uses scoped overrides for glob 14.0.2 and minimatch 11.0.1.
`@vue/test-utils` remains pinned to 2.4.6: upgrading to 2.5.1 pulled `nopt` and
`abbrev` versions requiring Node 22 or newer, while the Docker builder uses Node 20.
The overrides cross dependency ranges declared upstream and should be revisited when
upstream adopts compatible patched versions.

## Verification

- `npm audit --package-lock-only --ignore-scripts`: zero vulnerabilities after remediation.
- `npm ci --ignore-scripts` followed by `npm run test:run`: 13 tests passed on Node 24.
- The frontend Dockerfile built successfully with Node 20, including type checking
  and the Vite production build, with host `node_modules` excluded from the context.
