"""
A&R Discovery Detection Algorithms
Detections 1–4 as specified in the weekly scout report spec.
"""

from __future__ import annotations
import statistics
from typing import Any


# ── DETECTION 1: VELOCITY OUTLIERS ────────────────────────────────────────────

def detection_1_velocity_outliers(artists: list[dict]) -> list[dict]:
    """
    Flag artists where:
      - MoM growth > 2× genre median AND
      - Growth is accelerating (current rate > prior month rate)
    Adds months_to_500k and signed_status fields.
    """
    results = []
    for a in artists:
        # Use the pre-computed Chartmetric genre-wide median growth rate
        median = a.get("genre_median_growth", 0.01)
        is_2x = a["mom_growth_rate_current"] > 2 * median
        is_accel = a["mom_growth_rate_current"] > a["mom_growth_rate_prior"]
        if is_2x and is_accel:
            listeners = a["spotify_monthly_listeners"]
            growth = a["mom_growth_rate_current"]
            # Compound growth: months until 500K
            if growth > 0 and listeners < 500_000:
                months = 0
                current = listeners
                while current < 500_000 and months < 120:
                    current *= (1 + growth)
                    months += 1
                months_to_500k = months
            else:
                months_to_500k = 0

            signed_status = (
                f"already signed — monitor ({a['label']})"
                if a.get("label") else "available"
            )
            results.append({
                **a,
                "genre_median_growth": median,
                "months_to_500k": months_to_500k,
                "signed_status": signed_status,
                "detections": ["D1"],
            })
    return results


# ── DETECTION 2: SONIC TREND SHIFTS ───────────────────────────────────────────

def detection_2_sonic_shifts(features_data: dict) -> list[dict]:
    """
    Compare last-4-week new releases against 12-month genre averages.
    Flag features that have shifted >10% from the long-run average.
    """
    averages = features_data["genre_12mo_averages"]
    releases = features_data["top_20_new_releases_last_4wk"]

    # Group releases by genre
    by_genre: dict[str, list[dict]] = {}
    for r in releases:
        by_genre.setdefault(r["genre"], []).append(r)

    metrics = ["tempo", "energy", "danceability", "valence", "acousticness", "instrumentalness"]
    shifts = []

    for genre, tracks in by_genre.items():
        if genre not in averages:
            continue
        baseline = averages[genre]
        for metric in metrics:
            recent_avg = statistics.mean(t[metric] for t in tracks)
            base_val = baseline[metric]
            if base_val == 0:
                continue
            delta_pct = (recent_avg - base_val) / base_val * 100
            if abs(delta_pct) >= 10:
                direction = "UP" if delta_pct > 0 else "DOWN"
                shifts.append({
                    "genre": genre,
                    "metric": metric,
                    "baseline_12mo": round(base_val, 3),
                    "recent_4wk": round(recent_avg, 3),
                    "delta_pct": round(delta_pct, 1),
                    "direction": direction,
                    "detections": ["D2"],
                })
    return shifts


# ── DETECTION 3: GEOGRAPHIC BREAKOUT SIGNALS ──────────────────────────────────

def detection_3_geo_breakout(artists: list[dict], reddit_text: str) -> list[dict]:
    """
    Flag artists where:
      - >40% listeners in single city AND
      - That concentration decreased >5pp in last 60 days (spreading nationally)
    Cross-reference Reddit for geographic mention corroboration.
    """
    results = []
    for a in artists:
        pct_now = a.get("city_top_pct", 0)
        pct_60d = a.get("city_top_pct_60d_ago", 0)
        if pct_now > 40 and (pct_60d - pct_now) > 5:
            # Check Reddit cross-mentions
            name_lower = a["artist"].lower().replace("ú", "u").replace("é", "e")
            reddit_mentions = reddit_text.lower().count(name_lower)
            # Look for geographic subreddit signals
            geo_subreddits = ["r/bayarea", "r/houston", "r/dallas", "r/losangeles",
                              "r/chicago", "r/newyork", "r/nashville", "r/atlanta",
                              "r/portland", "r/austin"]
            geo_confirmed = any(s in reddit_text.lower() for s in geo_subreddits)
            signed_status = (
                f"already signed — monitor ({a['label']})"
                if a.get("label") else "available"
            )
            results.append({
                **a,
                "geo_concentration_now": pct_now,
                "geo_concentration_60d_ago": pct_60d,
                "geo_spread_delta": round(pct_60d - pct_now, 1),
                "reddit_mentions": reddit_mentions,
                "reddit_geo_confirmed": geo_confirmed,
                "signed_status": signed_status,
                "detections": ["D3"],
            })
    return results


# ── DETECTION 4: COBRAND CROSSOVER SIGNAL ─────────────────────────────────────

MAINSTREAM_BRAND_CATEGORIES = ["fast_food", "streaming_video", "major_sportswear"]
COBRAND_THRESHOLD = 1.5


def detection_4_cobrand(flagged_artists: list[dict], affinity_data: dict) -> list[dict]:
    """
    For each artist already flagged in D1–D3, check if any mainstream brand
    category scores >1.5× affinity index.
    """
    results = []
    seen = set()
    for a in flagged_artists:
        name = a["artist"]
        if name in seen:
            continue
        seen.add(name)
        aff = affinity_data.get(name, {})
        triggered_cats = [
            cat for cat in MAINSTREAM_BRAND_CATEGORIES
            if aff.get(cat, 0) > COBRAND_THRESHOLD
        ]
        if triggered_cats:
            results.append({
                "artist": name,
                "triggered_categories": triggered_cats,
                "affinity_scores": {cat: aff.get(cat, 0) for cat in triggered_cats},
                "detections": ["D4"],
            })
    return results


# ── MERGE & ANNOTATE ───────────────────────────────────────────────────────────

def merge_detections(
    d1: list[dict],
    d3: list[dict],
    d4: list[dict],
) -> dict[str, dict]:
    """
    Merge Detection 1, 3, 4 results into a unified artist-keyed dict.
    D2 is sonic-level, handled separately in the report.
    """
    merged: dict[str, dict] = {}

    for entry in d1:
        name = entry["artist"]
        merged[name] = {**entry}

    for entry in d3:
        name = entry["artist"]
        if name in merged:
            merged[name]["detections"] = sorted(
                set(merged[name].get("detections", []) + entry.get("detections", []))
            )
            merged[name].update({k: v for k, v in entry.items() if k not in merged[name]})
        else:
            merged[name] = {**entry}

    cobrand_names = {e["artist"] for e in d4}
    for name in merged:
        merged[name]["cobrand_flag"] = name in cobrand_names
        if name in cobrand_names:
            d4_entry = next(e for e in d4 if e["artist"] == name)
            merged[name]["cobrand_categories"] = d4_entry["triggered_categories"]
            merged[name]["cobrand_scores"] = d4_entry["affinity_scores"]
            merged[name]["detections"] = sorted(
                set(merged[name].get("detections", []) + ["D4"])
            )

    return merged
