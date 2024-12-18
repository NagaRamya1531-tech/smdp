import logging
from pyfaktory import Client, Consumer, Job, Producer
import time
import random
import requests

logger = logging.getLogger("reddit-faktory-test")
logger.propagate = False
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

def reddit_crawler(subreddit_name, post_limit=10):
    """
    Function to fetch posts from a subreddit and log the data.
    """
    try:
        url = f"https://www.reddit.com/r/{subreddit_name}/new.json?limit={post_limit}"
        headers = {"User-Agent": "python:reddit-crawler:v1.0 (by /u/your_username)"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Check for errors in the request
        
        posts = response.json()["data"]["children"]
        for post in posts:
            logger.info(f"Post Title: {post['data']['title']}, Score: {post['data']['score']}")
        
        # Simulate some processing delay to mimic a real workload
        sleep_for = random.randint(0, 10)
        time.sleep(sleep_for)
        logger.info(f"Finished processing subreddit: {subreddit_name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from subreddit {subreddit_name}: {e}")

if __name__ == "__main__":
    # Default url for a Faktory server running locally
    faktory_server_url = "tcp://:password@localhost:7419"

    with Client(faktory_url=faktory_server_url, role="producer") as client:
        producer = Producer(client=client)

        # List of subreddits to crawl
        subreddits = ["python", "datascience", "machinelearning"]
        
        # Generate jobs for each subreddit crawl
        jobs = []
        for subreddit in subreddits:
            job = Job(jobtype="reddit_crawl", args=(subreddit, 10), queue="default")
            jobs.append(job)

        producer.push_bulk(jobs)

    print("Starting consumer")

    # Consumer listens for 'reddit_crawl' jobs
    with Client(faktory_url=faktory_server_url, role="consumer") as client:
        consumer = Consumer(client=client, queues=["default"], concurrency=3)
        consumer.register("reddit_crawl", reddit_crawler)
        consumer.run()
