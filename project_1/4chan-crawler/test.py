import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    post_data = {
        "no": 12345,
        "content": "Test post data",
        "country": "US",
        "country_name": "United States"
    }

    query = """
    INSERT INTO posts (board, thread_number, post_number, data, country, country_name)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (post_number) DO NOTHING RETURNING id;
    """
    cur.execute(query, ("pol", 67890, post_data["no"], Json(post_data), post_data["country"], post_data["country_name"]))
    conn.commit()

    result = cur.fetchone()
    if result:
        print(f"Data inserted successfully with ID: {result[0]}")
    else:
        print("Data already exists, no new record inserted.")

    cur.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
