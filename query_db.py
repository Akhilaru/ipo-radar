import sqlite3
conn = sqlite3.connect("data/ipo_radar.db")
conn.row_factory = sqlite3.Row

print("=== IPO Guru API Usage ===")
row = conn.execute("SELECT * FROM api_usage WHERE provider='ipoguru'").fetchone()
if row:
    print(f"  requests used: {row['request_count']}/10")
    print(f"  last request at: {row['last_request_at']}")

print()
print("=== IPOs in database ===")
ipos = conn.execute("SELECT * FROM ipos ORDER BY id").fetchall()
print(f"  total IPOs: {len(ipos)}")

print()
print("=== GMP observations ===")
gmp_count = conn.execute("SELECT COUNT(*) FROM gmp_history").fetchone()[0]
print(f"  total GMP observations: {gmp_count}")

print()
print("=== Subscription observations ===")
sub_count = conn.execute("SELECT COUNT(*) FROM subscription_history").fetchone()[0]
print(f"  total subscription observations: {sub_count}")

print()
print("=== Duplicate check ===")
dup_gmp = conn.execute(
    "SELECT ipo_id, source, source_updated_at, COUNT(*) as cnt "
    "FROM gmp_history GROUP BY ipo_id, source, source_updated_at HAVING cnt > 1"
).fetchall()
dup_sub = conn.execute(
    "SELECT ipo_id, source, source_updated_at, COUNT(*) as cnt "
    "FROM subscription_history GROUP BY ipo_id, source, source_updated_at HAVING cnt > 1"
).fetchall()
print(f"  duplicate GMP rows: {len(dup_gmp)}")
print(f"  duplicate subscription rows: {len(dup_sub)}")

print()
print("=== Sample IPOs (first 3) ===")
for ipo in ipos[:3]:
    print(f"  Name: {ipo['company_name']}")
    print(f"  Slug: {ipo['slug']}")
    print(f"  Status: {ipo['status']}")
    print(f"  Type: {ipo['ipo_type']}")
    print(f"  Price: {ipo['price_low']} - {ipo['price_high']}")

    gmp = conn.execute(
        "SELECT * FROM gmp_history WHERE ipo_id=? ORDER BY id DESC LIMIT 1",
        (ipo["id"],),
    ).fetchone()
    if gmp:
        print(f"  GMP: Rs.{gmp['gmp']} ({gmp['gmp_percentage']}%)")
        print(f"  Est. Listing: Rs.{gmp['estimated_listing_price']}")
        print(f"  GMP updated: {gmp['source_updated_at']}")

    sub = conn.execute(
        "SELECT * FROM subscription_history WHERE ipo_id=? ORDER BY id DESC LIMIT 1",
        (ipo["id"],),
    ).fetchone()
    if sub:
        print(f"  Subscription - QIB: {sub['qib']}, NII: {sub['nii']}, Retail: {sub['retail']}, Total: {sub['total']}")
        print(f"  Sub updated: {sub['source_updated_at']}")
    print()

conn.close()
