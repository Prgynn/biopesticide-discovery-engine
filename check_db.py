import sqlite3

conn = sqlite3.connect('biopesticide.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()

print('Tables:')
for t in tables:
    name = t[0]
    try:
        c.execute(f'SELECT COUNT(*) FROM "{name}"')
        count = c.fetchone()[0]
        print(f'  {name}: {count} rows')
    except:
        print(f'  {name}: (virtual table)')

conn.close()
