import psycopg2

conn = psycopg2.connect("host=127.0.0.1 port=5433 dbname=tenniscapital user=bot password=bot")
cur = conn.cursor()
cur.execute("select 1;")
print(cur.fetchone())
conn.close()