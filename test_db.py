import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host='db',
        port='5432',
        dbname='trackingmap',
        user='trackingmap',
        password='trackingmap123'
    )
    print('✓ Connected to PostgreSQL!')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cursor.fetchall()
    print(f'✓ Tables found: {len(tables)}')
    for t in tables:
        print(f'  - {t[0]}')
    
    # Check tracker_data rows
    cursor.execute("SELECT COUNT(*) FROM tracker_data")
    count = cursor.fetchone()[0]
    print(f'✓ Rows in tracker_data: {count}')
    
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'✗ Error: {type(e).__name__}: {e}')
    sys.exit(1)
