# GitHub Actions: build, test, deploy to Cloud Run

## Table of contents
- [CI workflow](#ci-workflow-githubworkflowsciyml)
- [Deploy workflow](#deploy-workflow-githubworkflowsdeployyml)
- [Workload Identity Federation: one-time setup](#workload-identity-federation-one-time-setup)
- [What *not* to do](#what-not-to-do)

Two workflows cover everything:

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | PR + push | Lint, build the `test` target, run pytest in-container |
| `.github/workflows/deploy.yml` | Push to default branch | Build the `prod` target, push to a registry, deploy to Cloud Run (example) |

Both use **BuildKit cache via the GHA backend** (`type=gha`). Deploy uses
**Workload Identity Federation** — no JSON service-account keys in GitHub Secrets.
The deploy half is Cloud-Run-specific; swap it for your platform's deploy action
while keeping the build half intact.

## CI workflow: `.github/workflows/ci.yml`

Drop-in template at `assets/github/ci.yml`. Annotated highlights:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  api-test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3

      # Build the `test` stage and load it into the local docker daemon.
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: infra/api.Dockerfile
          target: test
          load: true                    # bring image into local docker for next step
          tags: api:test
          cache-from: type=gha,scope=api-test
          cache-to: type=gha,mode=max,scope=api-test

      # The image's CMD is `uv run pytest -v`.
      - name: Run pytest
        run: docker run --rm api:test
```

**Notes:**

- Distinct cache `scope`s (`api-test`, `web`) keep caches from clobbering each other.
- `load: true` puts the image into the local docker daemon so the next step can `docker run` it. Without `load`, buildx writes to cache only.
- `mode=max` exports cache for **every** layer (including intermediates). Without it, only the final layer caches and rebuilds redo most of the work.
- `permissions: contents: read` is the minimum for `actions/checkout`. We don't grant `packages: write` because we push to a cloud registry, not GHCR.

### Why test inside the image, not on the runner

1. **Environment parity.** Testing in the same image lineage as prod catches "passes on the runner, fails in container" bugs.
2. **One source of truth for the lockfile.** Running `uv sync` on the runner could re-resolve dependencies; running in the test image guarantees the same wheels every time.

## Deploy workflow: `.github/workflows/deploy.yml`

Drop-in template at `assets/github/deploy.yml`.

```yaml
name: Deploy api to Cloud Run

on:
  push:
    branches: [main]
    paths:
      - "apps/api/**"
      - "infra/api.Dockerfile"
      - ".github/workflows/deploy.yml"

env:
  PROJECT_ID:    ${{ vars.GCP_PROJECT_ID }}
  REGION:        ${{ vars.GCP_REGION }}              # e.g. asia-east1
  AR_REPO:       ${{ vars.ARTIFACT_REGISTRY_REPO }}  # e.g. your-repo
  CLOUD_RUN_SVC: api
  SQL_INSTANCE:  ${{ vars.CLOUD_SQL_INSTANCE }}      # e.g. your-prod-db

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write          # required for Workload Identity Federation
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

      - uses: google-github-actions/setup-gcloud@v2

      - name: Configure docker auth for Artifact Registry
        run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet

      - uses: docker/setup-buildx-action@v3

      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.AR_REPO }}/api
          tags: |
            type=sha,format=long
            type=raw,value=latest,enable={{is_default_branch}}

      - uses: docker/build-push-action@v6
        with:
          context: .
          file: infra/api.Dockerfile
          target: prod
          platforms: linux/amd64    # Cloud Run runs amd64; explicit is safer
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha,scope=api-prod
          cache-to: type=gha,mode=max,scope=api-prod

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.CLOUD_RUN_SVC }} \
            --image ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.AR_REPO }}/api:${{ github.sha }} \
            --region ${{ env.REGION }} \
            --platform managed \
            --allow-unauthenticated \
            --add-cloudsql-instances ${{ env.PROJECT_ID }}:${{ env.REGION }}:${{ env.SQL_INSTANCE }} \
            --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest \
            --set-env-vars "DATABASE_URL=postgres:///postgres?host=/cloudsql/${{ env.PROJECT_ID }}:${{ env.REGION }}:${{ env.SQL_INSTANCE }}" \
            --cpu 1 --memory 512Mi \
            --min-instances 0 --max-instances 10 \
            --timeout 300 \
            --port 8000 \
            --quiet
```

**Notes:**

- `paths:` filter — fires only when api code, the Dockerfile, or the workflow changes. Saves CI minutes.
- `vars.*` for non-secrets (project ID, region, repo name); `secrets.*` for sensitive bindings (WIF provider, service-account email).
- `id-token: write` is **mandatory** for WIF — `google-github-actions/auth` exchanges the GitHub OIDC token for short-lived GCP credentials.
- `metadata-action` produces a long-SHA tag plus `latest`. Long SHA tags make rollbacks trivial.
- `platforms: linux/amd64` — explicit prevents "works on my arm64 mac, fails on the platform" surprises.
- `--port 8000` is informational — the platform still injects `PORT`.

## Workload Identity Federation: one-time setup

WIF replaces the legacy "create a service account, download a JSON key, paste into a secret" pattern. Setup is per-project, not per-repo.

```bash
# Variables
PROJECT_ID="your-project-id"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
POOL=github-pool
PROVIDER=github-provider
SA_NAME=cloud-run-deployer
GH_OWNER="your-org"     # your GitHub org or user
GH_REPO="your-repo"

# 1. Create the WIF pool and provider
gcloud iam workload-identity-pools create "$POOL" \
  --location=global --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner=='${GH_OWNER}'"

# 2. Service account that GHA will impersonate
gcloud iam service-accounts create "$SA_NAME" --display-name="Cloud Run deployer (GHA)"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 3. Grant deploy + push roles to the service account
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/iam.serviceAccountUser"

# 4. Allow the GitHub repo to impersonate this SA
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GH_OWNER}/${GH_REPO}"

# 5. The two GH secrets you set on the repo
echo "WIF_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "WIF_SERVICE_ACCOUNT=${SA_EMAIL}"
```

The **runtime** service account (the one Cloud Run actually runs as) is separate from the deployer SA. It needs `roles/cloudsql.client` and `roles/secretmanager.secretAccessor`. Keep them separate so a compromised deploy SA can't read prod secrets.

## What *not* to do

- Don't `actions/setup-python` + `uv sync` on the runner. You get a different environment than what ships, defeating containerization.
- Don't use `cache-to: type=registry` for a small-team repo. The GHA cache backend is faster and free up to 10GB.
- Don't store JSON service-account keys in GitHub Secrets. They're long-lived and leak via logs/forks. WIF tokens last ~1 hour and are scoped to the run.
- Don't push `:latest` only — without an immutable tag (sha or version), you can't roll back deterministically.
- Don't grant `roles/owner` to the deploy SA. `run.admin + artifactregistry.writer + iam.serviceAccountUser` is the minimum.
