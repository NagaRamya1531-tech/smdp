import requests
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# Logger setup
logger = logging.getLogger("reddit_client")
logger.setLevel(logging.INFO)
sh = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)
logger.addHandler(sh)

class RedditClient:
    def __init__(self):
        self.token = None
        self.authenticate()

    def authenticate(self):
        """Authenticate with Reddit API and retrieve access token."""
        auth = requests.auth.HTTPBasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
        data = {
            "grant_type": "password",
            "username": REDDIT_USERNAME,
            "password": REDDIT_PASSWORD
        }
        headers = {"User-Agent": REDDIT_USER_AGENT}

        try:
            res = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers)
            res.raise_for_status()
            self.token = res.json().get("access_token")
            logger.info("Authenticated with Reddit API")
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            raise

    def get_headers(self):
        """Return the authorization headers with the access token."""
        if not self.token:
            self.authenticate()
        return {"Authorization": f"bearer {self.token}", "User-Agent": REDDIT_USER_AGENT}

    def fetch_subreddit_posts(self, subreddit, limit=10):
        """Fetch latest posts from a subreddit."""
        headers = self.get_headers()
        url = f"https://oauth.reddit.com/r/{subreddit}/new?limit={limit}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            logger.info(f"Fetched {limit} posts from subreddit: {subreddit}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch posts from {subreddit}: {e}")
            self.authenticate()  # Re-authenticate if token is expired
            return None

    def fetch_post_comments(self, post_id):
        """Fetch comments for a specific post."""
        headers = self.get_headers()
        url = f"https://oauth.reddit.com/comments/{post_id}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            logger.info(f"Fetched comments for post ID: {post_id}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch comments for post {post_id}: {e}")
            self.authenticate()  # Re-authenticate if token is expired
            return None
