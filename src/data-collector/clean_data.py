import os
import pandas as pd
import re
from url_deduplication import remove_similar_rows as rsr


# Function to clean text (remove HTML tags, URLs, and unnecessary spaces)
def clean_text(text):
    """
    Cleans text by removing HTML tags, URLs, HTML entities, and normalizing spaces.

    Args:
        text (str): The text to clean

    Returns:
        str: The cleaned text with HTML tags, URLs, and extra spaces removed
    """
    if pd.isna(text):
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)  # Remove URLs
    text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)  # Remove HTML entities
    text = re.sub(r'\s+', ' ', text).strip()  # Reduce multiple spaces
    return text


def clean_and_process_data(folder='raw_data', similarity_threshold=0.98):
    """
    Loads a .tsv.xz file from the given folder, cleans the content, removes similar articles,
    and saves the result as a Parquet file.

    Args:
        folder (str): Path to the folder containing the .tsv.xz file.
        similarity_threshold (float): Threshold for removing similar articles (between 0 and 1).

    Returns:
        pd.DataFrame: The cleaned and processed DataFrame.
    """
    # List files in the folder and filter for .tsv.xz files
    files = [f for f in os.listdir(folder) if f.endswith('.tsv.xz')]
    if not files:
        raise FileNotFoundError(f"No .tsv.xz files found in the folder {folder}.")

    # Get the path of the first found file
    file_path = os.path.join(folder, files[0])

    # Read the CSV file
    df = pd.read_csv(file_path, sep='\t', compression='xz')

    # Clean column names (remove extra spaces)
    df.columns = df.columns.str.strip()

    # Clean the "content" column
    df["content"] = df["content"].apply(clean_text)

    # Remove similar or nearly identical articles
    df = rsr(df, similarity_threshold)

    # Convert 'pubtime' to a datetime format
    df['pubtime'] = pd.to_datetime(df['pubtime'])


    return df
