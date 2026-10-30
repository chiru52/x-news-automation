# Cloudflare build migration — preview only

The live `signaldesk-news` Pages project was historically published through a
GitHub Actions Wrangler direct upload. Linking GitHub with an empty build command
does not reproduce that export process.

This branch provides a **preview-only**, fail-closed build script.

## Safe local or disposable preview usage

Requirements: Python 3.12, Bash, network access for RSS candidates.

```sh
SIGNALDESK_PREVIEW_BUILD=true bash scripts/build_cloudflare_preview.sh
```

Expected output directory: `dist/signaldesk`.

The script validates the public schema, verifies Topic Writer is present, wires
the same approved live RSS endpoint and fails if no news was collected. It reads
**no private GitHub issues** and therefore displays **no historical private
editorial drafts**. It does not call Cloudflare, connect to X, or send posts.

**Do not put this command into the existing production Cloudflare Pages project
yet**. Its build intentionally omits private editorial drafts; switching the
production build without a migration plan would regress the existing site.

Before a production cutover: independently verify the production feed, decide how
to migrate or intentionally omit private editorial drafts, confirm the correct
build environment and output directory in a disposable Pages project, and obtain
explicit approval before enabling any production deployments.
