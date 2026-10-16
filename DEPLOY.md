# Deploying to Render

Everything Render needs is described in [render.yaml](render.yaml) (a Render
"Blueprint"). One Blueprint creates four resources, all in one region:

| Resource | Name | What it runs |
|---|---|---|
| Web Service | `stockprices-web` | gunicorn: the public site, the API, `/admin/` |
| Background Worker | `stockprices-worker` | Celery worker with beat embedded: the scheduled syncs |
| Key Value | `stockprices-redis` | Redis: cache, Celery broker, sync locks |
| Postgres | `stockprices-db` | the database |

Database and Redis credentials are wired in automatically (`DATABASE_URL`,
`REDIS_URL`). You only type in the Massive API key and your domain.

None of these run on Render's free tier: background workers and pre-deploy
commands are paid-only, and a free web service sleeps when idle, which hurts
an SEO site. The Blueprint uses the smallest paid size of each; check the
current prices on the Blueprint preview screen before you confirm.

---

## 1. Before you start

1. Push this repo to GitHub, including `render.yaml`. Render deploys from the
   `master` branch (set in `render.yaml`).
2. Have ready:
   - your Massive API key (https://massive.com/dashboard)
   - the domain the site will live on, e.g. `www.example.com`. No domain yet?
     Use the Render URL for now (step 3 explains).
3. **Pick the region.** `render.yaml` uses `oregon` for all four resources. To
   change it, edit every `region:` line before step 2. It cannot be changed
   after the database is created. Options: `oregon`, `ohio`, `virginia`,
   `frankfurt`, `singapore`.

## 2. Create the Blueprint

1. Sign in at https://dashboard.render.com and connect your GitHub account.
2. **New +** → **Blueprint** → choose the `stockprice` repo.
3. Render reads `render.yaml` and lists the four resources and the
   `stockprices-shared` environment group. Review the instance sizes here.
4. Fill in the values it asks for:

| Variable | Service | Value |
|---|---|---|
| `MASSIVE_API_KEY` | web and worker | your Massive key (same on both) |
| `SITE_URL` | web and worker | `https://www.example.com`, no trailing slash (same on both) |
| `ALLOWED_HOSTS` | web | `www.example.com,example.com` |
| `CSRF_TRUSTED_ORIGINS` | web | `https://www.example.com,https://example.com` |

5. Click **Apply**. Render creates Postgres and Key Value, builds both
   services, runs `migrate` and `apply_sql` (the pre-deploy command, which
   builds the schema), then starts the site.

**No domain yet?** Use the `onrender.com` URL. Render shows it on the web
service's page, e.g. `https://stockprices-web.onrender.com`. Set `SITE_URL` to
that URL. Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to the same host, or
leave them blank: the app always allows its own `onrender.com` host. Change
all three when the domain is attached (step 5).

## 3. Check the first deploy

- Web service **Logs**: the pre-deploy step should list the `sql/` files it
  applied, and gunicorn should report it is listening.
- `https://<your-host>/api/health/` should return `"status": "ok"`. Render
  uses this URL as the health check, so a failing database or Redis stops the
  deploy.
- Worker **Logs** should show `celery@... ready` and `beat: Starting...`.

## 4. First-time setup (Render Shell)

Open **stockprices-web → Shell** and run:

```bash
python manage.py createsuperuser
```

The database starts empty. Hand the first syncs to the worker, so they keep
running if the Shell disconnects:

```bash
python manage.py shell -c "from sync.tasks import sync_exchanges_task, sync_reference_data_task; sync_exchanges_task.delay(); sync_reference_data_task.delay()"
```

That loads the exchange list, then tickers, then company profiles, then
sectors. Watch progress in the worker's **Logs**. On the free Massive tier
(5 calls a minute) company profiles take a long time; the daily 01:15 UTC run
keeps working through them.

When the ticker list has loaded, backfill recent prices (this runs in the
Shell itself):

```bash
python manage.py sync_daily_prices --days 5
```

After that the beat schedule in `app/config/celery.py` keeps everything
current (UTC times):

| Job | When |
|---|---|
| exchanges | 1st of the month, 01:00 |
| tickers, profiles, sectors | daily, 01:15 |
| daily prices | Tue–Sat, 01:45 |

## 5. Attach your domain

1. **stockprices-web → Settings → Custom Domains** → add `www.example.com`
   (and `example.com` if you want the apex to redirect).
2. Add the DNS records Render shows at your DNS provider and wait for the
   certificate to be issued. Render redirects HTTP to HTTPS itself.
3. If you deployed on the `onrender.com` URL, update `SITE_URL` (web **and**
   worker), `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. Saving restarts the
   services.
4. Clear cached pages so they pick up the new canonical URLs:
   `python manage.py clear_api_cache` in the Shell.
5. From your own machine, check the site the way a crawler sees it:
   `make verify URL=https://www.example.com`.

## 6. Optional settings

Add these under **Environment Groups → stockprices-shared** (shared by web and
worker), then save:

| Variable | Purpose |
|---|---|
| `INDEXNOW_KEY` | 8–128 chars of `[a-zA-Z0-9-]`. Turns on IndexNow pings to Bing and others after each profile sync. |
| `SITE_TWITTER` | `@handle` for Twitter cards |
| `ORGANIZATION_SAME_AS` | comma-separated profile URLs for structured data |

## Day-to-day

- **Deploy:** push to `master`. Both services rebuild. The web service runs
  `migrate` and `apply_sql` before the new code goes live. `RELEASE` comes
  from the commit SHA automatically, so cached pages from the old code are
  never served.
- **Schema change:** add a new `.sql` file under `sql/` (see
  [SCHEMA_PLAN.md](SCHEMA_PLAN.md)) and push. The pre-deploy step applies it.
  A failing `.sql` file stops the deploy, and the old version keeps serving.
- **Changed an API response?** Run `python manage.py clear_api_cache` in the
  Shell after the deploy.
- **Run a sync by hand:** any of the commands in the README, from the Shell.
- **Logs:** each service's **Logs** tab. Files written under `logs/` are lost
  on every deploy; use the Logs tab.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `400 Bad Request` on every page | The host isn't in `ALLOWED_HOSTS`. |
| `403 CSRF verification failed` on the admin login | `CSRF_TRUSTED_ORIGINS` is missing `https://` + the domain you used. |
| Deploy stuck on the health check | `/api/health/` returns 503: check `DATABASE_URL` / `REDIS_URL` and that all four resources are in the same region. |
| Scheduled syncs never run | Worker not running, or `PROJECT_NAME` differs between web and worker (it names the Celery queue). |
| Jobs run twice | The worker was scaled past 1 instance. Beat runs inside it, so keep it at 1. |
| Canonical URLs or sitemap show the wrong host | `SITE_URL` is wrong on web or worker. Fix it, then run `clear_api_cache`. |
