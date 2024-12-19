from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
import pandas as pd
import matplotlib.pyplot as plt
from textblob import TextBlob
import io
import base64
import json
import time
import threading
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Database URLs
reddit_db_url = "postgresql://postgres:testpassword@localhost:5437/reddit_data_crawler"
chan_db_url = "postgresql://postgres:testpassword@localhost:5437/chan_data_crawler"

# Create Flask app
app = Flask(__name__)

# Create database engines
reddit_engine = create_engine(reddit_db_url)
chan_engine = create_engine(chan_db_url)

# Global progress tracking dictionary
progress_status = {
    "reddit_total": 0,
    "reddit_processed": 0,
    "chan_total": 0,
    "chan_processed": 0,
    "status": "idle",  # 'idle', 'processing', 'completed'
}


# Utility functions
def calculate_toxicity(content):
    """Calculate sentiment polarity as toxicity score."""
    if not content or not isinstance(content, str):
        return None
    return TextBlob(content).sentiment.polarity

def classify_hate_speech(content):
    """Classify if the content is hate speech based on toxicity."""
    toxicity_score = calculate_toxicity(content)
    return toxicity_score is not None and toxicity_score < -0.3

def plot_to_base64(plt):
    """Convert a matplotlib plot to Base64 for rendering in HTML."""
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    base64_image = base64.b64encode(buffer.getvalue()).decode()
    buffer.close()
    plt.close()
    return base64_image
def extract_comment_content(data):
    if not data:
        return None
    try:
        data_dict = json.loads(data) if isinstance(data, str) else data
        if isinstance(data_dict, dict) and 'com' in data_dict:
            return data_dict['com'].strip()
        else:
            return None
    except json.JSONDecodeError:
        return None

# Processing Functions
# Processing Functions with Hate Speech
def process_reddit_comments():
    print("Processing Reddit comments...")
    progress_status["status"] = "processing"
    with reddit_engine.connect() as conn:
        query = text("SELECT comment_id, content FROM reddit_crawler_comments WHERE toxicity_score IS NULL")
        comments = conn.execute(query).fetchall()
        progress_status["reddit_total"] = len(comments)
        progress_status["reddit_processed"] = 0

        for comment_id, content in comments:
            toxicity_score = calculate_toxicity(content)
            is_hate_speech = classify_hate_speech(content)
            conn.execute(
                text("""
                    UPDATE reddit_crawler_comments
                    SET toxicity_score = :toxicity_score, is_hate_speech = :is_hate_speech
                    WHERE comment_id = :comment_id
                """),
                {"toxicity_score": toxicity_score, "is_hate_speech": is_hate_speech, "comment_id": comment_id},
            )
            progress_status["reddit_processed"] += 1
        conn.commit()
    print("Reddit comments toxicity and hate speech updated.")

def process_chan_comments():
    print("Processing 4chan comments...")
    progress_status["status"] = "processing"
    with chan_engine.connect() as conn:
        query = text("""
            SELECT id, data
            FROM chan_comments
            WHERE toxicity_score IS NULL
        """)
        comments = conn.execute(query).fetchall()
        progress_status["chan_total"] = len(comments)
        progress_status["chan_processed"] = 0

        for comment_id, data in comments:
            comment_content = extract_comment_content(data)
            toxicity_score = calculate_toxicity(comment_content)
            is_hate_speech = classify_hate_speech(comment_content)
            conn.execute(
                text("""
                    UPDATE chan_comments
                    SET toxicity_score = :toxicity_score, is_hate_speech = :is_hate_speech
                    WHERE id = :comment_id
                """),
                {"toxicity_score": toxicity_score, "is_hate_speech": is_hate_speech, "comment_id": comment_id},
            )
            progress_status["chan_processed"] += 1
        conn.commit()
    print("4chan comments toxicity and hate speech updated.")

# Background Processing with Threading
def process_all_comments():
    process_reddit_comments()
    process_chan_comments()
    progress_status["status"] = "completed"

@app.route('/start-processing')
def start_processing():
    """Start processing comments in the background."""
    if progress_status["status"] == "processing":
        return jsonify({"message": "Processing already in progress"}), 400
    thread = threading.Thread(target=process_all_comments)
    thread.start()
    return jsonify({"message": "Processing started"}), 202

@app.route('/progress-status')
def progress_status_route():
    """Get the current processing status."""
    return jsonify(progress_status)
@app.route('/data-count', methods=['GET'])
def data_count():
    """
    Bar graph showing the total count of posts from Reddit and 4chan filtered by date and platform,
    with optional date and platform filters.
    """
    # Flags to control filter visibility
    show_date_filter = True
    show_platform_filter = True

    # Extract user inputs for date range and platform
    start_date = request.args.get('start_date', "2024-11-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))
    platform = request.args.get('platform', 'all')  # 'reddit', 'chan', or 'all'

    queries = {
        "reddit": f"""
            SELECT COUNT(*) AS count
            FROM reddit_crawler_posts
            WHERE created_utc BETWEEN '{start_date}' AND '{end_date}';
        """,
        "chan": f"""
            SELECT COUNT(*) AS count
            FROM chan_posts
            WHERE created_at BETWEEN '{start_date}' AND '{end_date}';
        """
    }

    # Fetch data for the selected platform(s)
    reddit_data, chan_data = pd.DataFrame(), pd.DataFrame()
    if platform in ['all', 'reddit']:
        with reddit_engine.connect() as conn:
            reddit_data = pd.read_sql(queries['reddit'], conn)
        reddit_data['source'] = 'Reddit'

    if platform in ['all', 'chan']:
        with chan_engine.connect() as conn:
            chan_data = pd.read_sql(queries['chan'], conn)
        chan_data['source'] = '4chan'

    # Combine data and calculate total count
    combined_data = pd.concat([reddit_data, chan_data], ignore_index=True)
    total_count = combined_data['count'].sum()

    # Prepare the plot
    plt.figure(figsize=(8, 6))
    plt.bar(combined_data['source'], combined_data['count'], color=['blue', 'green'])
    plt.title('Data Count by Platform', fontsize=16)
    plt.xlabel('Platform', fontsize=14)
    plt.ylabel('Count', fontsize=14)
    plt.tight_layout()
    image = plot_to_base64(plt)

    # Render the graph with dynamic filters and data summary
    return render_template(
        'graph_with_dates.html',
        title="Data Count by Platform",
        image=image,
        show_date_filter=show_date_filter,
        show_platform_filter=show_platform_filter,
        start_date=start_date,
        end_date=end_date,
        platform=platform,
        total_count=total_count,
         function_name="data_count"
    )
@app.route('/daily-comments')
def daily_comments():
    """Line graph showing daily comment counts for Reddit and 4chan."""
    # Extract user-defined parameters
    start_date = request.args.get('start_date', "2024-11-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))
    platform = request.args.get('platform', 'all')  # Options: 'all', 'reddit', 'chan'

    # Initialize empty DataFrame for combining data
    combined_data = pd.DataFrame()

    # Query Reddit data if platform is 'all' or 'reddit'
    if platform in ['all', 'reddit']:
        reddit_query = f"""
        SELECT DATE(created_utc) AS comment_date, COUNT(*) AS count
        FROM reddit_crawler_comments
        WHERE created_utc BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY comment_date
        ORDER BY comment_date;
        """
        with reddit_engine.connect() as conn:
            reddit_data = pd.read_sql(reddit_query, conn)
        reddit_data['platform'] = 'Reddit'
        combined_data = pd.concat([combined_data, reddit_data], ignore_index=True)

    # Query 4chan data if platform is 'all' or 'chan'
    if platform in ['all', 'chan']:
        chan_query = f"""
        SELECT DATE(created_at) AS comment_date, COUNT(*) AS count
        FROM chan_comments
        WHERE created_at BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY comment_date
        ORDER BY comment_date;
        """
        with chan_engine.connect() as conn:
            chan_data = pd.read_sql(chan_query, conn)
        chan_data['platform'] = '4chan'
        combined_data = pd.concat([combined_data, chan_data], ignore_index=True)

    # Plotting the data
    plt.figure(figsize=(14, 7))
    if platform in ['all', 'reddit']:
        plt.plot(
            reddit_data['comment_date'], 
            reddit_data['count'], 
            label='Reddit', 
            marker='o', 
            color='blue'
        )
    if platform in ['all', 'chan']:
        plt.plot(
            chan_data['comment_date'], 
            chan_data['count'], 
            label='4chan', 
            marker='o', 
            color='green'
        )
    plt.title('Daily Comments from Reddit and 4chan', fontsize=16)
    plt.xlabel('Date', fontsize=14)
    plt.ylabel('Number of Comments', fontsize=14)
    plt.xticks(rotation=45)
    plt.legend(fontsize=12)
    plt.grid()
    plt.tight_layout()

    # Convert plot to base64
    image = plot_to_base64(plt)

    # Render the graph page
    return render_template(
        'graph_with_dates.html',
        title="Daily Comments",
        image=image,
        start_date=start_date,
        end_date=end_date,
        platform=platform.capitalize(),
        show_date_filter=True,
        show_platform_filter=True,
        function_name="daily_comments"
    )




@app.route('/subreddit-comments')
def subreddit_comments():
    """Line graph showing daily comment counts for a specific subreddit."""
    subreddit_name = request.args.get('subreddit', 'politics')
    start_date = request.args.get('start_date', "2024-11-23")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

    try:
        # Fetch unique subreddit names for dropdown
        query = text("SELECT DISTINCT subreddit FROM reddit_crawler_posts ORDER BY subreddit;")
        with reddit_engine.connect() as conn:
            subreddits = [row[0] for row in conn.execute(query).fetchall()]

        # Query for subreddit-specific data
        reddit_query = text(f"""
        SELECT DATE(c.created_utc) AS comment_date, COUNT(*) AS count
        FROM reddit_crawler_comments c
        JOIN reddit_crawler_posts p ON c.post_id = p.post_id
        WHERE p.subreddit = :subreddit_name
        AND c.created_utc BETWEEN :start_date AND :end_date
        GROUP BY comment_date
        ORDER BY comment_date;
        """)
        with reddit_engine.connect() as conn:
            subreddit_data = pd.read_sql(reddit_query, conn, params={
                "subreddit_name": subreddit_name,
                "start_date": start_date,
                "end_date": end_date
            })

        # Plotting the data
        plt.figure(figsize=(14, 7))
        plt.plot(
            subreddit_data['comment_date'],
            subreddit_data['count'],
            label=subreddit_name.title(),
            marker='o',
            color='blue'
        )
        plt.title(f'Daily Comments for Subreddit: {subreddit_name.title()}', fontsize=16)
        plt.xlabel('Date', fontsize=14)
        plt.ylabel('Number of Comments', fontsize=14)
        plt.xticks(rotation=45)
        plt.legend(fontsize=12)
        plt.grid()
        plt.tight_layout()

        image = plot_to_base64(plt)

        return render_template(
            'graph_with_dates.html',
            title=f"Subreddit Comments - {subreddit_name.title()}",
            image=image,
            start_date=start_date,
            end_date=end_date,
            show_date_filter=True,
            show_platform_filter=False,
            subreddits=subreddits,
            subreddit=subreddit_name,
            function_name="subreddit_comments"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/daily-submissions')
def daily_submissions():
    """Bar graph showing daily submission counts for a subreddit with user-defined date range."""
    try:
        # Fetch unique subreddit names for the dropdown
        query = text("SELECT DISTINCT subreddit FROM reddit_crawler_posts ORDER BY subreddit;")
        with reddit_engine.connect() as conn:
            subreddits = [row[0] for row in conn.execute(query).fetchall()]

        # Extract user-defined subreddit and date range
        subreddit = request.args.get('subreddit', subreddits[0])  # Default to the first subreddit
        start_date = request.args.get('start_date', "2024-12-01")
        end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

        # SQL query to fetch submission counts
        query = f"""
        SELECT DATE(created_utc) AS post_date, COUNT(*) AS submission_count
        FROM reddit_crawler_posts
        WHERE subreddit = '{subreddit}'
        AND created_utc BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY post_date
        ORDER BY post_date;
        """
        with reddit_engine.connect() as conn:
            subreddit_data = pd.read_sql(query, conn)

        # Generate a complete date range
        date_range = pd.date_range(start=start_date, end=end_date)
        subreddit_data['post_date'] = pd.to_datetime(subreddit_data['post_date'])
        complete_df = pd.DataFrame({'post_date': date_range})
        complete_df = complete_df.merge(subreddit_data, on='post_date', how='left')
        complete_df['submission_count'] = complete_df['submission_count'].fillna(0).astype(int)

        # Plotting the data
        plt.figure(figsize=(14, 7))
        plt.bar(
            complete_df['post_date'].dt.strftime('%Y-%m-%d'),
            complete_df['submission_count'],
            color='skyblue'
        )
        plt.title(f'Daily Submission Counts for r/{subreddit}', fontsize=16)
        plt.xlabel('Date', fontsize=14)
        plt.ylabel('Number of Submissions', fontsize=14)
        plt.xticks(rotation=90, fontsize=10)
        plt.tight_layout()

        # Convert plot to base64
        image = plot_to_base64(plt)

        # Render the graph page with subreddit dropdown
        return render_template(
            'graph_with_dates.html',
            title=f"Daily Submissions for r/{subreddit}",
            image=image,
            start_date=start_date,
            end_date=end_date,
            show_date_filter=True,
            show_platform_filter=False,
            subreddits=subreddits,
            subreddit=subreddit,
            function_name="daily_submissions"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/hourly-comments')
def hourly_comments():
    """Line graph showing hourly comment volume for a subreddit with user-defined date range."""
    try:
        # Fetch unique subreddit names for the dropdown
        query = text("SELECT DISTINCT subreddit FROM reddit_crawler_posts ORDER BY subreddit;")
        with reddit_engine.connect() as conn:
            subreddits = [row[0] for row in conn.execute(query).fetchall()]

        # Extract user-defined subreddit and date range
        subreddit = request.args.get('subreddit', subreddits[0])  # Default to the first subreddit
        start_date = request.args.get('start_date', "2024-12-01")
        end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

        # SQL query to fetch hourly comment counts
        query = f"""
        SELECT DATE_TRUNC('hour', c.created_utc) AS datetime_hour, COUNT(*) AS comment_count
        FROM reddit_crawler_comments c
        JOIN reddit_crawler_posts p ON c.post_id = p.post_id
        WHERE p.subreddit = '{subreddit}'
        AND c.created_utc BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY datetime_hour
        ORDER BY datetime_hour;
        """
        with reddit_engine.connect() as conn:
            df = pd.read_sql(query, conn)

        # Generate a complete hourly range
        start_datetime = pd.to_datetime(start_date)
        end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1)
        hourly_range = pd.date_range(start=start_datetime, end=end_datetime, freq='H')

        # Create a complete DataFrame and merge
        df['datetime_hour'] = pd.to_datetime(df['datetime_hour']).dt.tz_localize(None)
        complete_df = pd.DataFrame({'datetime_hour': hourly_range})
        complete_df = complete_df.merge(df, on='datetime_hour', how='left')
        complete_df['comment_count'] = complete_df['comment_count'].fillna(0).astype(int)

        # Dynamically adjust x-axis ticks
        max_ticks = 25
        step = max(1, len(complete_df) // max_ticks)
        ticks = complete_df['datetime_hour'][::step]
        labels = ticks.dt.strftime('%Y-%m-%d %H:%M')

        # Plotting the data
        plt.figure(figsize=(14, 7))
        plt.plot(
            complete_df['datetime_hour'],
            complete_df['comment_count'],
            marker='o',
            color='blue',
            linewidth=1
        )
        plt.title(f'Hourly Comment Counts for r/{subreddit}', fontsize=16)
        plt.xlabel('Date and Time (Hourly)', fontsize=14)
        plt.ylabel('Number of Comments', fontsize=14)
        plt.xticks(ticks=ticks, labels=labels, rotation=90, fontsize=10)
        plt.grid(True, linestyle='--', linewidth=0.5)
        plt.tight_layout()

        # Convert plot to base64
        image = plot_to_base64(plt)

        # Render the graph page with subreddit dropdown
        return render_template(
            'graph_with_dates.html',
            title=f"Hourly Comments for r/{subreddit}",
            image=image,
            start_date=start_date,
            end_date=end_date,
            show_date_filter=True,
            show_platform_filter=False,
            subreddits=subreddits,
            subreddit=subreddit,
            function_name="hourly_comments"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/top-subreddits')
def top_subreddits():
    """Bar graph showing the number of comments received by the top 10 subreddits."""
    query = """
    SELECT p.subreddit AS subreddit_name, COUNT(c.comment_id) AS count
    FROM reddit_crawler_comments c
    JOIN reddit_crawler_posts p ON c.post_id = p.post_id
    GROUP BY p.subreddit
    ORDER BY count DESC
    LIMIT 10;
    """
    with reddit_engine.connect() as conn:
        subreddit_data = pd.read_sql(query, conn)

    # Plot the data
    plt.figure(figsize=(14, 8))
    plt.bar(subreddit_data['subreddit_name'], subreddit_data['count'], color='blue')

    # Customize the chart
    plt.title('Comments Received by Subreddit (Top 10)', fontsize=16)
    plt.xlabel('Subreddit', fontsize=14)
    plt.ylabel('Number of Comments', fontsize=14)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Convert the plot to a Base64 image for rendering
    image = plot_to_base64(plt)

    return render_template(
        'graph_with_dates.html',
        title="Top Subreddits by Comments",
        image=image,
        show_date_filter=False,
        show_platform_filter=False,
        function_name="top_subreddits"
    )

# Sentiment classification function
def classify_sentiment(text):
    if not isinstance(text, str) or text.strip() == "":
        return "Neutral"
    sentiment_score = TextBlob(text).sentiment.polarity
    if sentiment_score > 0.2:
        return "Positive"
    elif sentiment_score < -0.2:
        return "Negative"
    else:
        return "Neutral"
@app.route('/sentiment-comparison')
def sentiment_comparison():
    """Grouped bar chart comparing sentiment counts across platforms."""
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

    # Define queries for Reddit and 4chan
    queries = {
        "reddit": f"""
            SELECT content
            FROM reddit_crawler_comments
            WHERE created_utc BETWEEN '{start_date}' AND '{end_date}';
        """,
        "chan": f"""
            SELECT data
            FROM chan_comments
            WHERE created_at BETWEEN '{start_date}' AND '{end_date}';
        """
    }

    # Sentiment counts for each platform
    sentiment_counts = {"Reddit": {"Positive": 0, "Neutral": 0, "Negative": 0},
                        "4chan": {"Positive": 0, "Neutral": 0, "Negative": 0}}

    # Fetch and classify sentiments for Reddit
    with reddit_engine.connect() as conn:
        reddit_data = pd.read_sql(queries['reddit'], conn)
        reddit_data['sentiment'] = reddit_data['content'].apply(classify_sentiment)
        sentiment_counts['Reddit'] = reddit_data['sentiment'].value_counts().to_dict()

    # Fetch and classify sentiments for 4chan
    with chan_engine.connect() as conn:
        chan_data = pd.read_sql(queries['chan'], conn)
        chan_data['content'] = chan_data['data'].apply(extract_comment_content)  # Extract content from 4chan data
        chan_data['sentiment'] = chan_data['content'].apply(classify_sentiment)
        sentiment_counts['4chan'] = chan_data['sentiment'].value_counts().to_dict()

    # Convert sentiment counts to a DataFrame
    sentiment_df = pd.DataFrame(sentiment_counts).fillna(0)

    # Plot grouped bar chart
    plt.figure(figsize=(10, 6))
    sentiment_df.plot(kind='bar', width=0.8, figsize=(10, 6))
    plt.title("Sentiment Analysis Comparison", fontsize=16)
    plt.xlabel("Sentiment", fontsize=14)
    plt.ylabel("Count", fontsize=14)
    plt.xticks(rotation=0)
    plt.legend(title="Platform", fontsize=10)
    plt.tight_layout()

    # Convert plot to Base64 for HTML rendering
    image = plot_to_base64(plt)

    return render_template(
        'graph_with_dates.html',
        title="Sentiment Comparison Across Platforms",
        image=image,
        start_date=start_date,
        end_date=end_date,
        show_date_filter=True,
        show_platform_filter=False,
        function_name="sentiment-comparison"
    )
@app.route('/hatespeech-comparison')
def hatespeech_comparison():
    """Grouped bar chart comparing hate speech counts (True/False) across platforms."""
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

    # Define queries for Reddit and 4chan
    queries = {
        "reddit": """
            SELECT is_hate_speech, COUNT(*) as count
            FROM reddit_crawler_comments
            WHERE created_utc BETWEEN :start_date AND :end_date
            GROUP BY is_hate_speech;
        """,
        "chan": """
            SELECT is_hate_speech, COUNT(*) as count
            FROM chan_comments
            WHERE created_at BETWEEN :start_date AND :end_date
            GROUP BY is_hate_speech;
        """
    }

    # Initialize hate speech counts for both platforms
    hate_speech_counts = {
        "True": {"Reddit": 0, "4chan": 0},
        "False": {"Reddit": 0, "4chan": 0}
    }

    # Fetch hate speech data for Reddit
    with reddit_engine.connect() as conn:
        reddit_data = pd.read_sql(
            text(queries['reddit']), conn, params={"start_date": start_date, "end_date": end_date}
        )
        for _, row in reddit_data.iterrows():
            key = "True" if row['is_hate_speech'] else "False"
            hate_speech_counts[key]["Reddit"] += row["count"]

    # Fetch hate speech data for 4chan
    with chan_engine.connect() as conn:
        chan_data = pd.read_sql(
            text(queries['chan']), conn, params={"start_date": start_date, "end_date": end_date}
        )
        for _, row in chan_data.iterrows():
            key = "True" if row['is_hate_speech'] else "False"
            hate_speech_counts[key]["4chan"] += row["count"]

    # Convert data to DataFrame
    hate_speech_df = pd.DataFrame(hate_speech_counts).T
    hate_speech_df.reset_index(inplace=True)
    hate_speech_df.rename(columns={"index": "Hate Speech"}, inplace=True)

    # Plot the grouped bar chart
    plt.figure(figsize=(10, 6))
    x = range(len(hate_speech_df))
    bar_width = 0.35

    # Bar positions for each platform
    plt.bar([i - bar_width / 2 for i in x], hate_speech_df["Reddit"], bar_width, label="Reddit", color="blue")
    plt.bar([i + bar_width / 2 for i in x], hate_speech_df["4chan"], bar_width, label="4chan", color="orange")

    # Configure the plot
    plt.xticks(x, hate_speech_df["Hate Speech"], fontsize=12)
    plt.title("Hate Speech Analysis Comparison", fontsize=16)
    plt.xlabel("Hate Speech", fontsize=14)
    plt.ylabel("Count", fontsize=14)
    plt.legend(title="Platform", fontsize=12)
    plt.tight_layout()

    # Convert plot to Base64
    image = plot_to_base64(plt)

    # Pass hate speech counts as a summary
    data_summary = {
        "Reddit": {
            "True": hate_speech_counts["True"]["Reddit"],
            "False": hate_speech_counts["False"]["Reddit"]
        },
        "4chan": {
            "True": hate_speech_counts["True"]["4chan"],
            "False": hate_speech_counts["False"]["4chan"]
        }
    }

    # Render the graph page
    return render_template(
        'graph_with_dates.html',
        title="Hate Speech Comparison",
        image=image,
        start_date=start_date,
        end_date=end_date,
        show_date_filter=True,
        show_platform_filter=False,
        data_summary=data_summary,  # Pass the data summary
        function_name="hatespeech-comparison"
    )




@app.route('/sentiment-reddit')
def sentiment_reddit():
    """Sentiment analysis for a specific subreddit with user-defined date range."""
    try:
        # Fetch unique subreddit names for the dropdown
        query = text("SELECT DISTINCT subreddit FROM reddit_crawler_posts ORDER BY subreddit;")
        with reddit_engine.connect() as conn:
            subreddits = [row[0] for row in conn.execute(query).fetchall()]

        # Extract user-defined subreddit and date range
        subreddit = request.args.get('subreddit', subreddits[0])  # Default to the first subreddit
        start_date = request.args.get('start_date', "2024-12-01")
        end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

        # Query for sentiment analysis
        query = text(f"""
        SELECT c.content
        FROM reddit_crawler_comments c
        JOIN reddit_crawler_posts p ON c.post_id = p.post_id
        WHERE p.subreddit = :subreddit
        AND c.created_utc BETWEEN :start_date AND :end_date;
        """)
        with reddit_engine.connect() as conn:
            df = pd.read_sql(query, conn, params={
                "subreddit": subreddit,
                "start_date": start_date,
                "end_date": end_date
            })

        # Perform sentiment analysis
        df['sentiment_category'] = df['content'].apply(classify_sentiment)
        sentiment_counts = df['sentiment_category'].value_counts()

        # Plot sentiment distribution
        plt.figure(figsize=(8, 6))
        sentiment_counts.plot(kind='bar', color=['green', 'gray', 'red'])
        plt.title(f"Sentiment Analysis for r/{subreddit}", fontsize=16)
        plt.xlabel('Sentiment', fontsize=14)
        plt.ylabel('Count', fontsize=14)
        plt.tight_layout()
        image = plot_to_base64(plt)

        # Render with the dropdown
        return render_template(
    'graph_with_dates.html',
    title=f"Sentiment Analysis for r/{subreddit}",
    image=image,
    start_date=start_date,
    end_date=end_date,
    show_date_filter=True,
    show_platform_filter=False,
    subreddits=subreddits,  # List of all subreddits for the dropdown
    subreddit=subreddit,    # Selected subreddit value
    function_name="sentiment_reddit"
)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/hatespeech-reddit')
def hatespeech_reddit():
    """Hate speech analysis for Reddit comments with user-defined date range."""
    # Extract user-defined date range and subreddit
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))
    subreddit = request.args.get('subreddit', 'all')

    # Fetch unique subreddit names for dropdown
    query_subreddits = text("SELECT DISTINCT subreddit FROM reddit_crawler_posts ORDER BY subreddit;")
    with reddit_engine.connect() as conn:
        subreddits = [row[0] for row in conn.execute(query_subreddits).fetchall()]

    # SQL query with subreddit filtering
    query = f"""
    SELECT c.is_hate_speech
    FROM reddit_crawler_comments c
    JOIN reddit_crawler_posts p ON c.post_id = p.post_id
    WHERE c.created_utc BETWEEN :start_date AND :end_date
    """
    if subreddit != 'all':
        query += " AND p.subreddit = :subreddit"
    
    params = {"start_date": start_date, "end_date": end_date}
    if subreddit != 'all':
        params["subreddit"] = subreddit

    with reddit_engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    # Count hate speech occurrences
    hate_speech_counts = df['is_hate_speech'].value_counts()

    # Plot hate speech distribution
    plt.figure(figsize=(8, 6))
    hate_speech_counts.plot(kind='bar', color=['blue', 'orange'])
    plt.title(f"Hate Speech Analysis for r/{subreddit}" if subreddit != 'all' else "Hate Speech Analysis for Reddit")
    plt.xlabel('Hate Speech (0: No, 1: Yes)', fontsize=14)
    plt.ylabel('Count', fontsize=14)
    plt.tight_layout()
    image = plot_to_base64(plt)

    return render_template(
    'graph_with_dates.html',
    title=f"Hate Speech Analysis for r/{subreddit}" if subreddit != 'all' else "Hate Speech Analysis for Reddit",
    image=image,
    start_date=start_date,
    end_date=end_date,
    show_date_filter=True,
    show_platform_filter=False,
    subreddits=subreddits,  # Dropdown list
    subreddit=subreddit,    # Selected subreddit
    function_name="hatespeech_reddit"
)


@app.route('/sentiment-4chan')
def sentiment_4chan():
    """Sentiment analysis for 4chan comments with user-defined date range."""
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

    query = f"""
    SELECT sentiment
    FROM chan_comments
    WHERE created_at BETWEEN '{start_date}' AND '{end_date}';
    """
    with chan_engine.connect() as conn:
        df = pd.read_sql(query, conn)

    sentiment_counts = df['sentiment'].value_counts() if 'sentiment' in df else pd.Series([], name="sentiment")

    plt.figure(figsize=(8, 6))
    sentiment_counts.plot(kind='bar', color=['green', 'gray', 'red'])
    plt.title('Sentiment Analysis for 4chan', fontsize=16)
    plt.xlabel('Sentiment', fontsize=14)
    plt.ylabel('Count', fontsize=14)
    plt.tight_layout()

    image = plot_to_base64(plt)

    return render_template(
        'graph_with_dates.html',
        title="Sentiment Analysis for 4chan",
        image=image,
        start_date=start_date,
        end_date=end_date,
        show_date_filter=True,
        show_platform_filter=False,
        function_name="sentiment_4chan"
    )
@app.route('/hatespeech-4chan')
def hatespeech_4chan():
    """Hate speech analysis for 4chan comments with user-defined date range."""
    # Extract user-defined date range
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))

    # SQL query to fetch hate speech data
    query = f"""
    SELECT is_hate_speech
    FROM chan_comments
    WHERE created_at BETWEEN '{start_date}' AND '{end_date}';
    """
    with chan_engine.connect() as conn:
        df = pd.read_sql(query, conn)

    # Count hate speech occurrences
    hate_speech_counts = df['is_hate_speech'].value_counts()

    # Plot the hate speech distribution
    plt.figure(figsize=(8, 6))
    hate_speech_counts.plot(kind='bar', color=['blue', 'orange'])
    plt.title('Hate Speech Analysis for 4chan', fontsize=16)
    plt.xlabel('Hate Speech (0: No, 1: Yes)', fontsize=14)
    plt.ylabel('Count', fontsize=14)
    plt.tight_layout()

    # Convert plot to base64 image
    image = plot_to_base64(plt)

    # Render the graph with appropriate template
    return render_template(
        'graph_with_dates.html',
        title="Hate Speech Analysis for 4chan",
        image=image,
        start_date=start_date,
        end_date=end_date,
        show_date_filter=True,
        show_platform_filter=False,
        function_name="hatespeech_4chan"
    )


@app.route('/time-series-toxicity')
def time_series_toxicity():
    """Time series of average toxicity scores over user-defined date range and platform."""
    start_date = request.args.get('start_date', "2024-12-01")
    end_date = request.args.get('end_date', "2024-12-10")
    platform = request.args.get('platform', 'all')  # 'all', 'reddit', or 'chan'

    queries = {
        "reddit": f"""
            SELECT DATE(created_utc) AS post_date, AVG(toxicity_score) AS avg_toxicity
            FROM reddit_crawler_comments
            WHERE created_utc BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY post_date ORDER BY post_date;
        """,
        "chan": f"""
            SELECT DATE(created_at) AS post_date, AVG(toxicity_score) AS avg_toxicity
            FROM chan_comments
            WHERE created_at BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY post_date ORDER BY post_date;
        """
    }

    reddit_data, chan_data = pd.DataFrame(), pd.DataFrame()
    if platform in ['all', 'reddit']:
        with reddit_engine.connect() as conn:
            reddit_data = pd.read_sql(queries['reddit'], conn)
    if platform in ['all', 'chan']:
        with chan_engine.connect() as conn:
            chan_data = pd.read_sql(queries['chan'], conn)

    # Plot the data
    plt.figure(figsize=(10, 6))
    if not reddit_data.empty:
        plt.plot(reddit_data['post_date'], reddit_data['avg_toxicity'], label='Reddit', marker='o', color='blue')
    if not chan_data.empty:
        plt.plot(chan_data['post_date'], chan_data['avg_toxicity'], label='4chan', marker='o', color='orange')

    plt.title('Time Series of Average Toxicity Scores')
    plt.xlabel('Date')
    plt.ylabel('Average Toxicity Score')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()

    image = plot_to_base64(plt)

    return render_template(
        'graph_with_dates.html',
        title="Time Series of Toxicity Scores",
        image=image,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        show_date_filter=True,
        show_platform_filter=True,
        function_name="time_series_toxicity"
    )
@app.route('/platform-comparison-toxicity')
def platform_comparison():
    """Compare toxicity levels across platforms with optional date filtering."""
    start_date = request.args.get('start_date', "2024-11-01")
    end_date = request.args.get('end_date', datetime.datetime.now().strftime("%Y-%m-%d"))
    platform = request.args.get('platform', 'all')  # 'reddit', 'chan', or 'all'

    queries = {
        "reddit": f"""
            SELECT 'Reddit' AS platform, AVG(toxicity_score) AS avg_toxicity
            FROM reddit_crawler_comments
            WHERE created_utc BETWEEN '{start_date}' AND '{end_date}';
        """,
        "chan": f"""
            SELECT '4chan' AS platform, AVG(toxicity_score) AS avg_toxicity
            FROM chan_comments
            WHERE created_at BETWEEN '{start_date}' AND '{end_date}';
        """
    }

    reddit_data, chan_data = pd.DataFrame(), pd.DataFrame()
    if platform in ['all', 'reddit']:
        with reddit_engine.connect() as conn:
            reddit_data = pd.read_sql(queries['reddit'], conn)
    if platform in ['all', 'chan']:
        with chan_engine.connect() as conn:
            chan_data = pd.read_sql(queries['chan'], conn)

    combined_data = pd.concat([reddit_data, chan_data], ignore_index=True)

    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.bar(combined_data['platform'], combined_data['avg_toxicity'], color=['blue', 'orange'])
    plt.title('Toxicity Levels Across Platforms')
    plt.xlabel('Platform')
    plt.ylabel('Average Toxicity')
    plt.tight_layout()

    image = plot_to_base64(plt)

    # Render the graph page
    return render_template(
        'graph_with_dates.html',
        title="Platform Comparison of Toxicity",
        image=image,
        start_date=start_date,
        end_date=end_date,
        platform=platform,
        show_date_filter=True,
        show_platform_filter=True,
        function_name="platform_comparison"
    )
@app.route('/')
def index():
    """Homepage that provides links to other features."""
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
