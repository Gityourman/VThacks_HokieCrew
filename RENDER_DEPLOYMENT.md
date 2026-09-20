# Launch on Render

This deployment serves the Flask app from Render while keeping campus data in Databricks. No domain purchase is required: Render supplies an HTTPS `onrender.com` address.

## Create the service

1. Sign in to [Render](https://dashboard.render.com/).
2. Choose **New → Blueprint** and connect `Gityourman/VThacks_HokieCrew`, branch `main`.
3. Render reads the root `render.yaml`. The service explicitly uses the **Free** plan.
4. Enter the environment values below in Render, then deploy. Do not commit credentials or send them through chat.

Alternatively, choose **New → Web Service**, select the repository (or its public Git URL), and use:

| Setting | Value |
| --- | --- |
| Language | Python 3 |
| Branch | main |
| Root directory | Leave blank |
| Build command | `pip install -r requirements-render.txt` |
| Start command | `gunicorn --chdir VThacks_HokieCrew app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 --access-logfile - --error-logfile -` |
| Instance type | Free |
| Health check path | `/health` |

Set `PYTHON_VERSION=3.12.12` and the environment variables below for a manual Web Service. Render ignores the Databricks-specific `app.yaml` files. Existing Databricks deployments are unaffected.

## Connect Databricks

Create a dedicated service principal for this Render deployment in Databricks, generate an OAuth secret, and grant it CAN USE on the SQL warehouse. Grant USE CATALOG on `workspace`, USE SCHEMA on `workspace.default` and `workspace.vthacks`, and SELECT on the tables listed in [the data setup guide](VThacks_HokieCrew/APP_DEPLOYMENT.md).

The principal's application/client ID is not its display name or numeric workspace ID. If your workspace does not permit creating service principals or SQL warehouses, an administrator must complete this step; the app cannot inherit the notebook user's access.

| Render environment variable | Source |
| --- | --- |
| `DATABRICKS_AUTH_TYPE` | `oauth-m2m` |
| `DATABRICKS_HOST` | Workspace base URL, including `https://`; omit notebook paths and query parameters |
| `DATABRICKS_WAREHOUSE_ID` | Warehouse ID from its connection details |
| `DATABRICKS_CLIENT_ID` | Dedicated service principal's application ID |
| `DATABRICKS_CLIENT_SECRET` | OAuth secret generated for that service principal |
| `ELEVENLABS_API_KEY` | Rotated ElevenLabs key; required for voice |
| `GEMINI_API_KEY` | Rotated Gemini API key; omit to use keyword routing |
| `TIGERDATA_URL` | Rotated Timescale/PostgreSQL connection URL with `sslmode=require`; omit to disable its real-time features |

For an initial page-only deployment you can omit credentials using the manual Web Service flow. The page and `/health` can load, but data-dependent questions will not work until Databricks authentication is configured. The Blueprint prompts for every `sync: false` value; use the manual flow if deliberately omitting optional services.

If Databricks or Tiger Data restricts network access, allow the appropriate Render outbound addresses through the existing access policy. Do not make the databases public merely to resolve a connectivity error.

## Verify the launch

1. Wait until Render marks the deployment Live.
2. Open its HTTPS URL. Confirm the chat page loads.
3. Type `vegan food`, `bus to Walmart`, and `find a club` to verify the data connection.
4. Allow microphone access and speak the same questions. Check transcription and spoken replies.
5. Check Render logs if a query fails. A passing `/health` check only establishes that the process is running; it does not test data access or API keys.

The Free service can sleep when idle and wake slowly. Its limited memory may be insufficient if the datasets grow because the current app loads full tables into pandas. Databricks, Gemini, ElevenLabs, and Tiger Data retain their own quotas and costs. This Render URL is publicly accessible and does not inherit Databricks login protection; use a separate app access-control mechanism before serving private data.

## Optional GoDaddy domain

Once the provided address works, add a custom domain under the Render service's Settings. Copy Render's displayed DNS records into GoDaddy and wait for verification. The coupon is not needed for deployment.

References: [Render Flask deployment](https://render.com/docs/deploy-flask), [Blueprint configuration](https://render.com/docs/blueprint-spec), [Free service limits](https://render.com/docs/free), [Databricks OAuth M2M](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m).
