import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="ai_rep_optimizer",
    user="postgres",
    password="YOURPASSWORD"
)

print("Database connected successfully!")

conn.close()