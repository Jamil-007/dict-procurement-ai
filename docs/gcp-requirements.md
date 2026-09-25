# GCP Requirements — AI Analyst Persistent Storage

**For:** whoever holds admin on `ai-innov-474401`
**Requested by:** Mark Porazo (developer, no admin access)
**Project:** `ai-innov-474401`
**Region:** `asia-southeast1` (Singapore) — everything below must stay in this region to match the existing Cloud Run services

---

## 1. Why this is needed

The application currently keeps **everything in the container's memory and local disk**. Cloud Run wipes both on every redeploy and every scale-down, and staging runs at `min-instances 0`, so it recycles constantly.

In practice, today: a BAC officer creates a procurement, uploads a Terms of Reference, runs a review — and the record can be gone an hour later. There is no database and no file storage attached to this project.

The code to use Firestore and Cloud Storage is already written and merged behind environment variables. It is inert until the two resources below exist. Nothing needs to be rebuilt — only provisioned and configured.

---

## 2. What already exists (no action needed)

| Resource | Detail |
|---|---|
| Cloud Run — backend | `procurement-ai-backend-staging`, `procurement-ai-backend-prod` |
| Cloud Run — frontend | `procurement-ai-frontend-staging`, `procurement-ai-frontend-prod` |
| Artifact Registry | `asia-southeast1-docker.pkg.dev/ai-innov-474401/procurement-ai` |
| Vertex AI | Gemini, `gemini-2.5-flash`, already in use |
| Secret Manager | `TAVILY_API_KEY`, `GAMMA_API_KEY` |
| Workload Identity Federation | for GitHub Actions deploys |

---

## 3. What we need

### 3.1 Firestore — **required**

| Setting | Value |
|---|---|
| Mode | **Native mode** (not Datastore mode) |
| Location | `asia-southeast1` |
| Database ID | `(default)` |
| Delete protection | Recommended ON for production |

```bash
gcloud firestore databases create \
  --project=ai-innov-474401 \
  --location=asia-southeast1 \
  --type=firestore-native
```

> **Note:** a Firestore location is permanent — it cannot be changed after creation. Please confirm `asia-southeast1` before running this.

**One database serves both environments.** Staging writes are namespaced by a collection prefix (`staging_`), so the two never touch each other's records. If you would rather have hard separation, a second database named `staging` also works — tell us and we will point the staging service at it.

No composite indexes are needed. All queries are single-field equality filters, which Firestore indexes automatically.

### 3.2 Cloud Storage bucket — **required**

| Setting | Value |
|---|---|
| Name | `ai-innov-procurement-docs` (or your naming convention — just tell us the final name) |
| Location | `asia-southeast1`, Region (not multi-region) |
| Storage class | Standard |
| Access control | **Uniform bucket-level access** |
| Public access | **Prevented** — enforced |
| Object versioning | Recommended ON |
| Soft delete | Recommended, 30 days |
| Lifecycle rule | **None.** See retention note in §5. |

```bash
gcloud storage buckets create gs://ai-innov-procurement-docs \
  --project=ai-innov-474401 \
  --location=asia-southeast1 \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access \
  --public-access-prevention

gcloud storage buckets update gs://ai-innov-procurement-docs --versioning
```

One bucket is enough for both environments — staging objects can go under a `staging/` prefix. A second bucket is also fine if you prefer.

### 3.3 APIs to enable

```bash
gcloud services enable firestore.googleapis.com storage.googleapis.com \
  --project=ai-innov-474401
```

### 3.4 IAM

The Cloud Run services do **not** specify `--service-account`, so they run as the **default compute service account**:

```
<PROJECT_NUMBER>-compute@developer.gserviceaccount.com
```

Find the project number with `gcloud projects describe ai-innov-474401 --format='value(projectNumber)'`.

Grant it:

| Role | Scope | Why |
|---|---|---|
| `roles/datastore.user` | project | read/write procurement records and findings |
| `roles/storage.objectAdmin` | **bucket only**, not project | upload, read and delete procurement PDFs |

```bash
PROJECT_NUMBER=$(gcloud projects describe ai-innov-474401 --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding ai-innov-474401 \
  --member="serviceAccount:${SA}" --role="roles/datastore.user"

gcloud storage buckets add-iam-policy-binding gs://ai-innov-procurement-docs \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

If your policy forbids using the default compute service account, create a dedicated one (e.g. `procurement-ai-runtime@`) with the same two roles plus `roles/aiplatform.user` for Vertex AI, and we will add `--service-account` to the deploy workflows.

### 3.5 Environment variables on Cloud Run

Set by us in the GitHub Actions workflows once the resources exist — listed here so you know what to expect:

```
STORE_BACKEND=firestore
GCS_BUCKET=ai-innov-procurement-docs
FIRESTORE_PREFIX=staging_     # staging service only; empty on prod
```

---

## 4. What data we store, and where

### 4.1 Firestore — three collections

**`procurements`** — one document per procurement, keyed by reference number (`PROC-2026-001`):

> reference number · title · Approved Budget for the Contract · mode of procurement · fund source · category · end-user office · status (ongoing/finalized) · created and updated dates · attached-document metadata (filename, document type, page count, upload date, pointer to the PDF in the bucket) · review status · committee notes · who finalized it and when

**`findings`** — one document per AI Review finding, keyed `{reference}__{finding id}`:

> which review dimension raised it · severity · title · the analysis text · suggested action · source citation (document, page, section) · policy basis (RA 12009, IRR, GPPB/COA issuance) · quoted passage · cross-document comparison quotes · the committee's decision (accept/modify/request further review/reject) · who decided and when · any edits the committee made, with the original wording retained · comments · usefulness feedback

**`knowledge`** — ~15 seeded reference entries: laws, GPPB and COA issuances, DICT policies, standard forms. Public reference material, title and excerpt only.

Volume is small: a few kilobytes per document, well inside the Firestore free tier for the foreseeable future.

### 4.2 Cloud Storage — the uploaded PDFs

Path: `procurements/{reference}/{filename}` — for example
`gs://ai-innov-procurement-docs/procurements/PROC-2026-001/TOR.pdf`

These are the actual procurement documents the committee uploads: Terms of Reference, technical specifications, market studies, purchase requests, BAC resolutions, supplier quotations, bidding documents. Capped at 25 MB per file in the application.

### 4.3 Sensitivity — please read

These are **pre-award government procurement documents**. They contain approved budget figures, technical specifications and supplier quotations before the bidding process concludes. Premature disclosure has procurement-integrity implications, so:

- Public access prevention must be **enforced** on the bucket — no object should ever be publicly readable.
- Data stays in `asia-southeast1`.
- Access limited to the service account and named administrators.

No personal data beyond the names of DICT officers recorded against their decisions. There is no authentication in this version — every action is attributed to a single "BAC Admin" identity — so **this should not hold live procurement data until proper sign-in is added.** Test and pilot data only for now.

### 4.4 Retention

Procurement records are government records subject to COA retention rules. We have deliberately **not** set any lifecycle deletion rule — please advise what retention period applies so we can configure it correctly, or confirm that records should be kept indefinitely.

---

## 5. Not needed

To save you asking: no Cloud SQL, no AlloyDB, no BigQuery, no Memorystore, no Pub/Sub, no VPC connector, no load balancer, no CDN. Just the Firestore database and the one bucket.

---

## 6. Rough cost

At pilot volume — tens of procurements, a few hundred documents — this sits within or just above the always-free tier. Expect **under USD 5/month**, dominated by a few gigabytes of standard storage. It does not meaningfully change the project's spend; Vertex AI inference remains the larger cost.

---

## 7. What we need back from you

1. Confirmation that Firestore was created in `asia-southeast1` in **Native mode**
2. The **final bucket name**, if different from `ai-innov-procurement-docs`
3. Confirmation the runtime service account has both roles — and its **email address**, if it is not the default compute account
4. The applicable **retention period** for procurement records
5. Whether you want staging on a **collection prefix** (our default) or a separate database and bucket

Once we have 1–3 we can enable it on staging the same day.
