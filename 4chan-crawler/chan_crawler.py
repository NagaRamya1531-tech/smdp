# from chan_client import ChanClient
# import logging
# from pyfaktory import Client, Consumer, Job, Producer
# import datetime
# import psycopg2
# import time
# from psycopg2 import pool
# from psycopg2.extras import Json
# from psycopg2.extensions import register_adapter
# from retry import retry
# import os
# import uuid
# from dotenv import load_dotenv

# # Register adapter to allow psycopg2 to insert a dict into a JSONB column
# register_adapter(dict, Json)

# # Initialize logger
# logger = logging.getLogger("4chan client")
# logger.propagate = False
# logger.setLevel(logging.INFO)
# sh = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# sh.setFormatter(formatter)
# logger.addHandler(sh)

# # Load environment variables
# load_dotenv()
# FAKTORY_SERVER_URL = os.environ.get("FAKTORY_SERVER_URL")
# DATABASE_URL = os.environ.get("DATABASE_URL")

# # Initialize a database connection pool
# try:
#     db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=DATABASE_URL)
#     if db_pool:
#         logger.info("Connection pool created successfully")
# except Exception as e:
#     logger.error(f"Error creating connection pool: {e}")

# # Generate a unique worker ID for this instance
# worker_id = f"worker-{uuid.uuid4()}"
# logger.info(f"Starting worker with ID: {worker_id}")

# def thread_numbers_from_catalog(catalog):
#     thread_numbers = []
#     for page in catalog:
#         for thread in page["threads"]:
#             thread_number = thread["no"]
#             thread_numbers.append(thread_number)
#     return thread_numbers

# def find_dead_threads(previous_catalog_thread_numbers, current_catalog_thread_numbers):
#     dead_thread_numbers = set(previous_catalog_thread_numbers).difference(set(current_catalog_thread_numbers))
#     return dead_thread_numbers

# @retry(tries=3, delay=2, backoff=2)
# def fetch_thread(board, thread_number):
#     chan_client = ChanClient()
#     thread_data = chan_client.get_thread(board, thread_number)
#     if not thread_data:
#         raise Exception(f"Failed to fetch data for thread {thread_number}")
#     return thread_data
# def crawl_thread(board, thread_number):
#     logger.info(f"Starting to crawl thread {thread_number} on board {board}")
#     try:
#         thread_data = fetch_thread(board, thread_number)
#         logger.info(f"Thread fetched: {board}/{thread_number}")

#         conn = db_pool.getconn()
#         cur = conn.cursor()

#         for post in thread_data["posts"]:
#             post_number = post["no"]
#             country = post.get("country", "")
#             country_name = post.get("country_name", "")
#             is_op = post.get("resto") == 0  # Check if it's the original post

#             # Insert into posts table
#             post_query = """
#             INSERT INTO chan_posts (board, thread_number, post_number, data, country, country_name) 
#             VALUES (%s, %s, %s, %s, %s, %s) 
#             ON CONFLICT (post_number) DO NOTHING RETURNING id
#             """
#             cur.execute(post_query, (board, thread_number, post_number, Json(post), country, country_name))
#             conn.commit()

#             result = cur.fetchone()
#             if result:
#                 db_id = result[0]
#                 logger.info(f"Inserted DB id: {db_id}")

#                 # Insert into submissions or comments based on post type
#                 if is_op:
#                     submission_query = """
#                     INSERT INTO chan_submissions (post_id, submission_number, data)
#                     VALUES (%s, %s, %s)
#                     """
#                     cur.execute(submission_query, (post_number, post_number, Json(post)))
#                 else:
#                     comment_query = """
#                     INSERT INTO chan_comments (post_id, comment_number, data)
#                     VALUES (%s, %s, %s)
#                     """
#                     cur.execute(comment_query, (post["resto"], post_number, Json(post)))

#                 conn.commit()
#             else:
#                 logger.info(f"Post {post_number} already exists in the database.")

#     except psycopg2.Error as e:
#         logger.error(f"Database error: {e}")
#     except Exception as e:
#         logger.error(f"Error crawling thread {thread_number} on board {board}: {e}")
#     finally:
#         if cur:
#             cur.close()
#         if conn:
#             db_pool.putconn(conn)

# # def crawl_thread(board, thread_number):
# #     logger.info(f"Starting to crawl thread {thread_number} on board {board}")
# #     try:
# #         thread_data = fetch_thread(board, thread_number)
# #         logger.info(f"Thread fetched: {board}/{thread_number}")

# #         conn = db_pool.getconn()
# #         cur = conn.cursor()

# #         for post in thread_data["posts"]:
# #             post_number = post["no"]
# #             country = post.get("country", "")
# #             country_name = post.get("country_name", "")
# #             q = """
# #             INSERT INTO posts (board, thread_number, post_number, data, country, country_name) 
# #             VALUES (%s, %s, %s, %s, %s, %s) 
# #             ON CONFLICT (post_number) DO NOTHING RETURNING id
# #             """
# #             cur.execute(q, (board, thread_number, post_number, Json(post), country, country_name))
# #             conn.commit()

# #             result = cur.fetchone()
# #             if result:
# #                 db_id = result[0]
# #                 logger.info(f"Inserted DB id: {db_id}")
# #             else:
# #                 logger.info(f"Post {post_number} already exists in the database.")

# #     except psycopg2.Error as e:
# #         logger.error(f"Database error: {e}")
# #     except Exception as e:
# #         logger.error(f"Error crawling thread {thread_number} on board {board}: {e}")
# #     finally:
# #         if cur:
# #             cur.close()
# #         if conn:
# #             db_pool.putconn(conn)

# @retry(tries=3, delay=2, backoff=2)
# def crawl_catalog(board, previous_catalog_thread_numbers=[]):
#     logger.info(f"Starting catalog crawl for board: {board}")
#     try:
#         chan_client = ChanClient()
#         current_catalog = chan_client.get_catalog(board)
#         if not current_catalog:
#             raise Exception(f"Failed to fetch catalog for board {board}")

#         current_catalog_thread_numbers = thread_numbers_from_catalog(current_catalog)
#         dead_threads = find_dead_threads(previous_catalog_thread_numbers, current_catalog_thread_numbers)
#         logger.info(f"Dead threads: {dead_threads}")

#         crawl_thread_jobs = []
#         with Client(faktory_url=FAKTORY_SERVER_URL, role="producer") as client:
#             producer = Producer(client=client)
#             for dead_thread in dead_threads:
#                 job = Job(jobtype="crawl-thread", args=(board, dead_thread), queue="crawl-thread")
#                 crawl_thread_jobs.append(job)
#             if crawl_thread_jobs:
#                 logger.info(f"Enqueuing {len(crawl_thread_jobs)} jobs for board: {board}")
#                 producer.push_bulk(crawl_thread_jobs)

#         # Schedule another catalog crawl in 5 minutes
#         with Client(faktory_url=FAKTORY_SERVER_URL, role="producer") as client:
#             producer = Producer(client=client)
#             run_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
#             job = Job(
#                 jobtype="crawl-catalog",
#                 args=(board, current_catalog_thread_numbers),
#                 queue="crawl-catalog",
#                 at=run_at.isoformat()[:-7] + "Z",
#             )
#             logger.info(f"Scheduled next catalog crawl for board: {board} at {run_at}")
#             producer.push(job)
#     except Exception as e:
#         logger.error(f"Error in crawl_catalog for board {board}: {e}")

# def get_boards_from_file(file_path="boards.txt"):
#     try:
#         with open(file_path, 'r') as file:
#             boards = [line.strip() for line in file if line.strip()]
#         logger.info(f"Loaded boards from file: {boards}")
#         return boards
#     except FileNotFoundError:
#         logger.error(f"File {file_path} not found. Using default boards.")
#         return ["pol", "sci", "news"]

# if __name__ == "__main__":
#     boards = get_boards_from_file()
#     with Client(faktory_url=FAKTORY_SERVER_URL, role="consumer") as client:
#         consumer = Consumer(
#             client=client, queues=["crawl-catalog", "crawl-thread"], concurrency=5
#         )
#         consumer.register("crawl-catalog", crawl_catalog)
#         consumer.register("crawl-thread", crawl_thread)

#         try:
#             for board in boards:
#                 logger.info(f"Crawling board: {board}")
#                 crawl_catalog(board)

#             consumer.run()

#         except Exception as e:
#             logger.error(f"An error occurred: {e}")
#             time.sleep(30)  # Sleep for 1 minute before retrying if an error occurs




from chan_client import ChanClient
import logging
import psycopg2
from psycopg2.extras import Json
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")

# Logger setup
logger = logging.getLogger("4chan crawler")
logger.propagate = False
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

# Initialize client
chan_client = ChanClient()

def print_db_stats():
    """Print detailed database statistics"""
    conn = psycopg2.connect(dsn=DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # Get posts statistics
        cur.execute("""
            SELECT 
                board,
                COUNT(*) as post_count,
                MIN(created_at) as earliest_post,
                MAX(created_at) as latest_post
            FROM chan_posts
            GROUP BY board
        """)
        post_stats = cur.fetchall()
        
        # Get comments statistics
        cur.execute("""
            SELECT 
    p.board,
    COUNT(c.id) AS comment_count,
    MIN(p.created_at) AS earliest_comment,
    MAX(p.created_at) AS latest_comment
FROM chan_comments c
JOIN chan_posts p ON c.post_id = p.id
GROUP BY p.board

        """)
        comment_stats = cur.fetchall()
        
        logger.info("=== Database Statistics ===")
        for board, count, earliest, latest in post_stats:
            logger.info(f"/{board}/:")
            logger.info(f"  Posts: {count} ({earliest} to {latest})")
            
        for board, count, earliest, latest in comment_stats:
            logger.info(f"  Comments in /{board}/: {count} ({earliest} to {latest})")
        logger.info("========================")
        
    finally:
        cur.close()
        conn.close()


def store_thread_data(board, thread_data):
    """Store thread data using index-based upsert"""
    if not thread_data or "posts" not in thread_data or not thread_data["posts"]:
        return False

    main_post = thread_data["posts"][0]
    thread_number = main_post["no"]
    post_time = datetime.fromtimestamp(main_post["time"], tz=timezone.utc)
    
    logger.info(f"Processing thread {thread_number} on /{board}/ from {post_time}")
    
    conn = psycopg2.connect(dsn=DATABASE_URL)
    cur = conn.cursor()
    
    try:
        # First check if post exists
        cur.execute("""
            SELECT id 
            FROM chan_posts 
            WHERE board = %s AND thread_number = %s AND post_number = %s
        """, (board, thread_number, main_post["no"]))
        
        existing_post = cur.fetchone()
        
        if existing_post:
            # Update existing post
            cur.execute("""
                UPDATE chan_posts 
                SET data = %s, 
                    last_checked = %s
                WHERE id = %s
                RETURNING id, created_at
            """, (
                Json(main_post),
                datetime.now(timezone.utc),
                existing_post[0]
            ))
            post_id, created_at = cur.fetchone()
            logger.info(f"Updated existing thread {thread_number} on /{board}/")
        else:
            # Insert new post
            cur.execute("""
                INSERT INTO chan_posts (
                    board, 
                    thread_number, 
                    post_number, 
                    data, 
                    created_at,
                    last_checked
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                board,
                thread_number,
                main_post["no"],
                Json(main_post),
                post_time,
                datetime.now(timezone.utc)
            ))
            post_id, created_at = cur.fetchone()
            logger.info(f"Inserted new thread {thread_number} on /{board}/ from {created_at}")

        # Process comments
        comments_added = 0
        comments_updated = 0
        
        for comment in thread_data["posts"][1:]:
            comment_time = datetime.fromtimestamp(comment["time"], tz=timezone.utc)
            
            # Check if comment exists
            cur.execute("""
                SELECT id 
                FROM chan_comments 
                WHERE post_id = %s AND comment_number = %s
            """, (post_id, comment["no"]))
            
            existing_comment = cur.fetchone()
            
            if existing_comment:
                # Update existing comment
                cur.execute("""
                    UPDATE chan_comments 
                    SET data = %s
                    WHERE id = %s
                """, (Json(comment), existing_comment[0]))
                if cur.rowcount > 0:
                    comments_updated += 1
            else:
                # Insert new comment
                cur.execute("""
                    INSERT INTO chan_comments (
                        post_id, 
                        comment_number, 
                        data, 
                        created_at
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    post_id,
                    comment["no"],
                    Json(comment),
                    comment_time
                ))
                comments_added += 1

        conn.commit()
        
        if comments_added > 0 or comments_updated > 0:
            logger.info(f"Thread {thread_number}: Added {comments_added} new comments, updated {comments_updated}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing thread {thread_number} on /{board}/: {str(e)}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def collect_and_store_threads(boards):
    """Collect and store all available threads"""
    logger.info("Starting collection")
    print_db_stats()
    
    for board in boards:
        threads_processed = 0
        threads_stored = 0
        
        try:
            catalog = chan_client.get_catalog(board)
            if not catalog:
                continue
                
            total_threads = sum(len(page["threads"]) for page in catalog)
            logger.info(f"Found {total_threads} threads in /{board}/")
            
            for page in catalog:
                for thread_preview in page["threads"]:
                    thread_number = thread_preview["no"]
                    threads_processed += 1
                    
                    thread_data = chan_client.get_thread(board, thread_number)
                    if thread_data and store_thread_data(board, thread_data):
                        threads_stored += 1
                            
                    if threads_processed % 10 == 0:
                        logger.info(f"/{board}/ progress: {threads_processed}/{total_threads} processed, {threads_stored} stored")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error processing board {board}: {str(e)}")
    
    logger.info("Collection completed")
    print_db_stats()
def continuous_collection(boards, delay=120):
    """Main collection function"""
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            logger.info(f"\n=== Starting Collection Cycle {cycle_count} ===")
            
            collect_and_store_threads(boards)
            
            logger.info(f"Cycle {cycle_count} completed. Waiting {delay} seconds...")
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error in cycle {cycle_count}: {str(e)}")
            time.sleep(delay)
if __name__ == "__main__":
    target_boards = ["pol", "news", "sci"]
    
    logger.info(f"Starting crawler for boards: {', '.join(target_boards)}")
    
    continuous_collection(
        boards=target_boards,
        delay=120
    )

