# Deploying the campus assistant

## Required setup after the data/voice fix

The Flask app runs outside a notebook. It reads Unity Catalog with the Databricks SQL connector instead of relying on a notebook's `spark` object.

1. Add a SQL warehouse resource to the Databricks app with the resource key `sql-warehouse` and grant the app **CAN USE**.
2. Grant the app's service principal **USE CATALOG** on `workspace`, **USE SCHEMA** on `workspace.default` and `workspace.vthacks`, and **SELECT** on the tables below. A notebook user's access does not grant access to the app.
3. Add secret resources with these keys (the YAML files reference them with `valueFrom`):
   - `elevenlabs-api-key`: exported as `ELEVENLABS_API_KEY`.
   - `gemini-api-key`: exported as `GEMINI_API_KEY`.
   - `tigerdata-url`: exported as `TIGERDATA_URL`.
4. Rotate the previously committed ElevenLabs, Gemini, and Tiger Data credentials. Removing the app's defaults does not revoke them or erase notebook copies and Git history. Do not paste replacements into source files.
5. Deploy from the repository root. Its `app.yaml` launches `VThacks_HokieCrew/app.py`. Deploying only the nested folder is also supported; it now has its own `requirements.txt`.

If a service is intentionally disabled, remove its `valueFrom` entry before deploying; the corresponding feature is disabled when its environment variable is absent. Databricks provides OAuth credentials for the app automatically. Do not add a personal access token to source code.

For a local process, configure Databricks unified authentication and `DATABRICKS_HOST`, plus either `DATABRICKS_WAREHOUSE_ID` or `DATABRICKS_HTTP_PATH`. An explicit HTTP path takes precedence.

## Data tables

Run the ingestion notebooks first, using a principal with permission to create/populate these tables:

- Bus: `workspace.vthacks.bt_routes_full`, `workspace.vthacks.bt_vehicle_positions`.
- Food: `workspace.default.food_menus`, `workspace.default.restaurants`.
- Health: `workspace.default.health_resources`.
- Events: `workspace.default.ii_campus_events`, `workspace.default.ii_student_clubs`, `workspace.default.ii_cultural_centers`.
- Professional: `workspace.default.research_opportunities`, `workspace.default.career_resources`, `workspace.default.career_events`, `workspace.default.career_pathways`.

The event notebook creates the `ii_*` names, not the `*_clean` names previously queried by the app. Verify existing workspace tables if ingestion was customized.

Menu dietary flags use `is_vegetarian`, `is_vegan`, and `is_halal`; restaurant flags use `vegetarian`, `vegan`, and `gluten_free`. Missing flags are not considered verified matches. This is not comprehensive allergen matching or a guarantee against cross-contact; the current source does not have explicit gluten-free menu or halal restaurant flags.

Gemini defaults to `gemini-2.5-flash`; set `GEMINI_MODEL` to another model supported by your account. Failed classification falls back to keyword routing. Food responses skip generative rewriting to preserve filter results.

## Verification

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The regression tests use mocked external services. They verify SQL row conversion, table names, request validation, transcription contracts, dietary filtering, and that equivalent voice/text requests use the same recommendation path.

After redeploying, test both typing and speaking "vegan food", "bus to Walmart", and "find a club". Check the transcript, response, and audio. `/health` is a process/configuration check, not proof that warehouse permissions, external credentials, or datasets work. Inspect app logs for the underlying exception when the API returns a data-unavailable error.

## Remaining limitations

- Live warehouse, microphone, and external-service access have not been verified by the offline tests.
- Tiger Data uses one shared connection; autocommit prevents failed statements from poisoning later transactions, but connection pooling/reconnection remains future work.
- Missing or invalid bus telemetry is preserved as unavailable rather than converted to zero. Tiger Data population and data freshness need live verification.
- Event fixtures include historical dates, and bus/gym notebooks include simulated data. The app should not be presented as a verified live operational service without refreshing and validating those feeds.

References: [Databricks app authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth), [SQL warehouse resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse), [environment resource references](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/environment-variables), [ElevenLabs transcription](https://elevenlabs.io/docs/api-reference/speech-to-text/convert), [Gemini models](https://ai.google.dev/gemini-api/docs/models).
