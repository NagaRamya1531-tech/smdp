# Project Title: Reddit and 4chan Data Analysis

This project uses data from Reddit and 4chan to analyze trends, generate insights, and visualize results. It includes Python code to extract, process, and visualize data.

## Prerequisites

1. Python 3.8 or higher.
2. PostgreSQL database (configured as `reddit_data_crawler` and `chan_data_crawler`).
3. Required Python libraries (install with `requirements.txt`).
4. Jupyter Notebook.

## Setup Instructions

### Step 1: Clone Repository and Navigate
Clone the project repository and navigate to its directory:
```bash
git clone <repository-url>
cd <project-folder>
```

### Step 2: Create a Virtual Environment
Set up a virtual environment to manage dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### Step 3: Install Dependencies
Install the necessary Python libraries using `requirements.txt`:
```bash
pip install -r requirements.txt
```

### Step 4: Set Up the Database
1. **Database Names:**
   - `reddit_data_crawler`
   - `chan_data_crawler`

2. **Tables for Reddit Data (`reddit_data_crawler`):**
   - `reddit_crawler_comments`
   - `reddit_crawler_posts`
   - `reddit_crawling_state`

3. **Tables for 4chan Data (`chan_data_crawler`):**
   - `chan_comments`
   - `chan_posts`
   - `chan_submissions`

Ensure your database is running, and update the connection strings if necessary.

### Step 5: Configure Environment Variables
Set up the following environment variables:
- `DATABASE_URL`: PostgreSQL connection string.
- Example: `postgres://<user>:<password>@<host>:<port>/<database>`

Use `.env` file for storing these values:
```env
DATABASE_URL=postgres://postgres:password@localhost:5432/reddit_data_crawler
```

### Step 6: Run the Jupyter Notebook
Start the Jupyter Notebook server and open the project file:
```bash
jupyter notebook
```
Navigate to `p2_4chan_reddit.ipynb` and open it.

## Notebook Execution
1. **Configure Parameters:** Modify variables like table names and dates as per your dataset.
2. **Run the Notebook:** Execute each cell sequentially for data extraction, analysis, and visualization.

## Outputs
- Visualizations for data trends.
- Insights from data analysis.


