Here's a more detailed and clear README for your project:

```markdown
# Data Collection System for Reddit and 4chan

## Overview
This project is designed to continuously collect data from **Reddit** and **4chan**. The system dynamically tracks posts and comments, storing them in a PostgreSQL database for further analysis.

---

## Key Features
- **Reddit Crawler**: Collects posts and comments from dynamically selected subreddits.
- **4chan Crawler**: Continuously fetches threads and comments from selected boards.
- **Dynamic Configuration**: Easily update the list of subreddits or 4chan boards without changing the code.
- **Rate Limit Handling**: Implements retries and backoff strategies to handle API rate limits gracefully.
- **Database Storage**: Data is stored in a PostgreSQL database for easy querying and analysis.

---

## Prerequisites
Before you begin, ensure you have the following installed:
1. **Python**: Version 3.8 or later.
2. **PostgreSQL**: For storing collected data.
3. **Git**: To clone the repository.
4. **Faktory**: Task queue system (required for the 4chan crawler).

---

## Installation and Setup

### 1. Clone the Repository
Start by cloning the project repository:
```bash
git clone https://github.com/your-username/data-collection-system.git
cd data-collection-system
```

### 2. Create a Python Environment
Set up a virtual environment to isolate dependencies:
```bash
python -m venv env
source env/bin/activate  # Linux/Mac
env\Scripts\activate     # Windows
```

### 3. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

---

## Configuration

### 1. Set Environment Variables
Create a `.env` file in the root directory of the project and populate it with the following variables:
```plaintext
DATABASE_URL=postgres://<username>:<password>@<host>:<port>/<database>
FAKTORY_SERVER_URL=tcp://<password>@<host>:<port>  # For 4chan crawler
REDDIT_CLIENT_ID=<your_reddit_client_id>
REDDIT_CLIENT_SECRET=<your_reddit_client_secret>
REDDIT_USER_AGENT=<your_reddit_user_agent>
```
- Replace `<username>`, `<password>`, `<host>`, `<port>`, and `<database>` with your PostgreSQL details.
- Use your Reddit API credentials for `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`.

### 2. Prepare the Database
Set up your PostgreSQL database and create the required tables. Ensure the database schema matches the structure defined for the crawlers.

---

## Running the Crawlers

### 1. Reddit Crawler
Edit the list of subreddits in the `reddit_crawler.py` script or configuration. Then, run the crawler:
```bash
python reddit_crawler.py
```

### 2. 4chan Crawler
Create a `boards.txt` file in the root directory of the project and add the boards to monitor, one per line:
```plaintext
pol
sci
news
```

Run the 4chan crawler:
```bash
python chan_crawler.py
```

---

## Monitoring and Logs
- Both crawlers log their activity to the console, including successful operations, errors, and retry attempts.
- Logs provide timestamps and detailed messages to help troubleshoot issues.

---

## Database Schema

### Reddit Tables
- **`reddit_crawler_posts`**
  - Stores Reddit post metadata and content.
  - Example columns: `post_id`, `title`, `author`, `created_utc`, `content`, `score`, `subreddit`, `last_checked`.
- **`reddit_crawler_comments`**
  - Stores Reddit comments linked to posts.
  - Example columns: `comment_id`, `post_id`, `author`, `created_utc`, `content`, `score`.
- **`reddit_crawling_state`**
  - Tracks the last crawled post for each subreddit.

### 4chan Tables
- **`chan_posts`**
  - Stores 4chan post metadata and content.
  - Example columns: `board`, `thread_number`, `post_number`, `data`, `country`, `country_name`.
- **`chan_comments`**
  - Stores comments linked to 4chan posts.
  - Example columns: `post_id`, `comment_number`, `data`.
- **`chan_submissions`**
  - Stores original posts (OP) for threads.
  - Example columns: `post_id`, `submission_number`, `data`.

---

## Notes
1. **Dynamic Configuration**:
   - Subreddits and 4chan boards can be updated without modifying the code.
2. **Rate Limiting**:
   - The Reddit crawler handles rate limits using exponential backoff to avoid API bans.
3. **Crawling Frameworks**:
   - Avoid using frameworks like Scrapy; unauthorized libraries will result in a zero for implementation.

---

## Troubleshooting
- **Database Connection Issues**: Check the `DATABASE_URL` in your `.env` file.
- **API Errors**: Ensure your Reddit API credentials are correct and active.
- **Missing Logs**: Verify that the logger setup in the script is configured correctly.

---

## License
This project is licensed under the MIT License.
```

This version includes detailed, beginner-friendly instructions for downloading, configuring, and running the crawlers. Let me know if there’s anything else you’d like to add!
