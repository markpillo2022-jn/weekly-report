# Nightly update of the public weekly report

Runs at 12:01 AM, 6:01 AM, 12:01 PM and 6:01 PM US Eastern (America/New_York). Goal: refresh `data.json` in the GitHub repository so the public domain shows current numbers.

1. Make a temp folder RAW.
2. ClickUp (connector ClickUp, tool clickup_filter_tasks) for each manager, save the whole JSON answer as RAW/dir_<key>.json:
   args: list_ids ["901415242260"], statuses ["active"], fields ["status"], custom_fields
   [{field_id "b9fc52f5-0993-4bc7-8b51-a0393b159008", operator "=", value "c85f1a51-cf54-4e1d-959c-1024f142863a"},
    {field_id "97fdfe84-32fc-402d-acce-85ccf9a7c06d", operator "ANY", value "[\"<user id>\"]"}]
   user ids: danica 88234611, genesis 88234493, marge 88283803, mark 88234610.
3. For every returned task whose task_id is in tools/accounts_map.json with a non-empty meta_account_id, call Meta MCP
   ads_get_ad_entities twice and save the raw answer (or {"error": "<message>"} on failure):
   RAW/life_<id>.json  date_preset "maximum"
   RAW/d30_<id>.json   date_preset "last_30d", time_increment "1"
   common args: level "campaign", fields ["name","amount_spent","lead"], limit 1000,
   filtering [{campaign.name CONTAIN ["JN"]}, {campaign.name CONTAIN ["Conversion"]}, {amount_spent GREATER_THAN ["0"]}],
   reporting_purpose ["metric_lookup"], include_additional_context false, advertiser_job "report_measure_or_look_up".
4. Typed-in numbers: ArtifactData list collection "data/team/manual" on https://claude.ai/artifact/YLxWMwndf37x88tJC4Sghh;
   save as RAW/manual.json = list of {"id": doc_id, ...doc fields}. If it fails, save [].
5. python3 tools/build_data.py RAW data.json
6. Commit only data.json ("Nightly data update <date>") and push to the Pages branch. Change nothing else.
If ClickUp fails, stop without pushing (yesterday's page stays up).
