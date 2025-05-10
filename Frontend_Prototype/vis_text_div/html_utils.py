"""
Utilities for cleaning and post-processing HTML content.
"""
import re
from bs4 import BeautifulSoup
from .logger_utils import setup_logger

logger = setup_logger("html_utils")

def clean_html_output(html_content: str) -> str:
    """
    Clean up HTML output by combining consecutive spans with identical formatting.
    """
    try:
        # Extract just the content div to work with
        content_div_match = re.search(r'<div style=\'padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;\'>\n(.*?)\n</div>',
                                    html_content, re.DOTALL)
        
        if not content_div_match:
            logger.warning("Could not extract content div for cleaning")
            return html_content
            
        content_html = content_div_match.group(1)
        soup = BeautifulSoup(content_html, 'html.parser')
        
        # Group consecutive spans with the same class and style
        current_span = None
        current_attrs = None
        spans_to_remove = []
        
        for span in soup.find_all('span'):
            # Get attributes for comparison (class and style)
            span_attrs = (
                tuple(span.get('class', [])), 
                span.get('style', '')
            )
            
            if current_span is not None and span_attrs == current_attrs:
                # Same formatting as previous span, merge content
                if span.string:
                    if current_span.string:
                        current_span.string += ' ' + span.string
                    else:
                        current_span.string = span.string
                spans_to_remove.append(span)
            else:
                # New formatting group
                current_span = span
                current_attrs = span_attrs
        
        # Remove merged spans
        for span in spans_to_remove:
            span.decompose()
        
        # Replace the content div with cleaned content
        cleaned_content = str(soup)
        cleaned_html = re.sub(
            r'<div style=\'padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;\'>\n.*?\n</div>',
            f"<div style='padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;'>\n{cleaned_content}\n</div>",
            html_content,
            flags=re.DOTALL
        )
        
        return cleaned_html
    
    except Exception as e:
        logger.error(f"Error while cleaning HTML: {e}")
        return html_content  # Return original HTML if cleaning fails
