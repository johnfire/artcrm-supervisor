# Deployment secrets — build-context .dockerignore (H-2)

The supervisor image is built with the **parent directory as the build context**
(`docker-compose.yml` → `build.context: ..`). Docker only honours the `.dockerignore`
at the **build-context root**, which is `/home/chris/ppp2/artcrm/` — *not*
`artcrm-supervisor/.dockerignore`.

Without a root `.dockerignore`, `Dockerfile`'s `COPY artcrm-supervisor/ ...` bakes the
live `.env` (all API keys, SMTP password, Open Brain + BrightData tokens) and every
sibling repo's `.git` history into the image layers — readable by anyone who can pull
the image or read a backup.

That root file lives outside every component git repo, so it cannot be version-controlled
here. **Canonical content** (recreate at `/home/chris/ppp2/artcrm/.dockerignore` if lost):

```
# Secrets — never bake these into an image layer.
**/.env
**/.env.*
!**/.env.example

# Per-component git repos (each sibling dir is its own repo; history may hold secrets).
**/.git
.git

# Python / virtualenv / build artifacts
**/.venv
**/__pycache__
**/*.pyc
**/*.pyo
**/*.egg-info
**/.pytest_cache
**/dist
**/build

# Node / mobile
**/node_modules

# Local-only working dirs and bulky data not needed in the image
**/.worktrees
**/.superpowers
**/backups
**/*.xlsx
```

## After (re)creating it

1. Rebuild the image: `docker compose build --no-cache app`.
2. Confirm no secrets in the image:
   `docker run --rm --entrypoint sh artcrm-app -c 'find / -name ".env" 2>/dev/null'`
   (should print nothing under the app dirs).
3. Rotate any credential that may already have been baked into a previously-built image
   (see the operational rotation checklist).
