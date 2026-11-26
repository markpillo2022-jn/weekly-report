# Nightly update of the Fresh Fuel ROAS dashboard

Runs every night at 12:01 AM US Eastern (America/New_York). Read-only on the ad accounts: never change a campaign, ad set or budget.

1. Make a temp folder RAW. For each client in `fresh-fuel/tools/clients.json` (ad account id `act`), call Meta MCP `ads_get_ad_entities`
   and save the whole answer (or {"error": "<message>"} on failure). Common args: reporting_purpose ["metric_lookup"],
   include_additional_context false, advertiser_job "report_measure_or_look_up", scheduled_task_run true.
   - RAW/d30_<act>.json  level "campaign", date_preset "last_30d", fields ["name","amount_spent","omni_purchase_values","lead"],
     filtering [{"field":"amount_spent","operator":"GREATER_THAN","value":["0"]}], limit 200
   - RAW/d7_<act>.json   same, date_preset "last_7d"
   - RAW/life_<act>.json level "campaign", date_preset "maximum", fields ["name","amount_spent","omni_purchase_values","lead","effective_status"],
     object_ids = every campaign id in d30_<act>.json
   - RAW/acct_<act>.json level "ad_account", date_preset "maximum", fields ["amount_spent","omni_purchase_values","lead"]
   Follow any pagination cursor and merge pages into one ad_entities list before saving.
2. `python3 fresh-fuel/tools/build_data.py RAW fresh-fuel/data.json`
3. Commit only `fresh-fuel/data.json` ("Fresh Fuel nightly data <date>") and push. Push to `main` if `fresh-fuel/` exists on main;
   otherwise push to branch `fresh-fuel-roas-dashboard` (the preview PR is not merged yet).
4. Refresh the private preview: `python3 fresh-fuel/tools/make_artifact.py fresh-fuel/index.html <scratch>/ffroas`, then Artifact publish
   `<scratch>/ffroas/index.html` with files {"data.json": "<scratch>/ffroas/data.json"} and url https://claude.ai/artifact/7ZWLhAe96AwV1cCJuEgMBD
   (read it first with action "read").
If every Meta call fails, stop without pushing (yesterday's numbers stay up). Change nothing else.
