import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse
import logging
import nltk
from nltk.corpus import stopwords
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Helper functions for URL processing
def process_url(url: str) -> List[str]:
    """
    Split URL on '/' and remove 'preview' elements.
    """
    if not url or not isinstance(url, str):
        return []
    parts = url.strip('/').split('/')
    return [part for part in parts if part != 'preview']


def is_versioned_pair(url1_parts: List[str], url2_parts: List[str]) -> bool:
    """
    Check if two URLs represent different versions of the same article.
    """
    if len(url1_parts) != len(url2_parts):
        return False

    # Check if all elements except the last one are identical
    if url1_parts[:-1] != url2_parts[:-1]:
        return False

    # Get the last elements
    last1 = url1_parts[-1]
    last2 = url2_parts[-1]  # Fixed: was incorrectly using url1_parts[-1]
    
    # If they are identical, they're not different versions
    if last1 == last2:
        return False

    # Special case for the specific pattern like "50-jahre-pedro-pascal-vom-uberlebenskunstler-zum-internet-daddy-810941-0"
    # Look for URLs that end with {articleid}-{version} pattern
    specific_pattern = r'^(.*-\d+)-(\d+)$'
    specific_match1 = re.match(specific_pattern, last1)
    specific_match2 = re.match(specific_pattern, last2)
    
    if specific_match1 and specific_match2 and specific_match1.group(1) == specific_match2.group(1):
        return True
        
    # Check for common versioning patterns
    # 1. Handle patterns like "article-810941-0", "article-810941-1" - specific pattern that ends with -X
    explicit_version_pattern = r'^(.+?)-(\d+)$'
    match1 = re.match(explicit_version_pattern, last1)
    match2 = re.match(explicit_version_pattern, last2)
    
    if match1 and match2 and match1.group(1) == match2.group(1):
        # Check if these are just different version numbers
        return True
        
    # 2. Handle pattern where an article ID is followed by a version suffix
    # Like "50-jahre-pedro-pascal-vom-uberlebenskunstler-zum-internet-daddy-810941-0"
    article_id_version_pattern = r'^(.+)-(\d+)-(\d+)$'
    match1 = re.match(article_id_version_pattern, last1)
    match2 = re.match(article_id_version_pattern, last2)
    
    if match1 and match2:
        # If the base and article ID parts are the same, just different version numbers
        if match1.group(1) == match2.group(1) and match1.group(2) == match2.group(2):
            return True
    
    # 3. Previous pattern matching as fallback
    pattern = r'^(.*?)(?:-\d+)*(?:-(\d+))?$'
    match1 = re.match(pattern, last1)
    match2 = re.match(pattern, last2)
    
    if match1 and match2:
        # Extract the base part without any version numbers
        base1 = match1.group(1)
        base2 = match2.group(1)
        
        # If base parts are identical, they're considered versions
        if base1 == base2:
            return True
            
        # Special case: if one has a base ending with a number and the other has the same base
        # For example: "article-810941" and "article-810941-1"
        base_pattern = r'^(.+?)(?:-\d+)?$'
        base_match1 = re.match(base_pattern, base1)
        base_match2 = re.match(base_pattern, base2)
        
        if base_match1 and base_match2 and base_match1.group(1) == base_match2.group(1):
            return True

    # Check if one is contained in the other (original logic as fallback)
    if last1 in last2 or last2 in last1:
        # Check for versioning pattern like "nice-day" and "nice-day-1"
        simple_pattern = r'^(.+?)(-\d+)?$'
        simple_match1 = re.match(simple_pattern, last1)
        simple_match2 = re.match(simple_pattern, last2)

        if simple_match1 and simple_match2 and simple_match1.group(1) == simple_match2.group(1):
            return True

    return False


def extract_base_link(url: str) -> str:
    """
    Extract domain from URL.
    """
    try:
        if not url or not isinstance(url, str):
            return ""
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return url if isinstance(url, str) else ""


def extract_url_path(url: str) -> str:
    """
    Extract path from URL (everything after the domain).
    """
    try:
        if not url or not isinstance(url, str):
            return ""
        parsed = urlparse(url)
        return parsed.path.strip('/')
    except:
        return ""


def get_url_last_segment(url: str) -> str:
    """
    Extract the last segment of a URL path.
    """
    path = extract_url_path(url)
    if not path:
        return ""
    segments = path.split('/')
    return segments[-1] if segments else ""


# New smaller functions for deduplication strategies
def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the dataframe for deduplication by adding necessary columns.
    """
    df = df.copy()
    
    # Add base_link column if it doesn't exist
    if 'base_link' not in df.columns:
        if 'link' in df.columns:
            df['base_link'] = df['link'].apply(extract_base_link)
        elif 'url' in df.columns:
            df['base_link'] = df['url'].apply(extract_base_link)
        else:
            # If no link column exists, just use the head as the grouping key
            df['base_link'] = df['head']
    
    # Extract URL paths for cross-domain deduplication
    if 'url' in df.columns:
        df['url_path'] = df['url'].apply(extract_url_path)
        df['url_last_segment'] = df['url'].apply(get_url_last_segment)
    else:
        df['url_path'] = ""
        df['url_last_segment'] = ""
    
    return df


def deduplicate_by_url_path(df: pd.DataFrame) -> Set[int]:
    """
    Deduplicate articles with identical URL paths across different domains.
    Returns indices of articles to keep.
    """
    kept_indices = set()
    duplicate_indices = set()
    
    if 'url_last_segment' not in df.columns or df['url_last_segment'].isna().all():
        logger.info("No valid URL paths found, skipping URL path deduplication")
        return set(df.index)
        
    # Find meaningful URL paths (non-empty)
    meaningful_paths_mask = df['url_last_segment'].apply(lambda x: bool(x) if isinstance(x, str) else False)
    path_df = df[meaningful_paths_mask]
    
    if path_df.empty:
        logger.info("No meaningful URL paths found")
        return set(df.index)
        
    # Group by URL last segment
    url_segment_groups = path_df.groupby('url_last_segment')
    
    for segment, group in url_segment_groups:
        if len(group) > 1:  # Multiple articles share the same URL last segment
            # Keep the newest article by pubtime
            newest_idx = group['pubtime'].idxmax()
            kept_indices.add(newest_idx)
            
            # Mark other indices as duplicates
            dup_indices = group.index.difference([newest_idx]).tolist()
            duplicate_indices.update(dup_indices)
            logger.debug(f"URL path deduplication: keeping {newest_idx} from {group.index.tolist()}")
        else:
            # Only one article with this path
            kept_indices.add(group.index[0])
    
    # Add indices of articles without meaningful paths
    kept_indices.update(df[~meaningful_paths_mask].index)
    
    logger.info(f"URL path deduplication kept {len(kept_indices)} articles from {len(df)} candidates")
    logger.info(f"URL path deduplication removed {len(duplicate_indices)} duplicate articles")
    return kept_indices


def deduplicate_by_versioning(group: pd.DataFrame) -> Set[int]:
    """
    Identify versioned URLs within a group and keep the newest from each version.
    Returns indices of articles to keep.
    """
    kept_indices = set()
    
    processed_urls = {idx: process_url(row['url']) for idx, row in group.iterrows()}
    version_groups = {}

    # Group indices by versioning pattern
    for idx1, parts1 in processed_urls.items():
        found_group = False
        for version_key, indices in version_groups.items():
            idx_sample = indices[0]
            if is_versioned_pair(parts1, processed_urls[idx_sample]):
                version_groups[version_key].append(idx1)
                found_group = True
                break

        if not found_group:
            version_groups[len(version_groups)] = [idx1]

    # For each version group, keep the newest by pubtime
    for version_key, indices in version_groups.items():
        if len(indices) == 1:
            kept_indices.add(indices[0])
        else:
            newest_idx = max(indices, key=lambda idx: group.loc[idx, 'pubtime'])
            kept_indices.add(newest_idx)
            logger.debug(f"URL versioning deduplication: keeping {newest_idx} from {indices}")
    
    logger.info(f"URL versioning deduplication kept {len(kept_indices)} articles from {len(group)} in group")
    return kept_indices


def preprocess_text(text: str) -> str:
    """
    Preprocess text by removing special characters, normalizing whitespace,
    and removing stopwords.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    
    try:
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and numbers
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\d+', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove stopwords (optional - comment if causing performance issues)
        try:
            stop_words = set(stopwords.words('german')) | set(stopwords.words('english'))
            words = text.split()
            text = ' '.join(word for word in words if word not in stop_words)
        except:
            logger.warning("Stopword removal failed, using original text")
        
        return text
    except Exception as e:
        logger.error(f"Text preprocessing failed: {str(e)}")
        return text if isinstance(text, str) else ""


def deduplicate_by_content_similarity(group: pd.DataFrame, threshold: float = 0.85) -> Set[int]:
    """
    Deduplicate articles based on content similarity using TF-IDF.
    Returns indices of articles to keep.
    """
    kept_indices = set()
    
    # Filter out rows with invalid content
    valid_content_mask = group['content'].apply(lambda x: isinstance(x, str) and bool(x.strip()))
    valid_content_group = group[valid_content_mask]

    # If no valid content remains, keep all rows
    if valid_content_group.empty:
        logger.warning("No valid content found in group, keeping all")
        return set(group.index.tolist())

    try:
        # Preprocess content for better similarity detection
        preprocessed_content = valid_content_group['content'].apply(preprocess_text)
        
        # Get document count to set appropriate TF-IDF parameters
        doc_count = len(preprocessed_content)
        logger.debug(f"Processing content similarity for {doc_count} documents")
        
        # For very small groups, use simplified parameters
        if doc_count <= 3:
            tfidf = TfidfVectorizer(
                analyzer='word',
                ngram_range=(1, 1),  # Use only unigrams for small groups
                min_df=1,            # Accept terms appearing in at least 1 document
                max_df=1.0,          # Accept terms appearing in all documents
                sublinear_tf=True    # Apply sublinear tf scaling (1 + log(tf))
            ).fit_transform(preprocessed_content)
        else:
            # Dynamically set min_df and max_df based on document count
            min_df_val = min(2, max(1, int(doc_count * 0.1)))  # At least 1, at most 2, or 10% of docs
            max_df_val = min(0.95, (doc_count - 1) / doc_count)  # Ensure max_df is always less than 100% of docs
            
            tfidf = TfidfVectorizer(
                analyzer='word',
                ngram_range=(1, 2),  # Use unigrams and bigrams
                min_df=min_df_val,   # Dynamically set min_df
                max_df=max_df_val,   # Dynamically set max_df
                sublinear_tf=True    # Apply sublinear tf scaling (1 + log(tf))
            ).fit_transform(preprocessed_content)
        
        # Calculate the similarity matrix for all document pairs
        similarity_matrix = cosine_similarity(tfidf)
        n = len(valid_content_group)
        
        # Create prioritization scores based on pubtime (newer is better)
        has_pubtime = 'pubtime' in valid_content_group.columns
        if has_pubtime:
            # Ensure pubtime is datetime
            if not pd.api.types.is_datetime64_any_dtype(valid_content_group['pubtime']):
                try:
                    valid_content_group['pubtime'] = pd.to_datetime(valid_content_group['pubtime'])
                except:
                    has_pubtime = False
        
        # Priority selection algorithm
        unselected = set(range(n))
        selected = []
        
        # If we have pubtime, start with the newest article
        if has_pubtime:
            newest_idx = valid_content_group['pubtime'].argmax()
            selected.append(newest_idx)
            unselected.remove(newest_idx)
        
        # While there are unselected articles
        while unselected:
            best_candidate = None
            max_min_distance = -1
            
            # For each unselected article
            for candidate in unselected:
                # Find minimum similarity to already selected articles
                min_sim = 1.0
                for idx in selected:
                    sim = similarity_matrix[candidate, idx]
                    min_sim = min(min_sim, sim)
                
                # Convert similarity to distance (1 - sim)
                min_distance = 1.0 - min_sim
                
                # If this candidate is more distinct than our current best
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_candidate = candidate
            
            # If the best candidate is distinct enough (below threshold)
            if max_min_distance > (1.0 - threshold):
                selected.append(best_candidate)
            
            # Remove from unselected regardless (to avoid infinite loop)
            unselected.remove(best_candidate)
        
        # Get the original indices
        selected_indices = valid_content_group.iloc[selected].index.tolist()
        kept_indices.update(selected_indices)
        logger.debug(f"Content similarity kept {len(selected_indices)} articles from {n} with valid content")

        # Add rows with invalid content that were filtered out earlier
        invalid_content_indices = group[~valid_content_mask].index.tolist()
        kept_indices.update(invalid_content_indices)
        logger.debug(f"Added {len(invalid_content_indices)} articles with invalid content")
        
    except Exception as e:
        # If TF-IDF fails, keep all remaining articles
        logger.error(f"TF-IDF processing failed with error: {str(e)}. Keeping all articles in group.")
        return set(group.index.tolist())

    logger.info(f"Content similarity deduplication kept {len(kept_indices)} articles from {len(group)} in group")
    return kept_indices


def deduplicate_by_content_similarity_per_day(df: pd.DataFrame, threshold: float = 0.85) -> pd.DataFrame:
    """
    Final deduplication step: remove content-similar articles within each day.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Input DataFrame with articles
    threshold : float, default=0.85
        Similarity threshold for content-based deduplication
        
    Returns:
    --------
    pandas.DataFrame
        Deduplicated DataFrame with duplicate articles removed
    """
    if df.empty:
        return df
    
    logger.info(f"Starting day-by-day content similarity deduplication on {len(df)} articles")
    
    # Ensure pubtime is datetime
    df_copy = df.copy()
    if 'pubtime' in df_copy.columns:
        if not pd.api.types.is_datetime64_any_dtype(df_copy['pubtime']):
            try:
                df_copy['pubtime'] = pd.to_datetime(df_copy['pubtime'])
            except Exception as e:
                logger.error(f"Failed to convert pubtime to datetime: {str(e)}")
                # Create a dummy date column
                df_copy['date'] = pd.Timestamp('2000-01-01')
                return df_copy
    else:
        # If no pubtime, return the original dataframe
        logger.warning("No pubtime column found, skipping day-by-day deduplication")
        return df_copy
    
    # Extract date component for grouping
    df_copy['date'] = df_copy['pubtime'].dt.date
    
    # Create empty result dataframe
    result_parts = []
    
    # Group by date and process each day
    date_groups = df_copy.groupby('date')
    logger.info(f"Processing {len(date_groups)} date groups")
    
    for date, group in date_groups:
        if len(group) <= 1:
            # Only one article on this day, keep it
            result_parts.append(group)
            continue
            
        logger.debug(f"Processing {len(group)} articles for date {date}")
        
        try:
            # Apply content similarity deduplication to this day's articles
            kept_indices = deduplicate_by_content_similarity(group, threshold)
            deduplicated_group = group.loc[list(kept_indices)]
            result_parts.append(deduplicated_group)
            
            logger.debug(f"Day deduplication kept {len(deduplicated_group)} of {len(group)} articles for {date}")
        except Exception as e:
            logger.error(f"Error during day deduplication for {date}: {str(e)}")
            # If error occurs, keep all articles for this day
            result_parts.append(group)
    
    # Combine results and drop the temporary date column
    result_df = pd.concat(result_parts) if result_parts else df_copy
    
    logger.info(f"Day-by-day deduplication reduced articles from {len(df)} to {len(result_df)}")
    return result_df.drop(columns=['date'])


def validate_dataframe(df: pd.DataFrame) -> None:
    """
    Check if the DataFrame contains all required columns.
    Raises ValueError if a required column is missing.
    """
    required_columns = ['base_link', 'head', 'url', 'content', 'pubtime']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Required columns missing from DataFrame: {missing_columns}")


def deduplicate_df(df_with_link: pd.DataFrame, threshold: float = 0.85) -> pd.DataFrame:
    """
    Deduplicate articles based on URL versioning and content similarity.
    Also deduplicates articles that share the same URL path across different domains.
    """
    # Create a working copy to avoid modifying the original
    df = prepare_dataframe(df_with_link.copy())
    
    try:
        validate_dataframe(df)
    except ValueError as e:
        logger.error(f"DataFrame validation failed: {str(e)}")
        return df_with_link
    
    # First pass: deduplicate articles with identical URL last segments across different domains
    kept_indices = deduplicate_by_url_path(df)
    
    # Filter DataFrame to keep only non-duplicate articles
    df_filtered = df.loc[list(kept_indices)]
    
    if df_filtered.empty:
        logger.info("No articles remaining after URL path deduplication")
        return df_with_link.loc[list(kept_indices)].reset_index(drop=True)
    
    # Second pass: Process the remaining articles by group
    final_kept_indices = set()
    
    try:
        groups = df_filtered.groupby(['base_link', 'head'])
        logger.info(f"Processing {len(groups)} groups for version and content deduplication")
        
        for (base, head), group in groups:
            logger.debug(f"Processing group with base_link={base}, head={head}, size={len(group)}")
            
            if len(group) <= 1:
                # Only one article in the group, keep it
                final_kept_indices.update(group.index.tolist())
                continue
            
            # First try to identify versioned URLs
            version_kept_indices = deduplicate_by_versioning(group)
            final_kept_indices.update(version_kept_indices)
            
            # Process remaining articles in the group for content similarity
            version_removed_indices = group.index.difference(version_kept_indices).tolist()
            if version_removed_indices:
                remaining_in_group = group.loc[version_removed_indices]
                content_kept_indices = deduplicate_by_content_similarity(remaining_in_group, threshold)
                final_kept_indices.update(content_kept_indices)
    
    except Exception as e:
        logger.error(f"Error during group processing: {str(e)}")
        # If an error occurs, add all remaining indices
        final_kept_indices.update(df_filtered.index.tolist())
    
    # Return deduplicated DataFrame with original indices
    logger.info(f"Final deduplication kept {len(final_kept_indices)} articles from {len(df_with_link)}")
    return df_with_link.loc[list(final_kept_indices)].reset_index(drop=True)


def remove_similar_rows(df: pd.DataFrame, threshold: float = 0.85, debug: bool = False) -> pd.DataFrame:
    """
    Remove duplicate articles based on URL and headline similarity.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing article data
    threshold : float, default=0.85
        Similarity threshold for content-based deduplication
    debug : bool, default=False
        If True, prints additional debugging information
        
    Returns:
    --------
    pandas.DataFrame
        Deduplicated DataFrame
    """
    # Store the original logging level to restore it later
    original_log_level = logging.getLogger().level
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)
        
    if df is None or df.empty:
        logger.warning("Empty DataFrame provided, returning empty DataFrame")
        # Restore original logging level
        logging.getLogger().setLevel(original_log_level)
        return pd.DataFrame()

    # Create a working copy of the DataFrame with original index preserved
    working_df = df.copy().reset_index(names='original_index')
    logger.info(f"Starting deduplication on DataFrame with {len(working_df)} rows")

    # Remove rows with the same content_id
    if 'content_id' in working_df.columns:
        working_df = working_df.drop_duplicates(subset=['content_id'], keep='last')
        logger.info(f"Removed {len(df) - len(working_df)} duplicate content_id rows")
    else:
        logger.info("No content_id column found, skipping duplicate removal")

    # Remove rows where 'head' and 'article_link' are the same
    if {'head', 'article_link'}.issubset(working_df.columns):
        working_df = working_df.drop_duplicates(subset=['head', 'article_link'], keep='last')
        logger.info(f"Removed {len(df) - len(working_df)} duplicate rows based on 'head' and 'article_link'")
    else:
        logger.info("'head' or 'article_link' column not found, skipping duplicate removal")

    # Check if article_link column exists
    if 'article_link' not in working_df.columns:
        logger.warning("'article_link' column not found. No deduplication performed.")
        # Restore original logging level
        logging.getLogger().setLevel(original_log_level)
        return working_df.drop(columns=['original_index'])

    # Split dataframe into rows with and without article links
    df_with_link = working_df[working_df['article_link'].notna()].copy()
    df_without_link = working_df[working_df['article_link'].isna()].copy()
    
    logger.info(f"Split DataFrame into {len(df_with_link)} rows with links and {len(df_without_link)} rows without links")

    result_parts = []

    # Deduplicate rows with article links
    if not df_with_link.empty:
        # Rename 'article_link' to 'url' for compatibility with deduplicate_df
        df_with_link['url'] = df_with_link['article_link']
        
        # Ensure pubtime is datetime
        if 'pubtime' in df_with_link.columns:
            if not pd.api.types.is_datetime64_any_dtype(df_with_link['pubtime']):
                try:
                    df_with_link['pubtime'] = pd.to_datetime(df_with_link['pubtime'])
                except:
                    logger.warning("Failed to convert 'pubtime' to datetime. Using original values.")

        # Apply deduplication to rows with article links
        try:
            deduplicated_with_links = deduplicate_df(df_with_link, threshold)
            logger.info(f"Deduplication reduced linked articles from {len(df_with_link)} to {len(deduplicated_with_links)}")
            result_parts.append(deduplicated_with_links)
        except Exception as e:
            logger.error(f"Error during deduplication of linked articles: {str(e)}. Using original linked articles.")
            result_parts.append(df_with_link)

    # Deduplicate rows without article links based on headlines
    if not df_without_link.empty:
        try:
            # Set dummy url values using the headline as the key
            df_without_link['url'] = df_without_link['head']
            df_without_link['base_link'] = "no_link"  # Use a dummy base_link
            
            # Ensure pubtime is datetime
            if 'pubtime' in df_without_link.columns:
                if not pd.api.types.is_datetime64_any_dtype(df_without_link['pubtime']):
                    try:
                        df_without_link['pubtime'] = pd.to_datetime(df_without_link['pubtime'])
                    except:
                        logger.warning("Failed to convert 'pubtime' to datetime. Using original values.")
            
            # Apply same deduplication logic to rows without article links
            deduplicated_no_links = deduplicate_df(df_without_link, threshold)
            logger.info(f"Deduplication reduced unlinked articles from {len(df_without_link)} to {len(deduplicated_no_links)}")
            result_parts.append(deduplicated_no_links)
        except Exception as e:
            logger.error(f"Error during deduplication of articles without links: {str(e)}. Using original unlinked articles.")
            result_parts.append(df_without_link)

    # Combine both deduplicated sets
    result_df = pd.concat(result_parts, ignore_index=True) if result_parts else working_df
    logger.info(f"Combined deduplicated DataFrame has {len(result_df)} rows")

    # Drop extra columns added during processing
    result_df = result_df.drop(columns=['url', 'base_link'], errors='ignore')
    
    logger.info(f"Final deduplicated DataFrame has {len(result_df)} rows")
    
    # Restore original logging level
    logging.getLogger().setLevel(original_log_level)
    
    # Return result without the original_index column
    return result_df.drop(columns=['original_index'])


if __name__ == '__main__':
    # Example usage with more obvious deduplication examples
    df = pd.DataFrame({
        'article_link': [
            'http://example.com/article',
            'http://example.com/article-2',  # Version of the first article
            'http://example.com/article',    # Duplicate of the first article
            'http://example.com/another-article', 
            'http://different-site.com/article'  # Same path as first but different domain
        ],
        'head': [
            'Article 1', 
            'Article 1',   # Same headline
            'Article 1',   # Same headline
            'Article 2', 
            'Article 1'    # Same headline
        ],
        'content': [
            'This is the content of article 1.',
            'This is the content of article 1 with minor changes.',  # Very similar
            'This is the content of article 1.',  # Identical
            'This is the content of article 2.', 
            'This is completely different content with the same headline.'
        ],
        'pubtime': [
            '2023-01-01', 
            '2023-01-02',  # Newer version
            '2023-01-01',
            '2023-01-03', 
            '2023-01-04'   # Newest
        ]
    })

    print("Original DataFrame:")
    print(df)
    print("\n" + "="*50 + "\n")

    # Convert pubtime to datetime
    df['pubtime'] = pd.to_datetime(df['pubtime'])
    
    # Create a copy with original indices to track what was removed
    df_with_idx = df.copy().reset_index(names='original_idx')
    
    # Enable debug mode to see more detailed logs
    deduplicated_df = remove_similar_rows(df, threshold=0.85, debug=False)
    
    print("\nDeduplicated DataFrame:")
    print(deduplicated_df)
    
    # Track which original articles were kept by comparing content
    kept_indices = []
    for _, dedup_row in deduplicated_df.iterrows():
        # Find matching rows in original dataframe by comparing all fields
        for idx, orig_row in df.iterrows():
            if (dedup_row['article_link'] == orig_row['article_link'] and 
                dedup_row['head'] == orig_row['head'] and 
                dedup_row['content'] == orig_row['content']):
                kept_indices.append(idx)
                break
    
    # Show which articles were removed
    removed_indices = set(range(len(df))) - set(kept_indices)
    if removed_indices:
        print("\nRemoved articles:")
        for idx in removed_indices:
            print(f"Index {idx}: {df.iloc[idx]['article_link']} - {df.iloc[idx]['head']}")




