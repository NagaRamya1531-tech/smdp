from dotenv import load_dotenv
import os
import psycopg2
from psycopg2.extras import Json

# Load environment variables from .env file
load_dotenv()

# Fetch the DATABASE_URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Sample data to insert
sample_data = {
    "board": "pol",
    "thread_number": 123456,
    "post_number": 7891011,
    "data": {"content": "Sample post content"},
    "country": "US",
    "country_name": "United States"
}

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Insert sample data into the posts table
    insert_query = """
    INSERT INTO posts (board, thread_number, post_number, data, country, country_name)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (post_number) DO NOTHING RETURNING id;
    """

    cur.execute(insert_query, (
        sample_data["board"],
        sample_data["thread_number"],
        sample_data["post_number"],
        Json(sample_data["data"]),
        sample_data["country"],
        sample_data["country_name"]
    ))

    # Commit transaction and retrieve result
    conn.commit()
    result = cur.fetchone()
    if result:
        print("Sample data inserted successfully. DB ID:", result[0])
    else:
        print("Post already exists in the database.")

except psycopg2.Error as e:
    print("Database error code:", e.pgcode)
    print("Database error message:", e.pgerror)
    print("Details:", e)

finally:
    # Close the cursor and connection
    if 'cur' in locals() and cur is not None:
        cur.close()
    if 'conn' in locals() and conn is not None:
        conn.close()
print("DATABASE_URL:", DATABASE_URL)
