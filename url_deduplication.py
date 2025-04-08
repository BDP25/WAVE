import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse


def process_url(url: str) -> List[str]:
    """
    Split URL on '/' and remove 'preview' elements.

    Parameters:
    -----------
    url : str
        URL to process

    Returns:
    --------
    List[str]
        List of URL parts with 'preview' elements removed
    """
    if not url or not isinstance(url, str):
        return []
    parts = url.strip('/').split('/')
    return [part for part in parts if part != 'preview']


def is_versioned_pair(url1_parts: List[str], url2_parts: List[str]) -> bool:
    """
    Check if two URLs represent different versions of the same article.

    Parameters:
    -----------
    url1_parts : List[str]
        Processed parts of the first URL
    url2_parts : List[str]
        Processed parts of the second URL

    Returns:
    --------
    bool
        True if URLs represent different versions of the same article
    """
    if len(url1_parts) != len(url2_parts):
        return False

    # Check if all elements except the last one are identical
    if url1_parts[:-1] != url2_parts[:-1]:
        return False

    # Get the last elements
    last1 = url1_parts[-1]
    last2 = url2_parts[-1]

    # Check if one is contained in the other
    if last1 in last2 or last2 in last1:
        # Check for versioning pattern like "nice-day" and "nice-day-1"
        pattern = r'^(.+?)(-\d+)?$'
        match1 = re.match(pattern, last1)
        match2 = re.match(pattern, last2)

        if match1 and match2 and match1.group(1) == match2.group(1):
            return True

    return False


def extract_base_link(url: str) -> str:
    """
    Extract domain from URL.

    Parameters:
    -----------
    url : str
        URL to process

    Returns:
    --------
    str
        Domain of the URL or original URL if parsing fails
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

    Parameters:
    -----------
    url : str
        URL to process

    Returns:
    --------
    str
        Path of the URL or empty string if parsing fails
    """
    try:
        if not url or not isinstance(url, str):
            return ""
        parsed = urlparse(url)
        return parsed.path.strip('/')
    except:
        return ""


def deduplicate_df(df_with_link: pd.DataFrame, threshold: float = 0.85) -> pd.DataFrame:
    """
    Deduplicate articles based on URL versioning and content similarity.
    Also deduplicates articles that share the same URL path across different domains.

    Parameters:
    -----------
    df_with_link : pandas.DataFrame
        DataFrame containing article data with URLs
    threshold : float, default=0.85
        Similarity threshold for content-based deduplication

    Returns:
    --------
    pandas.DataFrame
        Deduplicated DataFrame
    """
    # Create a working copy to avoid modifying the original
    df = df_with_link.copy()

    # Check if base_link exists, if not create it
    if 'base_link' not in df.columns:
        if 'link' in df.columns:
            df['base_link'] = df['link'].apply(extract_base_link)
        else:
            # If no link column exists, just use the head as the grouping key
            df['base_link'] = df['head']
    
    # Extract URL paths for cross-domain deduplication
    if 'url' in df.columns:
        df['url_path'] = df['url'].apply(extract_url_path)
    else:
        df['url_path'] = ""

    kept_indices = []

    # Ensure required columns exist
    required_columns = ['base_link', 'head', 'url', 'content', 'pubtime']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    # First pass: deduplicate articles with identical URL paths across different domains
    if 'url_path' in df.columns and not df['url_path'].isna().all():
        # Find meaningful URL paths (non-empty)
        meaningful_paths_mask = df['url_path'].apply(lambda x: bool(x) if isinstance(x, str) else False)
        
        # Group by URL path for articles with meaningful paths
        url_path_groups = df[meaningful_paths_mask].groupby('url_path')
        
        for path, group in url_path_groups:
            if len(group) > 1:  # Multiple articles share the same URL path
                # Keep the newest article by pubtime
                newest_idx = group['pubtime'].idxmax()
                kept_indices.append(newest_idx)
                
                # Mark the rest of the group as processed by removing from the dataframe
                df = df.drop(group.index.difference([newest_idx]))
            
    # Second pass: Use original logic for remaining articles
    try:
        groups = df.groupby(['base_link', 'head'])
    except Exception as e:
        raise ValueError(f"Error grouping DataFrame: {str(e)}")

    for _, group in groups:
        if len(group) <= 1:
            kept_indices.extend(group.index.tolist())
        else:
            # First, try to identify versioned URLs
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
            for indices in version_groups.values():
                if len(indices) == 1:
                    kept_indices.extend(indices)
                else:
                    newest_idx = max(indices, key=lambda idx: group.loc[idx, 'pubtime'])
                    kept_indices.append(newest_idx)

            # If there are still multiple articles to compare after version filtering, use TF-IDF
            remaining_group = group.loc[~group.index.isin(kept_indices)]
            if len(remaining_group) > 1:
                # Filter out rows with invalid content
                valid_content_mask = remaining_group['content'].apply(lambda x: isinstance(x, str) and bool(x.strip()))
                valid_content_group = remaining_group[valid_content_mask]

                # If no valid content remains, keep all rows
                if valid_content_group.empty:
                    kept_indices.extend(remaining_group.index.tolist())
                    continue

                try:
                    # Compute TF-IDF vectors for the valid content
                    tfidf = TfidfVectorizer().fit_transform(valid_content_group['content'])
                    vectors = tfidf.toarray()
                    n = len(valid_content_group)
                    selected = []

                    # Greedy selection: add the candidate if no previous candidate is too similar
                    for i in range(n):
                        candidate_vector = vectors[i].reshape(1, -1)
                        add_candidate = True
                        for sel in selected:
                            sim = cosine_similarity(candidate_vector, vectors[sel].reshape(1, -1))[0, 0]
                            if sim > threshold:
                                add_candidate = False
                                break
                        if add_candidate:
                            selected.append(i)

                    # Correctly use .iloc on the DataFrame instead of on its Index
                    selected_indices = valid_content_group.iloc[selected].index.tolist()
                    kept_indices.extend(selected_indices)

                    # Add rows with invalid content that were filtered out earlier
                    invalid_content_indices = remaining_group[~valid_content_mask].index.tolist()
                    kept_indices.extend(invalid_content_indices)
                except Exception as e:
                    # If TF-IDF fails, keep all remaining articles
                    print(f"Warning: TF-IDF processing failed with error: {str(e)}. Keeping all articles in group.")
                    kept_indices.extend(remaining_group.index.tolist())

    # Return deduplicated DataFrame
    return df_with_link.loc[kept_indices].reset_index(drop=True)


def remove_similar_rows(df: pd.DataFrame, threshold: float = 0.85) -> pd.DataFrame:
    """
    Remove duplicate articles based on URL and headline similarity.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing article data
    threshold : float, default=0.85
        Similarity threshold for content-based deduplication

    Returns:
    --------
    pandas.DataFrame
        Deduplicated DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Create a working copy of the DataFrame
    working_df = df.copy()

    # Check if article_link column exists
    if 'article_link' not in working_df.columns:
        print("Warning: 'article_link' column not found. No deduplication performed.")
        return working_df

    # Split dataframe into rows with and without article links
    df_with_link = working_df[working_df['article_link'].notna()].copy()
    df_without_link = working_df[working_df['article_link'].isna()].copy()

    result_parts = []

    # Deduplicate rows with article links
    if not df_with_link.empty:
        # Rename 'article_link' to 'url' for compatibility with deduplicate_df
        df_with_link['url'] = df_with_link['article_link']

        # Apply deduplication to rows with article links
        try:
            deduplicated_with_links = deduplicate_df(df_with_link, threshold)
            result_parts.append(deduplicated_with_links)
        except Exception as e:
            print(f"Error during deduplication of linked articles: {str(e)}. Using original linked articles.")
            result_parts.append(df_with_link)

    # Deduplicate rows without article links based on headlines
    if not df_without_link.empty:
        try:
            # Set dummy url values using the headline as the key
            df_without_link['url'] = df_without_link['head']
            df_without_link['base_link'] = "no_link"  # Use a dummy base_link
            
            # Apply same deduplication logic to rows without article links
            deduplicated_no_links = deduplicate_df(df_without_link, threshold)
            result_parts.append(deduplicated_no_links)
        except Exception as e:
            print(f"Error during deduplication of articles without links: {str(e)}. Using original unlinked articles.")
            result_parts.append(df_without_link)

    # Combine both deduplicated sets
    result_df = pd.concat(result_parts, ignore_index=True) if result_parts else working_df
    
    return result_df

