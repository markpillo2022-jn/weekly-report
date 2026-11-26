#!/usr/bin/env python3
"""Build fresh-fuel/data.json from raw Meta answers.

Usage: python3 build_data.py RAW_DIR OUT_JSON

Clients, targets (ROAS multiple, or cost per lead in the account currency) and colors live in clients.json next to this file.
RAW_DIR holds, for each client's ad account id <act>, the saved ads_get_ad_entities answers (or {"error": "..."}):
  d30_<act>.json   level campaign, date_preset last_30d, amount_spent > 0
  d14_<act>.json   level campaign, date_preset last_14d, amount_spent > 0
  d7_<act>.json    level campaign, date_preset last_7d,  amount_spent > 0
  life_<act>.json  level campaign, date_preset maximum, object_ids = the campaign ids in d30
  acct_<act>.json  level ad_account, date_preset maximum
  mtd_<act>.json   level ad_account, date_preset this_month (month to date, for the top chart; optional)
fields: name, amount_spent, omni_purchase_values, lead (life adds effective_status).
ROAS clients use omni_purchase_values; CPL clients use lead.
"""
import json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
r2 = lambda v: round(v + 0.0, 2)


def load(path):
    if not os.path.exists(path):
        return None
    a = json.load(open(path))
    if isinstance(a, dict) and set(a) == {"result"}:
        a = a["result"]
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            return None
    if isinstance(a, dict) and a.get("error"):
        return None
    ents = a.get("ad_entities") if isinstance(a, dict) else a
    if isinstance(ents, str):
        ents = json.loads(ents)
    return ents if isinstance(ents, list) else None


def num(v):
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def ratio(m, s, v):
    if m == "cpl":
        return r2(s / v) if v > 0 else None
    return r2(v / s) if s > 0 and v > 0 else (0.0 if s > 0 else None)


def main(raw, out_path):
    clients = json.load(open(os.path.join(HERE, "clients.json")))
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "manager": "Mark Pilio", "clients": []}
    tot = {}
    for c in clients:
        m, act = c["metric"], c["act"]
        V = "leads" if m == "cpl" else "value"
        field = "lead" if m == "cpl" else "omni_purchase_values"
        d30, d14, d7, life, acct = (load(os.path.join(raw, f"{p}_{act}.json")) for p in ("d30", "d14", "d7", "life", "acct"))
        entry = dict(key=c["key"], label=c["label"], color=c["color"], metric=m, target=c.get("target"), currency=c["currency"],
                     timezone=c["timezone"], ads_url="https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=" + act)
        if any(x is None for x in (d30, d14, d7, life, acct)):
            entry |= dict(error="Meta could not be read for this account", totals={}, rows=[])
            out["clients"].append(entry)
            continue
        by7 = {e["id"]: e for e in d7}
        by14 = {e["id"]: e for e in d14}
        byl = {e["id"]: e for e in life}
        rows = []
        for e in d30:
            i = e["id"]; s7e = by7.get(i, {}); s14e = by14.get(i, {}); le = byl.get(i, {})
            vals = {"all": (num(le.get("amount_spent")), num(le.get(field))), "30": (num(e.get("amount_spent")), num(e.get(field))),
                    "14": (num(s14e.get("amount_spent")), num(s14e.get(field))), "7": (num(s7e.get("amount_spent")), num(s7e.get(field)))}
            r = dict(campaign=e.get("name", ""), active=le.get("effective_status") == "ACTIVE")
            r["ads_url"] = f"https://adsmanager.facebook.com/adsmanager/manage/adsets?act={act}&selected_campaign_ids={i}"
            for p, (s, v) in vals.items():
                r[f"spend_{p}"] = r2(s); r[f"{V}_{p}"] = int(v) if V == "leads" else r2(v); r[f"{m}_{p}"] = ratio(m, s, v)
            rows.append(r)
        rows.sort(key=lambda r: (-r["spend_7"], -r["spend_14"], -r["spend_30"], -r["spend_all"]))  # top spender first
        S = lambda k: sum(r[k] for r in rows)
        a = acct[0] if acct else {}
        t = dict(campaigns=len(rows), active=sum(r["active"] for r in rows))  # totals cover every campaign, active or paused
        for p, s, v in (("all", num(a.get("amount_spent")), num(a.get(field))), ("30", S("spend_30"), S(f"{V}_30")), ("14", S("spend_14"), S(f"{V}_14")), ("7", S("spend_7"), S(f"{V}_7"))):
            t[f"spend_{p}"] = r2(s); t[f"{V}_{p}"] = int(v) if V == "leads" else r2(v); t[f"{m}_{p}"] = ratio(m, s, v)
        mtd = load(os.path.join(raw, f"mtd_{act}.json"))
        if mtd:
            ms, mv = num(mtd[0].get("amount_spent")), num(mtd[0].get(field))
            t["spend_mtd"] = r2(ms); t[f"{V}_mtd"] = int(mv) if V == "leads" else r2(mv); t[f"{m}_mtd"] = ratio(m, ms, mv)
        entry |= dict(totals=t, rows=[r for r in rows if r["active"]])  # only active campaigns are listed
        out["clients"].append(entry)
        if m == "roas":
            for k in ("spend_30", "value_30", "spend_14", "value_14", "spend_7", "value_7"):
                tot.setdefault(c["currency"], {}).setdefault(k, 0); tot[c["currency"]][k] += t[k]
    # clients ordered by last-7-day spend, top spender first (each in its own currency)
    out["clients"].sort(key=lambda c: -(c["totals"].get("spend_7") or 0))
    team = {"clients": sum(1 for c in out["clients"] if c["metric"] == "roas" and not c.get("error")), "by_currency": {}}
    for cur, d in tot.items():
        team["by_currency"][cur] = {k: r2(v) for k, v in d.items()} | {"roas_30": ratio("roas", d["spend_30"], d["value_30"]), "roas_14": ratio("roas", d["spend_14"], d["value_14"]), "roas_7": ratio("roas", d["spend_7"], d["value_7"])}
    g = lambda k: sum(d[k] for d in tot.values())
    team |= {"roas_7": ratio("roas", g("spend_7"), g("value_7")), "roas_30": ratio("roas", g("spend_30"), g("value_30"))}
    out["team"] = team
    json.dump(out, open(out_path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
