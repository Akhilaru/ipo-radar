"""Analyze job - read-only trend analysis from SQLite data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.analysis import (
    Freshness,
    Momentum,
    Trend,
    analyze_gmp_history,
    analyze_subscription_history,
)
from app.config import Settings
from app.database import Database

logger = logging.getLogger(__name__)


def run(settings: Settings, ipo_slug: str | None = None) -> None:
    """Run read-only trend analysis on existing data.
    
    Args:
        settings: Application settings
        ipo_slug: Optional slug to show detailed view for specific IPO
    """
    database = Database(settings.database_path)
    analysis_time = datetime.now(timezone.utc)
    
    with database.connect() as conn:
        if ipo_slug:
            _show_detailed_view(conn, ipo_slug, analysis_time)
        else:
            _show_summary_view(conn, analysis_time)


def _show_summary_view(conn, analysis_time: datetime) -> None:
    """Show summary table of all open IPOs."""
    ipos = conn.execute("""
        SELECT i.id, i.company_name, i.slug, i.ipo_type, i.status,
               i.open_date, i.close_date, i.price_low, i.price_high
        FROM ipos i
        WHERE i.status = 'open'
        ORDER BY i.company_name
    """).fetchall()
    
    if not ipos:
        print("No open IPOs found in database.")
        return
    
    print("=" * 140)
    print("IPO RADAR - TREND ANALYSIS")
    print("=" * 140)
    print(f"Analysis Time: {analysis_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Total Open IPOs: {len(ipos)}")
    print()
    
    print(f"{'IPO':<30} {'Type':<6} {'GMP':<10} {'Chg%':<8} {'Trend':<12} {'Mom':<8} {'QIB':<7} {'NII':<7} {'Ret':<7} {'Tot':<7} {'Obs':<4} {'Collect':<8} {'Source':<8}")
    print("-" * 140)
    
    for ipo in ipos:
        ipo_id = ipo["id"]
        company_name = ipo["company_name"]
        
        gmp_obs = conn.execute("""
            SELECT gmp, gmp_percentage, estimated_listing_price, source_updated_at, retrieved_at
            FROM gmp_history WHERE ipo_id = ?
            ORDER BY collection_date ASC, id ASC
        """, (ipo_id,)).fetchall()
        
        sub_obs = conn.execute("""
            SELECT qib, nii, retail, total, source_updated_at, retrieved_at
            FROM subscription_history WHERE ipo_id = ?
            ORDER BY collection_date ASC, id ASC
        """, (ipo_id,)).fetchall()
        
        gmp_analysis = analyze_gmp_history(
            ipo_id, company_name, [dict(obs) for obs in gmp_obs], analysis_time
        )
        sub_analysis = analyze_subscription_history(
            ipo_id, company_name, [dict(obs) for obs in sub_obs], analysis_time
        )
        
        _print_ipo_row(ipo, gmp_analysis, sub_analysis)
    
    print("-" * 140)
    print()
    print("LEGEND:")
    print("  Trend: ^ rising, v falling, > flat, ? insufficient data")
    print("  Mom: ^^ accelerating, vv decelerating, > steady, ? insufficient")
    print("  Collect: collection freshness from retrieved_at; Source: provider freshness from source_updated_at")
    print("  GMP: Grey Market Premium (Rs.), Chg%: % change from previous")
    print("  Subscription: Multiple of shares applied vs available (x)")
    print()
    print("NOTE: All analysis is read-only from historical observations.")
    print("      No API calls made. No data modified.")
    print()
    print("TIP: Use --ipo <slug> to see detailed history for a specific IPO.")


def _show_detailed_view(conn, ipo_slug: str, analysis_time: datetime) -> None:
    """Show detailed history for a specific IPO."""
    ipo = conn.execute(
        "SELECT * FROM ipos WHERE slug = ?", (ipo_slug,)
    ).fetchone()
    
    if not ipo:
        print(f"IPO with slug '{ipo_slug}' not found.")
        return
    
    ipo_id = ipo["id"]
    company_name = ipo["company_name"]
    
    gmp_obs = conn.execute("""
        SELECT gmp, gmp_percentage, estimated_listing_price, source_updated_at, retrieved_at
        FROM gmp_history WHERE ipo_id = ?
        ORDER BY collection_date ASC, id ASC
    """, (ipo_id,)).fetchall()
    
    sub_obs = conn.execute("""
        SELECT qib, nii, retail, total, source_updated_at, retrieved_at
        FROM subscription_history WHERE ipo_id = ?
        ORDER BY collection_date ASC, id ASC
    """, (ipo_id,)).fetchall()
    
    gmp_analysis = analyze_gmp_history(
        ipo_id, company_name, [dict(obs) for obs in gmp_obs], analysis_time
    )
    sub_analysis = analyze_subscription_history(
        ipo_id, company_name, [dict(obs) for obs in sub_obs], analysis_time
    )
    
    print("=" * 100)
    print(f"IPO DETAILS: {company_name}")
    print("=" * 100)
    print(f"Slug: {ipo['slug']}")
    print(f"Type: {ipo['ipo_type']}")
    print(f"Status: {ipo['status']}")
    print(f"Open Date: {ipo['open_date'] or 'N/A'}")
    print(f"Close Date: {ipo['close_date'] or 'N/A'}")
    print(f"Price Band: Rs.{ipo['price_low'] or 'N/A'} - Rs.{ipo['price_high'] or 'N/A'}")
    print(f"Analysis Time: {analysis_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    # GMP Analysis
    print("GMP ANALYSIS")
    print("-" * 100)
    tr = gmp_analysis.trend_result
    print(f"  Observations: {tr.observation_count}")
    print(f"  Latest GMP: Rs.{tr.latest if tr.latest is not None else 'N/A'}")
    if tr.previous is not None:
        print(f"  Previous GMP: Rs.{tr.previous}")
        if tr.percentage_change is not None:
            print(f"  Change: Rs.{tr.absolute_change:.2f} ({tr.percentage_change:.2f}%)")
        else:
            print(f"  Change: Rs.{tr.absolute_change:.2f} (N/A)")
    if tr.first is not None and tr.observation_count >= 2:
        print(f"  First GMP: Rs.{tr.first}")
        if tr.percentage_change_from_first is not None:
            print(f"  Overall Change: Rs.{tr.absolute_change_from_first:.2f} ({tr.percentage_change_from_first:.2f}%)")
        else:
            print(f"  Overall Change: Rs.{tr.absolute_change_from_first:.2f} (N/A)")
    print(f"  Latest Direction: {_format_trend(tr.latest_direction)}")
    print(f"  Overall Direction: {_format_trend(tr.overall_direction)}")
    print(f"  Momentum: {_format_momentum(tr.momentum)}")
    print(f"  Collection Freshness: {_format_freshness(gmp_analysis.collection_freshness)}")
    print(f"  Collection Retrieved: {gmp_analysis.retrieved_at or 'N/A'}")
    print(f"  Source Freshness: {_format_freshness(gmp_analysis.source_freshness)}")
    print(f"  Source Updated: {gmp_analysis.source_updated_at or 'N/A'}")
    print()
    
    # GMP History
    print("GMP HISTORY")
    print("-" * 100)
    print(f"{'Date':<25} {'GMP':<12} {'GMP%':<10} {'Est. Price':<12}")
    for obs in gmp_obs:
        print(f"{obs['source_updated_at']:<25} Rs.{obs['gmp']:<11} {obs['gmp_percentage'] or 'N/A':<10} Rs.{obs['estimated_listing_price'] or 'N/A':<12}")
    print()
    
    # Subscription Analysis
    print("SUBSCRIPTION ANALYSIS")
    print("-" * 100)
    for cat_name, cat_analysis in [("QIB", sub_analysis.qib), ("NII", sub_analysis.nii), 
                                     ("Retail", sub_analysis.retail), ("Total", sub_analysis.total)]:
        tr = cat_analysis.trend_result
        print(f"  {cat_name}:")
        if tr.latest is not None:
            print(f"    Latest: {tr.latest:.2f}x")
        else:
            print(f"    Latest: N/A")
        if tr.previous is not None:
            print(f"    Previous: {tr.previous:.2f}x")
            if tr.percentage_change is not None:
                print(f"    Change: {tr.absolute_change:.2f} ({tr.percentage_change:.2f}%)")
        print(f"    Direction: {_format_trend(tr.latest_direction)}")
        print(f"    Momentum: {_format_momentum(tr.momentum)}")
    print(f"  Collection Freshness: {_format_freshness(sub_analysis.collection_freshness)}")
    print(f"  Collection Retrieved: {sub_analysis.retrieved_at or 'N/A'}")
    print(f"  Source Freshness: {_format_freshness(sub_analysis.source_freshness)}")
    print(f"  Source Updated: {sub_analysis.source_updated_at or 'N/A'}")
    print()
    
    # Subscription History
    print("SUBSCRIPTION HISTORY")
    print("-" * 100)
    print(f"{'Date':<25} {'QIB':<10} {'NII':<10} {'Retail':<10} {'Total':<10}")
    for obs in sub_obs:
        qib = f"{obs['qib']:.2f}x" if obs['qib'] is not None else "N/A"
        nii = f"{obs['nii']:.2f}x" if obs['nii'] is not None else "N/A"
        retail = f"{obs['retail']:.2f}x" if obs['retail'] is not None else "N/A"
        total = f"{obs['total']:.2f}x" if obs['total'] is not None else "N/A"
        print(f"{obs['source_updated_at']:<25} {qib:<10} {nii:<10} {retail:<10} {total:<10}")
    print()
    
    print("NOTE: All analysis is read-only from historical observations.")
    print("      No API calls made. No data modified.")


def _print_ipo_row(ipo, gmp_analysis, sub_analysis) -> None:
    """Print a single IPO row in the summary table."""
    name = ipo["company_name"][:28] if len(ipo["company_name"]) > 28 else ipo["company_name"]
    name = f"{name:<30}"
    
    type_str = f"{ipo['ipo_type']:<6}"
    
    gmp_latest = gmp_analysis.trend_result.latest
    gmp_str = f"Rs.{gmp_latest:<9}" if gmp_latest is not None else f"{'N/A':<10}"
    
    pct = gmp_analysis.trend_result.percentage_change
    chg_str = f"{pct:>6.1f}%" if pct is not None else f"{'N/A':>7}"
    
    trend_str = f"{_format_trend(gmp_analysis.trend_result.latest_direction):<12}"
    mom_str = f"{_format_momentum_short(gmp_analysis.trend_result.momentum):<8}"
    
    def format_sub(cat_analysis):
        latest = cat_analysis.trend_result.latest
        return f"{latest:<6.1f}x" if latest is not None else f"{'N/A':<7}"
    
    qib_str = format_sub(sub_analysis.qib)
    nii_str = format_sub(sub_analysis.nii)
    retail_str = format_sub(sub_analysis.retail)
    total_str = format_sub(sub_analysis.total)
    
    obs_str = f"{gmp_analysis.trend_result.observation_count:<4}"
    fresh_str = f"{_format_freshness_short(gmp_analysis.collection_freshness):<6}"
    source_str = f"{_format_freshness_short(gmp_analysis.source_freshness):<6}"
    
    print(f"{name} {type_str} {gmp_str} {chg_str} {trend_str} {mom_str} {qib_str} {nii_str} {retail_str} {total_str} {obs_str} {fresh_str} {source_str}")


def _format_trend(trend) -> str:
    """Format trend for display."""
    if trend == Trend.RISING:
        return "^ rising"
    elif trend == Trend.FALLING:
        return "v falling"
    elif trend == Trend.FLAT:
        return "> flat"
    else:
        return "? insuff."


def _format_momentum(momentum) -> str:
    """Format momentum for display."""
    if momentum == Momentum.ACCELERATING:
        return "^^ accelerating"
    elif momentum == Momentum.DECELERATING:
        return "vv decelerating"
    elif momentum == Momentum.STEADY:
        return "> steady"
    else:
        return "? insufficient data"


def _format_momentum_short(momentum) -> str:
    """Format momentum for compact display."""
    if momentum == Momentum.ACCELERATING:
        return "^^ acc."
    elif momentum == Momentum.DECELERATING:
        return "vv dec."
    elif momentum == Momentum.STEADY:
        return "> stdy"
    else:
        return "? insuff"


def _format_freshness(freshness) -> str:
    """Format freshness for display."""
    if freshness == Freshness.FRESH:
        return "* fresh (<6h)"
    elif freshness == Freshness.AGING:
        return "o aging (6-24h)"
    else:
        return "x stale (>24h)"


def _format_freshness_short(freshness) -> str:
    """Format freshness for compact display."""
    if freshness == Freshness.FRESH:
        return "* fresh"
    elif freshness == Freshness.AGING:
        return "o aging"
    else:
        return "x stale"



