import logging
from pyfaktory import Client, Job, Producer
import sys

logger = logging.getLogger("reddit cold start")
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

if __name__ == "__main__":
    subreddit = sys.argv[1]
    print(f"Cold starting crawl for subreddit: {subreddit}")

    faktory_server_url = "tcp://:password@localhost:7419"

    with Client(faktory_url=faktory_server_url, role="producer") as client:
        producer = Producer(client=client)
        job = Job(jobtype="crawl-subreddit", args=(subreddit,), queue="crawl-subreddit")
        producer.push(job)
