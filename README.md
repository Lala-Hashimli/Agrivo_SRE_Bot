# Agrivo SRE Assistant

A read-only Telegram SRE bot for Agrivo. It supports mock demonstrations and real
Agrivo, Prometheus, Alertmanager, Grafana, Kubernetes, GitHub Actions and Argo CD
data. Missing signals are reported as unavailable instead of being shown as healthy.
All displayed dates use Azerbaijan time (`Asia/Baku`).

## Commands

- Health: `/status`, `/health`, `/doctor`, `/metrics`, `/chart [hours]`, `/alerts`
- Kubernetes: `/pods`, `/deployments`, `/hpa`, `/images`
- Delivery: `/workflows`, `/argocd`, `/last_deploy`
- Dashboards: `/grafana` (links and optional rendered overview image)
- Analysis: `/incident`, `/daily_report`, `/ask <question>`
- Preferences: `/language az`, `/language en`

No command restarts pods, syncs Argo CD, rolls back, deploys, or changes infrastructure.

## First local run

Use Python 3.12+ and start the Agrivo frontend/backend first. Then:

```powershell
cd C:\Users\lalah\Downloads\Agrivo\sre-bot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

In `.env`, set a newly rotated Telegram token and switch to real data:

```env
BOT_DATA_MODE=real
TELEGRAM_BOT_TOKEN=replace-with-new-token
DISPLAY_TIMEZONE=Asia/Baku
```

Never commit `.env`. Restrict access using your numeric Telegram ID:

```env
TELEGRAM_ALLOWED_USER_IDS=123456789
```

Start the bot:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8085
```

Check `http://localhost:8085/health/ready`, then send `/status` to the bot.
Only one bot process may poll the same Telegram token.

## Connecting to AKS services from the local bot

`localhost:9090`, `9093`, `3000`, and `8080` work only while these port-forwards
are running. Open four PowerShell terminals:

```powershell
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

For the Argo CD forward use:

```env
ARGOCD_URL=https://localhost:8080
ARGOCD_VERIFY_TLS=false
```

The bot invokes your configured read-only `kubectl` context. For the current dev
cluster use `KUBERNETES_CONTEXT=aks-agrivo-dev` and
`KUBERNETES_NAMESPACE_DEV=agrivo-dev`. Production returns no resources until the
`agrivo-prod` namespace actually contains workloads.

## Optional local monitoring stack

If you do not want AKS port-forwards, this package starts local Prometheus,
Alertmanager, and Grafana. Prometheus scrapes the backend at
`host.docker.internal:5001/api/metrics`.

```powershell
docker compose -f docker-compose.monitoring.yml up -d
```

- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Grafana: `http://localhost:3000` (`admin` / `agrivo-local-change-me`)

Change the local Grafana password immediately if the stack is exposed beyond your
machine. The provisioned dashboard includes request rate, p95 latency, 5xx rate,
and process memory. The backend instrumentation provides bounded route labels to
avoid high-cardinality metrics.

## Grafana image rendering

`/grafana` always sends configured dashboard links. It sends a PNG overview when a
Grafana Image Renderer is installed and these values are set:

```env
GRAFANA_RENDER_ENABLED=true
GRAFANA_SERVICE_ACCOUNT_TOKEN=replace-with-new-token
GRAFANA_DASHBOARD_OVERVIEW_URL=http://localhost:3000/d/agrivo-backend-overview/agrivo-backend-overview
```

If rendering is unavailable, the command safely falls back to links. `/chart` does
not require Grafana rendering; it creates its own PNG from Prometheus range data.

## Data and credentials

- GitHub Actions reads the repository REST API. A token is optional for a public
  repository but recommended to avoid low anonymous rate limits.
- Argo CD uses `ARGOCD_TOKEN`; use a read-only project/account token.
- Kubernetes uses the active kubeconfig context and performs only `kubectl get`.
- Gemini is optional and used only by `/ask`; deterministic health/incident output
  remains available without AI.
- GHCR image values shown by `/images` come from the running deployment specs, so
  they represent what Kubernetes is actually running.

## Validation

```powershell
python -m pytest -q -p no:cacheprovider
ruff check app tests
ruff format --check app tests
mypy app
node --check ..\backend\src\controllers\metricsController.js
node --check ..\backend\src\middleware\metricsMiddleware.js
```

The test suite uses mock HTTP transports and never calls real Telegram, Gemini,
GitHub, Kubernetes, Argo CD, Grafana, Prometheus, or Alertmanager credentials.
