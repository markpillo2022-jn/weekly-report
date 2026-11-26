#!/usr/bin/env python3
"""Build site/data.json for the public weekly report from raw connector answers.

Usage: python3 build_data.py RAW_DIR OUT_JSON

RAW_DIR holds the answers saved by the nightly task:
  dir_<manager>.json       ClickUp clickup_filter_tasks answer ({"tasks": [...]}) for danica, genesis, marge, mark
  life_<metaId>.json       Meta ads_get_ad_entities answer, campaign level, date_preset maximum
  d30_<metaId>.json        Meta ads_get_ad_entities answer, campaign level, last_30d, time_increment 1
  manual.json              list of typed-in docs from the dashboard store data/team/manual ({"id": task_id, ...})
A Meta file holding {"error": "..."} (or missing) means the account could not be read.
Same rules as the Claude dashboard: only JN Conversion campaigns count, accounts with none are hidden,
cost per lead = spend / leads, last 7 days = 7 days ending on the last day of the 30-day pull.
"""
import json, os, re, sys
from datetime import date, timedelta, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
MANAGERS = [("danica", "Danica", "#0ea5a4"), ("genesis", "Genesis", "#f97316"),
            ("marge", "Marge", "#8b5cf6"), ("mark", "Mark Pilio", "#2563eb")]
TARGET = 140
JN = re.compile(r"\bJNM?\s*[-|:]?\s*conversions?\b", re.I)


def load(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        a = json.load(f)
    # unwrap {"result": ...} or a JSON string
    if isinstance(a, dict) and set(a) == {"result"}:
        a = a["result"]
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            return {"error": a}
    return a


def num(v):
    if v is None:
        return 0.0
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def meta_rows(a):
    """Returns list of {campaign,date,spend,leads} or None when unreadable."""
    if a is None or (isinstance(a, dict) and a.get("error")):
        return None
    ents = a.get("ad_entities") if isinstance(a, dict) else None
    if isinstance(ents, str):
        ents = json.loads(ents)
    if not isinstance(ents, list):
        return None
    return [{"campaign": r.get("name", ""), "date": r.get("date_start"), "spend": num(r.get("amount_spent")),
             "leads": num(r.get("lead"))} for r in ents if JN.search(str(r.get("name", "")))]


def r2(v):
    return round(v + 0.0, 2)


def cpl(s, l):
    return r2(s / l) if l > 0 else None


def acct_totals(life, daily):
    days = sorted([r for r in daily if r["date"]], key=lambda r: r["date"])
    week = []
    if days:
        cut = (date.fromisoformat(days[-1]["date"]) - timedelta(days=6)).isoformat()
        week = [r for r in days if r["date"] >= cut]
    s = lambda rows, k: sum(r[k] for r in rows)
    sa, la, s30, l30, s7, l7 = s(life, "spend"), s(life, "leads"), s(daily, "spend"), s(daily, "leads"), s(week, "spend"), s(week, "leads")
    return {"campaigns": len({r["campaign"] for r in life + daily}),
            "spend_all": r2(sa), "leads_all": int(la), "cpl_all": cpl(sa, la),
            "spend_30": r2(s30), "leads_30": int(l30), "cpl_30": cpl(s30, l30),
            "spend_7": r2(s7), "leads_7": int(l7), "cpl_7": cpl(s7, l7)}


def main(raw, out):
    amap = {str(m["task_id"]): m for m in json.load(open(os.path.join(HERE, "accounts_map.json")))}
    manual = {str(m.get("id")): m for m in (load(os.path.join(raw, "manual.json")) or []) if isinstance(m, dict)}
    F = ["spend_all", "leads_all", "spend_30", "leads_30", "spend_7", "leads_7"]
    team = {f: 0.0 for f in F}
    team_clients = 0
    managers = []
    for key, label, color in MANAGERS:
        d = load(os.path.join(raw, f"dir_{key}.json"))
        if not d or d.get("error") or not isinstance(d.get("tasks"), list):
            raise SystemExit(f"ClickUp list for {key} missing or failed: {d and d.get('error')}")
        rows = []
        for j, t in enumerate(d["tasks"]):
            tid = str(t["id"])
            m = amap.get(tid)
            name = m["account"] if m else re.sub(r"\s*\(\d+\)\s*$", "", t.get("name", ""))
            row = {"account": name, "ads_url": (m or {}).get("ads_url", ""), "note": (m or {}).get("note", "") if m else
                   "New in ClickUp: Meta ad account not linked yet", "order": (m or {}).get("order", 1000 + j)}
            mid = (m or {}).get("meta_account_id", "")
            life = meta_rows(load(os.path.join(raw, f"life_{mid}.json"))) if mid else None
            daily = meta_rows(load(os.path.join(raw, f"d30_{mid}.json"))) if mid else None
            if life is not None and daily is not None:
                tot = acct_totals(life, daily)
                if not tot["campaigns"]:
                    continue  # no JN Conversion campaigns: hidden
                row.update(tot, status="ok")
            elif tid in manual:
                mm = manual[tid]
                row.update({f: mm.get(f, 0) for f in F}, status="typed", typed_by=mm.get("by", ""), typed_at=mm.get("at", ""))
                for p in ("all", "30", "7"):
                    row["cpl_" + p] = cpl(num(row["spend_" + p]), num(row["leads_" + p]))
            else:
                row.update(status="na")
                if mid and not row["note"]:
                    row["note"] = "Meta data could not be read on the last update"
            rows.append(row)
        rows.sort(key=lambda r: (r["status"] == "na", -(num(r.get("spend_all")) if r["status"] != "na" else 0), r["order"]))
        tot = {f: 0.0 for f in F}
        for r in rows:
            if r["status"] != "na":
                for f in F:
                    tot[f] += num(r[f])
        totals = {"clients": len(rows)}
        for p in ("all", "30", "7"):
            totals["spend_" + p] = r2(tot["spend_" + p]); totals["leads_" + p] = int(tot["leads_" + p])
            totals["cpl_" + p] = cpl(tot["spend_" + p], tot["leads_" + p])
        for f in F:
            team[f] += tot[f]
        team_clients += len(rows)
        for r in rows:
            r.pop("order", None)
        managers.append({"key": key, "label": label, "color": color, "totals": totals, "rows": rows})
    t = {"clients": team_clients}
    for p in ("all", "30", "7"):
        t["spend_" + p] = r2(team["spend_" + p]); t["leads_" + p] = int(team["leads_" + p])
        t["cpl_" + p] = cpl(team["spend_" + p], team["leads_" + p])
    data = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "target": TARGET,
            "team": t, "managers": managers}
    with open(out, "w") as f:
        json.dump(data, f, indent=1)
    print(f"wrote {out}: {team_clients} clients, 7d spend {t['spend_7']}, 7d CPL {t['cpl_7']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
