"""
Export the EuRepoC spreadsheet into data.js for the interactive dyadic
timeline page (index.html).

The parsing logic mirrors final_scripts/fig10_dyadic_timeline.py: primary
initiator country, exploded multi-date legal/political responses, canonical
lane names from codebook sections 52 and 25, and the HIIK offline conflict
level. The page then filters the exported incidents per country pair in the
browser.

Usage (from the thesis root or this folder):
    py -3 build_data.py                 # uses ../notes/data/eurepoc_*.xlsx
    py -3 build_data.py path/to/eurepoc.xlsx
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_XLSX = HERE.parent / "notes" / "data" / "eurepoc_data_2026-06-19T18_00.xlsx"

# EuRepoC only records legal responses systematically from 2017.
START_YEAR = 2016

_UNKNOWN = {"Not available", "Unknown", "nan", ""}

# Display aliases used in the country menu and titles.
LABELS = {
    "Iran, Islamic Republic of": "Iran",
    "Korea, Democratic People's Republic of": "North Korea",
    "Korea, Republic of": "South Korea",
    "Moldova, Republic of": "Moldova",
    "Russian Federation": "Russia",
    "Syrian Arab Republic": "Syria",
    "Taiwan, Province of China": "Taiwan",
    "Tanzania, United Republic of": "Tanzania",
    "Venezuela, Bolivarian Republic of": "Venezuela",
    "Viet Nam": "Vietnam",
}

# ---------------------------------------------------------------------------
# codebook section 52 - legal response types
# ---------------------------------------------------------------------------
LEGAL_TYPE_CANONICAL = [
    "Peaceful means: Retorsion",
    "Reprisal / Countermeasures",
    "Use of force",
    "No justification under IL",
    "Restrictive measures (EU/TFEU)",
    "Solidarity clause (Art. 222 TFEU)",
    "Collective self-defence (Art. 42 TEU)",
    "Proclamation of emergency",
    "Other national legal measures",
]
LEGAL_TYPE_PATTERNS = [
    ("Peaceful means: Retorsion", ["peaceful means", "retorsion"]),
    ("Reprisal / Countermeasures", ["reprisal", "countermeasure"]),
    ("Use of force", ["use of force"]),
    ("No justification under IL", ["no justification"]),
    ("Restrictive measures (EU/TFEU)", ["restrictive measure", "art. 215", "215 tfeu"]),
    ("Solidarity clause (Art. 222 TFEU)", ["solidarity", "222 tfeu", "art. 222"]),
    ("Collective self-defence (Art. 42 TEU)", ["collective", "42 (7) teu"]),
    ("Proclamation of emergency", ["proclamation", "public emergency"]),
    ("Other national legal measures", ["other legal", "law enforcement", "arrest",
                                       "national level", "investigation"]),
]


def parse_legal_type(tok):
    if not tok or tok.strip() in _UNKNOWN:
        return "Other national legal measures"
    primary = tok.strip().split(" - ")[0].strip().lower()
    for canonical, patterns in LEGAL_TYPE_PATTERNS:
        if any(p in primary for p in patterns):
            return canonical
    return "Other national legal measures"


# ---------------------------------------------------------------------------
# codebook section 25 - political response types (4 actor groups x 5 kinds)
# ---------------------------------------------------------------------------
def parse_political_type(tok):
    if not tok or tok.strip() in _UNKNOWN:
        return "State: Stabilizing"
    fl = tok.strip().lower()

    if any(k in fl for k in ["cfsp", "hr on behalf", "high representative",
                             "eu demarche", "eu demarches",
                             "common position of the european council",
                             "title v chapter", "art. 215", "art. 222",
                             "solidarity clause", "222 tfeu"]):
        actor = "EU"
    elif any(k in fl for k in ["eu member state", "eu member states",
                               "member states", "foreign ministers",
                               "heads of state"]):
        actor = "EU MS"
    elif any(k in fl for k in ["secretary-general", "secretary general",
                               "international organ", "supranational",
                               "un ", "nato ", "osce "]):
        actor = "Int'l Org"
    else:
        actor = "State"

    if any(k in fl for k in ["preventive", "awareness raising",
                             "capacity building", "confidence and security"]):
        kind = "Preventive"
    elif any(k in fl for k in ["cooperative", "demarche", "protest note"]):
        kind = "Cooperative"
    elif any(k in fl for k in ["stabiliz", "statement by", "head of state",
                               "head of government", "foreign affair",
                               "foreign minister", "secretary-general",
                               "common position", "cfsp conclusion",
                               "cfsp decision", "declaration of hr",
                               "declaration", "cfsp"]):
        kind = "Stabilizing"
    elif any(k in fl for k in ["legislative", "parliamentary investigation",
                               "legislative initiative"]):
        kind = "Legislative"
    elif any(k in fl for k in ["executive", "removal from office", "resignation"]):
        kind = "Executive"
    else:
        kind = "Stabilizing"
    return f"{actor}: {kind}"


# ---------------------------------------------------------------------------
# helpers (ported from fig10_dyadic_timeline.py)
# ---------------------------------------------------------------------------
def primary_country(val, sep=";"):
    if pd.isna(val):
        return None
    tok = str(val).split(sep)[0].split(" - ")[0].strip()
    return None if (tok in _UNKNOWN or tok.lower() == "nan") else tok


def country_list(val, sep=";"):
    if pd.isna(val):
        return []
    out = []
    for part in str(val).split(sep):
        tok = part.split(" - ")[0].strip()
        if tok and tok not in _UNKNOWN and tok.lower() != "nan" and tok not in out:
            out.append(tok)
    return out


def hiik_numeric(val) -> int:
    if pd.isna(val):
        return 0
    s = str(val).upper()
    for n in range(5, 0, -1):
        if f"HIIK {n}" in s:
            return n
    return 0


_STATE_CATS = {"State", "Non-state actor, state-affiliation suggested"}
_INITIATOR_RANK = {"State": 0, "Non-state actor, state-affiliation suggested": 1,
                   "Non-state-group": 2}


def highest_initiator(val) -> str:
    if pd.isna(val):
        return "Not available / Unknown"
    cats = [(s.strip(), _INITIATOR_RANK.get(s.strip(), 99))
            for s in str(val).split(";") if s.strip()]
    return min(cats, key=lambda x: x[1])[0] if cats else "Not available / Unknown"


def first_token(val):
    if pd.isna(val):
        return ""
    tok = str(val).split(";")[0].strip()
    return "" if tok in _UNKNOWN else tok


_SKIP = {"nan", "not available", "unknown", ""}


def explode_responses(row, date_col_str, cols, parse_fn):
    """One dict per dated response; short parallel lists reuse their last token."""
    date_tokens = [s.strip() for s in str(row.get(date_col_str, "") or "").split(";")
                   if s.strip().lower() not in _SKIP]
    if not date_tokens:
        return []
    col_tokens = {}
    for col in cols:
        parts = [s.strip() for s in str(row.get(col, "") or "").split(";")]
        col_tokens[col] = parts if any(parts) else [""]

    out = []
    for i, ds in enumerate(date_tokens):
        dt = pd.to_datetime(ds, errors="coerce")
        if pd.isna(dt):
            continue
        vals = {}
        for col in cols:
            toks = col_tokens[col]
            v = toks[i] if i < len(toks) else toks[-1]
            vals[col] = "" if v in _UNKNOWN or v.lower() == "nan" else v
        rec = {
            "d": dt.strftime("%Y-%m-%d"),
            "cat": parse_fn(vals.get(f"{'legal' if parse_fn is parse_legal_type else 'political'}_response_type", "")),
            "raw": vals.get(f"{'legal' if parse_fn is parse_legal_type else 'political'}_response_type", ""),
            "actor": vals.get(f"{'legal' if parse_fn is parse_legal_type else 'political'}_response_actor", ""),
            "country": vals.get(f"{'legal' if parse_fn is parse_legal_type else 'political'}_response_country", ""),
        }
        out.append(rec)
    return out


def clean(val):
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s in _UNKNOWN else s


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def main():
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    print(f"Loading {xlsx} ...")
    raw = pd.read_excel(xlsx)
    raw["_legal_date_str"] = raw["legal_response_date"].fillna("").astype(str)
    raw["_pol_date_str"] = raw["political_response_date"].fillna("").astype(str)
    raw["start_date"] = pd.to_datetime(raw["start_date"], errors="coerce")
    raw = raw[raw["start_date"].dt.year >= START_YEAR]
    raw = raw.dropna(subset=["start_date", "weighted_cyber_intensity"])
    print(f"  {len(raw):,} rows from {START_YEAR}")

    legal_cols = ["legal_response_type", "legal_response_country",
                  "legal_response_actor"]
    pol_cols = ["political_response_type", "political_response_country",
                "political_response_actor"]

    incidents = []
    init_count, recv_count = {}, {}
    for _, row in raw.iterrows():
        ic = primary_country(row.get("initiator_country"))
        rc = country_list(row.get("receiver_country"))
        if ic is None or not rc:
            continue                      # can never appear in a dyad
        legal = (explode_responses(row, "_legal_date_str", legal_cols, parse_legal_type)
                 if float(row.get("number_of_legal_responses") or 0) > 0 else [])
        pol = (explode_responses(row, "_pol_date_str", pol_cols, parse_political_type)
               if float(row.get("number_of_political_responses") or 0) > 0 else [])
        urls = [u.strip() for u in str(row.get("sources_url") or "").split(";")
                if u.strip().lower().startswith("http")]
        incidents.append({
            "id": int(row["ID"]),
            "name": clean(row.get("name")),
            "d": row["start_date"].strftime("%Y-%m-%d"),
            "desc": clean(row.get("description")),
            "ic": ic,
            "rc": rc,
            "itype": first_token(row.get("incident_type")),
            "iname": first_token(row.get("initiator_name")),
            "icat": first_token(row.get("initiator_category")),
            "state": highest_initiator(row.get("initiator_category")) in _STATE_CATS,
            "wci": float(row["weighted_cyber_intensity"]),
            "hiik": hiik_numeric(row.get("offline_conflict_intensity_subcode")),
            "urls": urls,
            "legal": legal,
            "pol": pol,
        })
        init_count[ic] = init_count.get(ic, 0) + 1
        for c in rc:
            recv_count[c] = recv_count.get(c, 0) + 1

    countries = sorted(set(init_count) | set(recv_count),
                       key=lambda c: LABELS.get(c, c))
    country_meta = [{"name": c, "label": LABELS.get(c, c),
                     "n": init_count.get(c, 0) + recv_count.get(c, 0)}
                    for c in countries]

    payload = {
        "meta": {
            "source": xlsx.name,
            "generated": date.today().isoformat(),
            "start_year": START_YEAR,
            "n_incidents": len(incidents),
        },
        "countries": country_meta,
        "incidents": incidents,
    }
    out = HERE / "data.js"
    with open(out, "w", encoding="utf-8") as f:
        f.write("// Generated by build_data.py - do not edit by hand.\n")
        f.write("window.EUREPOC = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"  {len(incidents):,} incidents, {len(countries)} countries "
          f"-> {out.name} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
