from reddit_client import RedditClient
import logging
import psycopg2
from psycopg2.extras import Json, execute_values
from datetime import datetime, timezone
import time
import os
from requests.exceptions import HTTPError
from dotenv import load_dotenv
from psycopg2 import pool

# Logger setup
logger = logging.getLogger("reddit_crawler")
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL)

# Initialize Reddit client
reddit_client = RedditClient()


def get_connection_from_pool():
    """Fetch a connection from the pool."""
    try:
        return connection_pool.getconn()
    except Exception as e:
        logger.error(f"Error getting connection from pool: {e}")
        raise


def release_connection(conn):
    """Release a connection back to the pool."""
    if conn:
        connection_pool.putconn(conn)


def fetch_with_backoff(reddit_client_func, *args, **kwargs):
    """Fetch data with backoff strategy in case of rate limiting."""
    backoff_time = 1  # Start with 1 second backoff
    max_backoff = 60  # Cap the backoff at 60 seconds

    while True:
        try:
            return reddit_client_func(*args, **kwargs)
        except HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limit hit. Backing off for {backoff_time} seconds...")
                time.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, max_backoff)  # Exponential backoff
            else:
                logger.error(f"HTTP Error: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break


def execute_with_retry(query, params=None, retries=3):
    """Execute a database query with retry logic."""
    conn = get_connection_from_pool()
    for attempt in range(retries):
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.fetchall() if cur.description else None
        except psycopg2.OperationalError as e:
            logger.error(f"Database error on attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                conn = get_connection_from_pool()  # Reconnect
            else:
                raise
        finally:
            cur.close()
            release_connection(conn)


# Database operations
def get_last_crawled_time(subreddit):
    query = "SELECT last_crawled_utc FROM reddit_crawling_state WHERE subreddit = %s"
    result = execute_with_retry(query, (subreddit,))
    return result[0][0] if result else None


def update_last_crawled_time(subreddit, last_crawled_utc):
    query = """
        INSERT INTO reddit_crawling_state (subreddit, last_crawled_utc)
        VALUES (%s, %s)
        ON CONFLICT (subreddit) DO UPDATE SET last_crawled_utc = EXCLUDED.last_crawled_utc
    """
    execute_with_retry(query, (subreddit, last_crawled_utc))


def create_placeholder_post(post_id, subreddit):
    """Create a placeholder post if the post ID does not exist."""
    placeholder_data = (
        post_id, "[Placeholder Title]", "[Unknown]", datetime.now(timezone.utc), "",
        0, subreddit, datetime.now()
    )
    query = """
        INSERT INTO reddit_crawler_posts (post_id, title, author, created_utc, content, score, subreddit, last_checked)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (post_id) DO NOTHING;
    """
    execute_with_retry(query, placeholder_data)
    logger.info(f"Created placeholder post for post_id: {post_id}")


def insert_reddit_posts(posts, subreddit):
    """Insert posts into the database."""
    conn = get_connection_from_pool()
    try:
        cur = conn.cursor()
        newest_created_utc = None
        post_values = []

        for post in posts:
            post_data = {
                "id": post["data"]["id"],
                "title": post["data"].get("title", "[No Title]"),
                "author": post["data"].get("author", "[Unknown]"),
                "created_utc": datetime.fromtimestamp(post["data"]["created_utc"], tz=timezone.utc),
                "selftext": post["data"].get("selftext", ""),
                "score": post["data"].get("score", 0),
                "subreddit": subreddit
            }
            post_values.append((
                post_data["id"], post_data["title"], post_data["author"], post_data["created_utc"],
                post_data["selftext"], post_data["score"], post_data["subreddit"], datetime.now()
            ))
            if not newest_created_utc or post_data["created_utc"] > newest_created_utc:
                newest_created_utc = post_data["created_utc"]

        query = """
            INSERT INTO reddit_crawler_posts (post_id, title, author, created_utc, content, score, subreddit, last_checked)
            VALUES %s
            ON CONFLICT (post_id) DO NOTHING
        """
        execute_values(cur, query, post_values)
        conn.commit()
        logger.info(f"Inserted {len(post_values)} posts for subreddit {subreddit}")
        return newest_created_utc
    except Exception as e:
        logger.error(f"Error inserting posts: {e}")
        conn.rollback()
    finally:
        cur.close()
        release_connection(conn)


def batch_insert_reddit_comments(comments, post_id, subreddit):
    """Insert comments into the database."""
    conn = get_connection_from_pool()
    try:
        cur = conn.cursor()

        # Ensure post exists
        query = "SELECT 1 FROM reddit_crawler_posts WHERE post_id = %s"
        post_exists = execute_with_retry(query, (post_id,))
        if not post_exists:
            logger.warning(f"Post ID {post_id} not found. Creating placeholder...")
            create_placeholder_post(post_id, subreddit)

        # Insert comments
        comment_values = []
        for comment in comments:
            if "data" not in comment or "created_utc" not in comment["data"]:
                logger.warning(f"Skipping comment due to missing 'created_utc'")
                continue

            created_utc = datetime.fromtimestamp(comment["data"]["created_utc"], tz=timezone.utc)
            comment_data = {
                "id": comment["data"]["id"],
                "post_id": post_id,
                "author": comment["data"].get("author", "[Unknown]"),
                "created_utc": created_utc,
                "content": comment["data"].get("body"),
                "score": comment["data"].get("score")
            }
            comment_values.append((
                comment_data["id"], comment_data["post_id"], comment_data["author"],
                comment_data["created_utc"], comment_data["content"], comment_data["score"]
            ))

        query = """
            INSERT INTO reddit_crawler_comments (comment_id, post_id, author, created_utc, content, score)
            VALUES %s
            ON CONFLICT (comment_id) DO NOTHING
        """
        execute_values(cur, query, comment_values)
        conn.commit()
        logger.info(f"Inserted {len(comment_values)} comments for post ID {post_id}")
    except Exception as e:
        logger.error(f"Error inserting comments: {e}")
        conn.rollback()
    finally:
        cur.close()
        release_connection(conn)


def crawl_reddit(subreddits, limit=100, delay=120, comment_update_interval=3600):
    """Main function to crawl posts and periodically update comments on old posts."""
    last_comment_update = time.time()
    while True:
        for subreddit in subreddits:
            logger.info(f"Fetching new posts from subreddit: {subreddit}")
            posts_data = fetch_with_backoff(reddit_client.fetch_subreddit_posts, subreddit, limit=limit)

            if posts_data:
                new_last_crawled_utc = insert_reddit_posts(posts_data["data"]["children"], subreddit)
                if new_last_crawled_utc:
                    update_last_crawled_time(subreddit, new_last_crawled_utc)
                for post in posts_data["data"]["children"]:
                    post_id = post["data"]["id"]
                    comments_data = fetch_with_backoff(reddit_client.fetch_post_comments, post_id)
                    if comments_data:
                        batch_insert_reddit_comments(comments_data[1]["data"]["children"], post_id, subreddit)

        if time.time() - last_comment_update > comment_update_interval:
            logger.info("Updating comments on old posts...")
            # Add logic to update old posts
            last_comment_update = time.time()

        logger.info(f"Waiting for {delay} seconds before the next fetch cycle...")
        time.sleep(delay)


if __name__ == "__main__":
    subreddits_to_monitor = [
        "immigration", "AskImmigration", "immigrationlaw", "asylum", "refugees",
        "PoliticalDiscussion", "WorldNews", "news", "WorldPolitics", "GlobalTalk",
        "ChapoTrapHouse", "Conservative", "liberal", "anarchism", "SocialJusticeInAction",
        "AskEconomics", "economics", "jobs", "AntiWork", "LateStageCapitalism",
        "America", "Canada", "europe", "MiddleEast", "AsianAmerican",
        "travel", "IWantOut", "worldnews", "news", "politics",
        "legaladviceuk", "AmericanPolitics", "CanadaPolitics",
        "ImmigrationLawyers", "ExpatFinance", "solotravel",
        "expatriates", "migrationpolicy", "internationalrelations",
        "AskAnAmerican", "UnitedKingdom", "VisaConsultants",
        "PoliticalDiscussion", "AustraliaVisa", "ImmigrationDebate"
    ]
    crawl_reddit(subreddits=subreddits_to_monitor, limit=100, delay=120, comment_update_interval=3600)
