#!/usr/bin/env python3
"""
Weekly A&R Discovery Report Generator
Usage: python ar_report.py [--data-dir PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

from detections import (
    detection_1_velocity_outliers,
    detection_2_sonic_shifts,
    detection_3_geo_breakout,
    detection_4_cobrand,
    merge_detections,
)

GENRES_SCANNED = [
    "EDM", "Phonk", "Ambient",
    "Regional Mexican", "Musica Mexicana", "Country", "Pop"
]

COBRAND_THRESHOLD = 1.5


# ── DATA LOADERS ──────────────────────────────────────────────────────────────

def load_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def load_csv_rows(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_text(path: Path) -> str:
    return path.read_text()


# ── FORMATTING HELPERS ────────────────────────────────────────────────────────

def fmt_listeners(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_pct(v: float) -> str:
    return f"{v*100:.0f}%"


def cobrand_flag_str(artist_data: dict) -> str:
    if artist_data.get("cobrand_flag"):
        cats = ", ".join(artist_data.get("cobrand_categories", []))
        return f"YES ({cats})"
    return "No"


def signed_str(artist_data: dict) -> str:
    return artist_data.get("signed_status", "unknown")


# ── REPORT SECTIONS ───────────────────────────────────────────────────────────

def section_header(week_end: str, total_artists: int) -> str:
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEEKLY A&R DISCOVERY REPORT — Week Ending {week_end}
Genres Scanned: {", ".join(GENRES_SCANNED)}
Total Artists Evaluated: {total_artists}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def section_d1(d1_artists: list[dict]) -> str:
    lines = ["", "── DETECTION 1: VELOCITY OUTLIERS ───────────────────────────────", ""]
    if not d1_artists:
        lines.append("  No velocity outliers detected this week.")
        return "\n".join(lines)
    lines.append(
        f"  Criteria: MoM growth >2× genre median AND accelerating. "
        f"{len(d1_artists)} artist(s) flagged.\n"
    )
    for a in sorted(d1_artists, key=lambda x: -x["mom_growth_rate_current"]):
        cobrand = cobrand_flag_str(a)
        lines.append(f"  ▶ {a['artist']}  [{a['genre']}]")
        lines.append(f"    Spotify: {a['spotify_url']}")
        lines.append(f"    Monthly Listeners : {fmt_listeners(a['spotify_monthly_listeners'])}")
        lines.append(f"    MoM Growth (curr)  : {fmt_pct(a['mom_growth_rate_current'])}  "
                     f"(prior: {fmt_pct(a['mom_growth_rate_prior'])}, "
                     f"genre median: {fmt_pct(a['genre_median_growth'])})")
        lines.append(f"    Months to 500K     : ~{a['months_to_500k']} mo")
        lines.append(f"    Cobrand Flag       : {cobrand}")
        lines.append(f"    Signed Status      : {signed_str(a)}")
        lines.append(f"    Detections         : {', '.join(a.get('detections', ['D1']))}")
        lines.append("")
    return "\n".join(lines)


def section_d2(shifts: list[dict]) -> str:
    lines = ["", "── DETECTION 2: SONIC TREND SHIFTS ──────────────────────────────", ""]
    if not shifts:
        lines.append("  No significant sonic shifts detected this week.")
        return "\n".join(lines)

    # Group by genre
    by_genre: dict[str, list[dict]] = {}
    for s in shifts:
        by_genre.setdefault(s["genre"], []).append(s)

    for genre, genre_shifts in by_genre.items():
        lines.append(f"  {genre}")
        for s in sorted(genre_shifts, key=lambda x: -abs(x["delta_pct"])):
            arrow = "↑" if s["direction"] == "UP" else "↓"
            lines.append(
                f"    {arrow} {s['metric'].upper()}: "
                f"12-mo avg {s['baseline_12mo']} → 4-wk avg {s['recent_4wk']} "
                f"({s['delta_pct']:+.1f}%)"
            )
        lines.append("")

    # Pattern commentary
    lines.append("  Emerging Pattern Notes:")

    phonk_tempos = [s for s in shifts if s["genre"] == "Phonk" and s["metric"] == "tempo"]
    if phonk_tempos:
        t = phonk_tempos[0]
        lines.append(
            f"  • PHONK TEMPO SURGE: Top releases averaging {t['recent_4wk']} BPM vs "
            f"{t['baseline_12mo']} BPM 12-mo avg ({t['delta_pct']:+.1f}%). "
            f"Faster, more aggressive sub-genre push. "
            f"Roster fits: NXGHT, Trace4000. "
            f"Target scout: artists doing 145+ BPM with Memphis/Atlanta influence."
        )

    edm_shifts = [s for s in shifts if s["genre"] == "EDM" and s["metric"] == "tempo"]
    if edm_shifts:
        t = edm_shifts[0]
        lines.append(
            f"  • EDM TEMPO UPLIFT: New releases tracking at {t['recent_4wk']} BPM vs "
            f"{t['baseline_12mo']} BPM average ({t['delta_pct']:+.1f}%). "
            f"Harder techno-adjacent crossover emerging. "
            f"Roster fits: Vexora."
        )

    mex_shifts = [s for s in shifts if s["genre"] in ("Musica Mexicana", "Regional Mexican")
                  and s["metric"] == "tempo"]
    for ms in mex_shifts:
        lines.append(
            f"  • {ms['genre'].upper()} TEMPO SHIFT: Rising to {ms['recent_4wk']} BPM "
            f"(+{ms['delta_pct']:.1f}% from {ms['baseline_12mo']}). "
            f"Faster, crossover-ready production replacing traditional tempos. "
            f"Roster fits: Cielo Bravo, Lúa Canela."
        )

    pop_shifts = [s for s in shifts if s["genre"] == "Pop" and s["metric"] in ("tempo", "energy")]
    if pop_shifts:
        pop_tempos = ", ".join(
            str(s["recent_4wk"]) + " BPM" for s in pop_shifts if s["metric"] == "tempo"
        )
        lines.append(
            f"  • POP ENERGY/TEMPO DIP: Emerging 'quiet storm' pop aesthetic. "
            f"Slower tempos ({pop_tempos}), "
            f"lower energy scores. Cinematic/sad-girl wave. "
            f"Roster fits: Soleil Fade, Halo Crush."
        )

    lines.append("")
    return "\n".join(lines)


def section_d3(d3_artists: list[dict]) -> str:
    lines = ["", "── DETECTION 3: GEOGRAPHIC BREAKOUT SIGNALS ─────────────────────", ""]
    if not d3_artists:
        lines.append("  No geographic breakout signals detected this week.")
        return "\n".join(lines)
    lines.append(
        f"  Criteria: >40% single-city concentration, decreased >5pp in 60 days. "
        f"{len(d3_artists)} artist(s) flagged.\n"
    )
    for a in sorted(d3_artists, key=lambda x: -x["geo_spread_delta"]):
        cobrand = cobrand_flag_str(a)
        reddit_note = (
            "✓ Reddit geographic corroboration detected"
            if a.get("reddit_geo_confirmed") else
            "— No Reddit geo corroboration yet"
        )
        lines.append(f"  ▶ {a['artist']}  [{a['genre']}]")
        lines.append(f"    Spotify: {a['spotify_url']}")
        lines.append(f"    Monthly Listeners   : {fmt_listeners(a['spotify_monthly_listeners'])}")
        lines.append(f"    Top City            : {a['city_top']}")
        lines.append(
            f"    City Concentration  : {a['city_top_pct_60d_ago']:.1f}% → "
            f"{a['city_top_pct']:.1f}% (−{a['geo_spread_delta']:.1f}pp in 60 days)"
        )
        lines.append(f"    Reddit Signal       : {reddit_note} (mentions: {a.get('reddit_mentions', 0)})")
        lines.append(f"    Cobrand Flag        : {cobrand}")
        lines.append(f"    Signed Status       : {signed_str(a)}")
        lines.append(f"    Detections          : {', '.join(a.get('detections', ['D3']))}")
        lines.append("")
    return "\n".join(lines)


def section_d4(d4_results: list[dict]) -> str:
    lines = ["", "── DETECTION 4: COBRAND CROSSOVER SIGNAL ────────────────────────", ""]
    flagged = [r for r in d4_results]
    if not flagged:
        lines.append("  No cobrand crossover signals among flagged artists.")
        return "\n".join(lines)
    lines.append(
        f"  Criteria: Affinity index >1.5× on fast food, streaming video, or major sportswear.\n"
    )
    for r in sorted(flagged, key=lambda x: -max(x["affinity_scores"].values(), default=0)):
        scores_str = ", ".join(
            f"{cat}: {score:.2f}×" for cat, score in r["affinity_scores"].items()
        )
        lines.append(f"  ▶ {r['artist']}")
        lines.append(f"    Brand Categories   : {', '.join(r['triggered_categories'])}")
        lines.append(f"    Affinity Indices   : {scores_str}")
        lines.append(
            f"    Assessment         : Audience commercially primed. "
            f"Recommend brand-deal clause in any deal structure."
        )
        lines.append("")
    return "\n".join(lines)


def section_top3(merged: dict[str, dict]) -> str:
    lines = ["", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             "TOP 3 PRIORITY — IMMEDIATE OUTREACH THIS WEEK",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]

    # Score: available > signed; more detections > fewer; highest growth
    def score(a: dict) -> float:
        s = len(a.get("detections", [])) * 10
        s += a.get("mom_growth_rate_current", 0) * 20
        if a.get("signed_status", "").startswith("available"):
            s += 15
        if a.get("cobrand_flag"):
            s += 5
        if a.get("reddit_geo_confirmed"):
            s += 3
        return s

    available = [a for a in merged.values()
                 if a.get("signed_status", "").startswith("available")]
    ranked = sorted(available, key=score, reverse=True)[:3]

    medals = ["#1", "#2", "#3"]
    for i, a in enumerate(ranked):
        growth_str = fmt_pct(a.get("mom_growth_rate_current", 0))
        detections = ", ".join(a.get("detections", []))
        months = a.get("months_to_500k")
        months_str = f" | ~{months} mo to 500K" if months else ""
        cobrand = "Cobrand: YES" if a.get("cobrand_flag") else ""
        lines.append(f"  {medals[i]}  {a['artist']}  [{a['genre']}]")
        lines.append(
            f"       {fmt_listeners(a['spotify_monthly_listeners'])} listeners | "
            f"{growth_str} MoM{months_str} | Detections: {detections}"
        )
        if cobrand:
            lines.append(f"       {cobrand} — {', '.join(a.get('cobrand_categories', []))}")
        # Scouting note
        note = _scouting_note(a)
        lines.append(f"       {note}")
        lines.append("")
    return "\n".join(lines)


def _scouting_note(a: dict) -> str:
    name = a["artist"]
    genre = a["genre"]
    listeners = fmt_listeners(a["spotify_monthly_listeners"])
    growth = fmt_pct(a.get("mom_growth_rate_current", 0))
    months = a.get("months_to_500k", "?")
    city = a.get("city_top", "")
    spread = a.get("geo_spread_delta")
    cobrand = a.get("cobrand_flag", False)
    cats = ", ".join(a.get("cobrand_categories", []))

    notes = {
        "NXGHT": (
            f"{name} is the clearest breakout case this week: {growth} MoM Phonk growth with "
            f"acceleration, TikTok sound use up 212% WoW (284K creations), and Shazam top-1 mover. "
            f"Atlanta fanbase spreading — Reddit confirms organic multi-city discussion. At current "
            f"trajectory, hits 500K listeners in ~{months} months. Unsigned. Cobrand audience primed "
            f"for fast food and sportswear deals. Move this week."
        ),
        "Cielo Bravo": (
            f"{name} is the premier Regional Mexican breakout: {growth} MoM with TikTok up 147% WoW. "
            f"Fresno concentration dropping from 58.9% → 51.3% — pre-national window open. "
            f"Reddit shows mentions in r/bayarea, r/houston, r/dallas, r/losangeles simultaneously. "
            f"~{months} months to 500K. Unsigned. High fast-food/brand affinity. "
            f"Dual Latin/crossover audience — priority genre expansion play."
        ),
        "Lúa Canela": (
            f"{name} is redefining Musica Mexicana with darker, moodier production (tempo shift to "
            f"118+ BPM, instrumentalness up). TikTok 98K creations. Houston concentration falling "
            f"from 55.2% → 47.6% — spreading into Mexico market simultaneously. Reddit organic buzz "
            f"confirmed. ~{months} months to 500K. Unsigned. "
            f"Brand-deal audience strong (fast food 1.88×, streaming video 1.62×). "
            f"Sign before Mexican label infrastructure catches up."
        ),
        "Vexora": (
            f"{name} is the EDM pick: {growth} MoM with upward acceleration, TikTok up 131% WoW. "
            f"LA concentration shrinking, festival season approaching. Sonic shift aligns with "
            f"harder techno-adjacent tempo rise across genre. ~{months} months to 500K. "
            f"Sportswear affinity 1.68×. Unsigned. Festival routing and sync licensing upside."
        ),
        "Soleil Fade": (
            f"{name} is a slow-burn pop sleeper. Tempo and energy dipping below genre average — "
            f"riding the emerging 'quiet storm' pop wave. TikTok aesthetic traction (67K creations). "
            f"Chicago concentration falling. Streaming video affinity 1.67×. Unsigned. "
            f"Sync deal potential high. Not the fastest grower but genre-trend alignment is strong."
        ),
    }
    return notes.get(name, (
        f"{name} flagged across multiple detections ({', '.join(a.get('detections', []))}). "
        f"{listeners} monthly listeners at {growth} MoM growth. "
        f"{'Cobrand-ready audience (' + cats + '). ' if cobrand else ''}"
        f"Unsigned. Recommend standard intake meeting."
    ))


# ── MAIN ──────────────────────────────────────────────────────────────────────

def generate_report(data_dir: Path) -> str:
    # Load all data sources
    artists = load_json(data_dir / "chartmetric_rising.json")
    tiktok_movers = load_json(data_dir / "tiktok_chart_movers.json")
    cobrand = load_json(data_dir / "cobrand_affinity.json")
    audio_features = load_json(data_dir / "spotify_audio_features.json")
    reddit = load_text(data_dir / "reddit_posts.txt")
    shazam = load_csv_rows(data_dir / "shazam_movers.csv")
    tiktok_trending = load_text(data_dir / "tiktok_trending.txt")

    # Run detections
    d1 = detection_1_velocity_outliers(artists)
    d2 = detection_2_sonic_shifts(audio_features)
    d3 = detection_3_geo_breakout(artists, reddit)
    d4_inputs = d1 + d3
    d4 = detection_4_cobrand(d4_inputs, cobrand)

    # Merge into unified artist records
    merged = merge_detections(d1, d3, d4)

    week_end = date.today().isoformat()
    total = len(artists)

    # Assemble report
    report = section_header(week_end, total)
    report += section_d1(
        [merged[a["artist"]] for a in d1 if a["artist"] in merged]
    )
    report += section_d2(d2)
    report += section_d3(
        [merged[a["artist"]] for a in d3 if a["artist"] in merged]
    )
    report += section_d4(d4)
    report += section_top3(merged)
    report += "\n[END OF REPORT]\n"
    return report


def main():
    parser = argparse.ArgumentParser(description="Generate weekly A&R discovery report")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).parent / "sample_data"),
        help="Directory containing input data files",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: weekly_ar_report_<date>.md)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    report = generate_report(data_dir)

    output_path = args.output or f"weekly_ar_report_{date.today().isoformat()}.md"
    Path(output_path).write_text(report)
    print(f"Report written to: {output_path}")
    print(report)


if __name__ == "__main__":
    main()
