#!/usr/bin/env python3
"""Fetch and freeze primary DOI metadata for the paper bibliography.

Crossref records are retained verbatim.  The generated BibTeX is derived from
those records rather than hand-entered metadata.  Network failures are explicit
and never converted into a successful audit.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

PROJECT = Path(__file__).resolve().parents[2]
META = PROJECT / "docs" / "reference-metadata"
META.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    ("necula1997", "10.1145/263699.263712", "certificates"),
    ("appel2001", "10.1109/LICS.2001.932501", "certificates"),
    ("hoare1969", "10.1145/363235.363259", "verification"),
    ("cousot1977", "10.1145/512950.512973", "verification"),
    ("cook1979", "10.1016/0022-0000(79)90024-2", "certificates"),
    ("blum1995", "10.1145/210332.210339", "certificates"),
    ("micali2000", "10.1137/S0097539795284959", "verifiable-computation"),
    ("gkr2015", "10.1145/2699436", "verifiable-computation"),
    ("parno2013", "10.1109/SP.2013.47", "verifiable-computation"),
    ("bensasson2018", "10.1145/3211332.3211337", "verifiable-computation"),
    ("kate2010", "10.1007/978-3-642-17373-8_11", "verifiable-computation"),
    ("ateniese2007", "10.1145/1315245.1315318", "remote-storage"),
    ("juels2007", "10.1145/1315245.1315317", "remote-storage"),
    ("shacham2008", "10.1007/978-3-540-89255-7_7", "remote-storage"),
    ("erway2009", "10.1145/1653662.1653688", "remote-storage"),
    ("barvinok1994", "10.1287/moor.19.4.769", "integer-counting"),
    ("cooper1972", "10.1016/0004-3702(72)90020-X", "integer-counting"),
    ("pugh1992", "10.1145/143165.143197", "integer-counting"),
    ("verdoolaege2010", "10.1007/978-3-642-11970-5_10", "integer-counting"),
    ("clauss1996", "10.1145/237090.237131", "integer-counting"),
    ("woods2004", "10.1016/j.jsc.2003.07.003", "integer-counting"),
    ("carter1979", "10.1016/0022-0000(79)90044-8", "permutations"),
    ("luby1988", "10.1137/0217084", "permutations"),
    ("black2002", "10.1007/3-540-45760-7_9", "permutations"),
    ("morris2009", "10.1007/978-3-642-04138-9_19", "permutations"),
    ("lemire2019", "10.1145/3230636", "permutations"),
    ("salmon2011", "10.1145/2063384.2063405", "permutations"),
    ("steele2014", "10.1145/2660193.2660195", "permutations"),
    ("bloom1970", "10.1145/362686.362692", "set-representation"),
    ("dean2008", "10.1145/1327452.1327492", "distributed-data"),
    ("ghemawat2003", "10.1145/945445.945450", "distributed-data"),
    ("corbett2013", "10.1145/2491245", "distributed-data"),
    ("dewitt1992", "10.1145/129888.129894", "distributed-data"),
    ("graefe1993", "10.1145/152610.152611", "distributed-data"),
    ("zaharia2016", "10.1145/2934664", "distributed-data"),
    ("isard2007", "10.1145/1272996.1273005", "distributed-data"),
    ("ousterhout2013", "10.1145/2517349.2522716", "distributed-data"),
    ("karger1997", "10.1145/258533.258660", "sharding"),
    ("stoica2001", "10.1145/383059.383071", "sharding"),
    ("decandia2007", "10.1145/1294261.1294281", "sharding"),
    ("lakshman2010", "10.1145/1773912.1773922", "sharding"),
    ("thomson2012", "10.1145/2213836.2213838", "distributed-data"),
    ("bailis2014", "10.14778/2732232.2732237", "distributed-data"),
    ("lamport1982", "10.1145/357172.357176", "dependability"),
    ("schneider1990", "10.1145/98163.98167", "dependability"),
    ("chandra1996", "10.1145/226643.226647", "dependability"),
    ("lamport1978", "10.1145/359545.359563", "dependability"),
    ("chandy1985", "10.1145/214451.214456", "dependability"),
    ("lamport1979", "10.1109/TC.1979.1675439", "dependability"),
    ("simmhan2005", "10.1145/1084805.1084812", "provenance"),
    ("buneman2001", "10.1007/3-540-44503-X_20", "provenance"),
    ("cheney2009", "10.1561/1900000006", "provenance"),
    ("bondhugula2008", "10.1145/1375581.1375595", "polyhedral"),
    ("bastoul2004", "10.1109/PACT.2004.10018", "polyhedral"),
    ("grosser2011", "10.1109/PACT.2011.23", "polyhedral"),
    ("feautrier1991", "10.1142/S0129626491000128", "polyhedral"),
    ("collberg2016", "10.1145/2812803", "reproducibility"),
    ("mohan1992", "10.1145/128765.128770", "distributed-data"),
]


def run_curl(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "--retry-delay", "1", "--connect-timeout", "15", "--max-time", "45",
         "-H", "User-Agent: PCS-artifact/2.0 (mailto:anonymous@example.invalid)", url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or f"curl failed for {url}")
    return proc.stdout


def clean_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", "", value or ""))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("–", "--").replace("—", "---").replace("−", "-")
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tex(value: str) -> str:
    value = clean_text(value)
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def first(message, key, default=""):
    value = message.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def year_of(message):
    for key in ("published-print", "published-online", "issued", "created"):
        try:
            return int(message[key]["date-parts"][0][0])
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return None


def bib_entry(key, message):
    kind = message.get("type", "journal-article")
    entry_type = "article" if kind == "journal-article" else "inproceedings" if "proceedings" in kind else "misc"
    authors = []
    for author in message.get("author", []):
        family = clean_text(author.get("family", ""))
        given = clean_text(author.get("given", ""))
        if family:
            authors.append(f"{family}, {given}" if given else family)
    title = tex(first(message, "title"))
    container = tex(first(message, "container-title"))
    fields = [
        ("author", " and ".join(tex(a) for a in authors)),
        ("title", "{" + title + "}"),
    ]
    if entry_type == "article":
        fields.append(("journal", container))
    elif entry_type == "inproceedings":
        fields.append(("booktitle", container))
    else:
        fields.append(("howpublished", container))
    fields += [
        ("year", str(year_of(message) or "")),
        ("volume", clean_text(str(message.get("volume", "")))),
        ("number", clean_text(str(message.get("issue", "")))),
        ("pages", clean_text(str(message.get("page", ""))).replace("-", "--")),
        ("publisher", tex(str(message.get("publisher", "")))),
        ("doi", tex(message["DOI"].lower())),
    ]
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields if value)
    return f"@{entry_type}{{{key},\n{body}\n}}\n"


def main():
    records = []
    failures = []
    for index, (key, doi, category) in enumerate(CANDIDATES):
        url = "https://api.crossref.org/works/" + quote(doi, safe="")
        try:
            payload = json.loads(run_curl(url))
            message = payload["message"]
            resolved = str(message.get("DOI", "")).lower()
            if resolved != doi.lower():
                raise RuntimeError(f"DOI mismatch: {resolved}")
            title = clean_text(first(message, "title"))
            year = year_of(message)
            authors = message.get("author", [])
            if not title or not year or not authors:
                raise RuntimeError("metadata lacks title, year, or author")
            record = {
                "key": key, "doi": doi.lower(), "category": category,
                "title": title, "year": year,
                "container_title": clean_text(first(message, "container-title")),
                "publisher": clean_text(str(message.get("publisher", ""))),
                "crossref_status": "verified",
                "crossref_url": url,
                "raw_file": f"reference-metadata/{key}.json",
                "message": message,
            }
            (META / f"{key}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            records.append(record)
        except Exception as exc:
            failures.append({"key": key, "doi": doi, "category": category, "error": str(exc)})
        time.sleep(0.05)

    if len(records) < 40:
        (PROJECT / "docs" / "reference-fetch-failures.json").write_text(json.dumps(failures, indent=2) + "\n")
        raise RuntimeError(f"only {len(records)} DOI records verified; at least 40 are required")

    # Keep every verified candidate.  Duplicate DOI and key checks are hard gates.
    keys = [r["key"] for r in records]
    dois = [r["doi"] for r in records]
    if len(keys) != len(set(keys)) or len(dois) != len(set(dois)):
        raise RuntimeError("duplicate key or DOI in verified bibliography")

    bib = "% Generated from retained Crossref records by fetch_references.py.\n"
    for record in records:
        bib += bib_entry(record["key"], record["message"]) + "\n"
    (PROJECT / "paper" / "references.bib").write_text(bib, encoding="utf-8")
    (PROJECT / "supplement" / "references.bib").write_text(bib, encoding="utf-8")

    groups = {}
    for record in records:
        groups.setdefault(record["category"], []).append(record["key"])
    macro_names = {
        "certificates": "RefsCertificates", "verification": "RefsVerification",
        "verifiable-computation": "RefsVerifiableComputation", "remote-storage": "RefsRemoteStorage",
        "integer-counting": "RefsIntegerCounting", "permutations": "RefsPermutations",
        "set-representation": "RefsSetRepresentation", "distributed-data": "RefsDistributedData",
        "sharding": "RefsSharding", "dependability": "RefsDependability",
        "provenance": "RefsProvenance", "polyhedral": "RefsPolyhedral",
        "reproducibility": "RefsReproducibility",
    }
    macro_text = "% Generated reference-group citations; every retained item is cited in the main text.\n"
    for category, keys_in_group in sorted(groups.items()):
        name = macro_names[category]
        macro_text += f"\\newcommand{{\\{name}}}{{\\cite{{{','.join(keys_in_group)}}}}}\n"
    macro_text += f"\\newcommand{{\\VerifiedReferenceCount}}{{{len(records)}}}\n"
    (PROJECT / "paper" / "reference-macros.tex").write_text(macro_text, encoding="utf-8")

    public_records = [{k: v for k, v in r.items() if k != "message"} for r in records]
    verification = {
        "schema": "pcs-reference-verification-v2",
        "method": "Crossref REST /works/{doi}; exact DOI match; nonempty author/title/year; raw responses retained",
        "verified_count": len(records),
        "failed_count": len(failures),
        "records": public_records,
        "failures": failures,
    }
    (PROJECT / "docs" / "reference-verification.json").write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Reference audit", "",
        f"Verified DOI records: **{len(records)}**. Failed candidates retained separately: **{len(failures)}**.", "",
        "The audit queried Crossref's work endpoint, required an exact DOI match and nonempty author, title, and year fields, and retained each raw JSON response. It verifies bibliographic identity, not that every paper was read in full.", "",
        "| Key | Year | Title | DOI | Category |", "|---|---:|---|---|---|",
    ]
    for r in public_records:
        title = r["title"].replace("|", "\\|")
        lines.append(f"| `{r['key']}` | {r['year']} | {title} | `{r['doi']}` | {r['category']} |")
    if failures:
        lines += ["", "## Candidates not admitted", "", "These entries are not present in the paper bibliography.", "", "| Key | DOI | Reason |", "|---|---|---|"]
        for f in failures:
            lines.append(f"| `{f['key']}` | `{f['doi']}` | {f['error'].replace('|','/')} |")
    (PROJECT / "docs" / "REFERENCE-AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"verified": len(records), "failed": len(failures)}, sort_keys=True))

if __name__ == "__main__":
    main()
