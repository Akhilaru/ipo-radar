"""Analyze job - read-only trend analysis from SQLite data."""

from __future__ import annotations

import logging
from datetime import datetime

from app.analysis import (
    Trend,
    analyze_gmp_history,
    analyze_subscription_history,
)
from app.config import Settings
from app.database import Database

logger = logging.getLogger(__name__)


def run(settings: Settings) -> None:
    """Run read-only trend analysis on existing data."""
    database = Database(settings.database_path)
    
    with database.connect() as conn:
        # Get all IPOs with their latest data
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
        
        print("=" * 100)
        print("IPO RADAR - TREND ANALYSIS")
        print("=" * 100)
        print(f"Analysis Time: {datetime.now(settings.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Total Open IPOs: {len(ipos)}")
        print()
        
        # Table header
        print(f"{'IPO':<35} {'GMP':<12} {'Trend':<18} {'QIB':<8} {'NII':<8} {'Retail':<8} {'Total':<8}")
        print("-" * 100)
        
        for ipo in ipos:
            ipo_id = ipo["id"]
            company_name = ipo["company_name"]
            
            # Get GMP observations
            gmp_obs = conn.execute("""
                SELECT gmp, gmp_percentage, estimated_listing_price, source_updated_at
                FROM gmp_history
                WHERE ipo_id = ?
                ORDER BY source_updated_at ASC, id ASC
            """, (ipo_id,)).fetchall()
            
            # Get subscription observations
            sub_obs = conn.execute("""
                SELECT qib, nii, retail, total, source_updated_at
                FROM subscription_history
                WHERE ipo_id = ?
                ORDER BY source_updated_at ASC, id ASC
            """, (ipo_id,)).fetchall()
            
            # Analyze
            gmp_analysis = analyze_gmp_history(
                ipo_id, company_name, [dict(obs) for obs in gmp_obs]
            )
            sub_analysis = analyze_subscription_history(
                ipo_id, company_name, [dict(obs) for obs in sub_obs]
            )
            
            # Format output
            _print_ipo_row(ipo, gmp_analysis, sub_analysis)
        
        print("-" * 100)
        print()
        
        # Summary
        print("LEGEND:")
        print("  Trend: ↑ rising, ↓ falling, → flat, ? insufficient data")
        print("  GMP: Grey Market Premium (₹)")
        print("  Subscription: Multiple of shares applied vs available (x)")
        print()
        print("NOTE: All analysis is read-only from historical observations.")
        print("      No API calls made. No data modified.")


def _print_ipo_row(ipo, gmp_analysis, sub_analysis) -> None:
    """Print a single IPO row in the analysis table."""
    # Company name (truncate if needed)
    name = ipo["company_name"][:33] if len(ipo["company_name"]) > 33 else ipo["company_name"]
    name = f"{name:<35}"
    
    # GMP
    gmp_latest = gmp_analysis.trend_result.latest
    if gmp_latest is not None:
        gmp_str = f"₹{gmp_latest:<11}"
    else:
        gmp_str = f"{'N/A':<12}"
    
    # Trend
    trend = gmp_analysis.trend_result.trend
    if trend == Trend.RISING:
        trend_str = "↑ rising"
    elif trend == Trend.FALLING:
        trend_str = "↓ falling"
    elif trend == Trend.FLAT:
        trend_str = "→ flat"
    else:
        trend_str = "? insufficient"
    trend_str = f"{trend_str:<18}"
    
    # Subscription categories
    def format_sub(cat_analysis):
        latest = cat_analysis.trend_result.latest
        if latest is not None:
            return f"{latest:<8.2f}"
        return f"{'N/A':<8}"
    
    qib_str = format_sub(sub_analysis.qib)
    nii_str = format_sub(sub_analysis.nii)
    retail_str = format_sub(sub_analysis.retail)
    total_str = format_sub(sub_analysis.total)
    
    print(f"{name} {gmp_str} {trend_str} {qib_str} {nii_str} {retail_str} {total_str}")
