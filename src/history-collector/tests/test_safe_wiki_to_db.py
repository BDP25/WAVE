import sys
import types

# Stub out heavy external dependencies before importing code under test
sys.modules['pandas'] = types.ModuleType('pandas')
# Minimal pandas stubs used in safe_wiki_to_db
setattr(sys.modules['pandas'], 'to_datetime', lambda x: x)
setattr(sys.modules['pandas'], 'Timestamp', lambda x: x)
sys.modules['psycopg2'] = types.ModuleType('psycopg2')
# Stub psycopg2 and psycopg2.extras to satisfy imports
psycopg2_mod = types.ModuleType('psycopg2')
# Mark as package
setattr(psycopg2_mod, '__path__', [])
sys.modules['psycopg2'] = psycopg2_mod

# Create extras submodule
extras = types.ModuleType('psycopg2.extras')
setattr(extras, 'execute_batch', lambda *args, **kwargs: None)
sys.modules['psycopg2.extras'] = extras
# Also map 'extras' attribute on psycopg2 module
setattr(psycopg2_mod, 'extras', extras)
extras = types.ModuleType('extras')
setattr(extras, 'execute_batch', lambda *args, **kwargs: None)
setattr(sys.modules['psycopg2'], 'extras', extras)

import re
import pytest
from bs4 import BeautifulSoup

# Now safe to import functions without pandas/psycopg2 loading issues
from safe_wiki_to_db import clean_internal_links, get_user_color, diff_text, compute_diff


def test_clean_internal_links_removes_wiki_links():
    html = '<p>See <a href="/wiki/Test_Page">Test</a> and <a href="/wiki/File:Image.png"><img src="img.png"></a> and <a href="http://example.com">External</a>.</p>'
    cleaned = clean_internal_links(html)
    # Internal /wiki/ link replaced, file link kept, external link kept
    assert 'Test' in cleaned
    assert '<a href' not in cleaned.split('Test')[0]
    assert '<img' in cleaned
    assert 'External' in cleaned
    assert 'http://example.com' in cleaned


def test_get_user_color_is_deterministic_and_hex():
    color1 = get_user_color('Alice')
    color2 = get_user_color('Alice')
    color3 = get_user_color('Bob')
    # Should always start with '#' and length 7
    assert isinstance(color1, str)
    assert color1.startswith('#') and len(color1) == 7
    assert color1 == color2
    assert color1 != color3


def test_diff_text_basic_insert_and_delete():
    old = 'Hello world!'
    new = 'Hello brave new world!'
    diffed = diff_text(old, new, user='Tester')
    # Should highlight inserted words 'brave new'
    assert '<span' in diffed and 'Tester' in diffed
    assert 'brave' in diffed and 'new' in diffed
    # Ensure trailing punctuation remains
    assert diffed.endswith('world!')


def test_diff_text_delete():
    old = 'The quick brown fox.'
    new = 'The fox.'
    diffed = diff_text(old, new, user='Del')
    # 'quick brown ' should be struck through
    assert 'quick' in diffed and 'brown' in diffed
    # Ensure trailing punctuation remains
    assert diffed.endswith('fox.')


def test_compute_diff_html_structure():
    old_html = '<div><p>Alpha beta gamma.</p><p>One two three.</p></div>'
    new_html = '<div><p>Alpha delta gamma.</p><p>One three.</p></div>'
    diffed_html = compute_diff(old_html, new_html, user='U1')
    soup = BeautifulSoup(diffed_html, 'html.parser')
    ps = soup.find_all('p')
    # First paragraph: 'delta' highlighted and trailing content preserved
    html1 = str(ps[0])
    assert '<span' in html1 and 'delta' in html1
    assert 'gamma.' in html1
    # Second paragraph: 'two' deletion and trailing punctuation intact
    html2 = str(ps[1])
    assert 'three.' in html2


def test_diff_text_preserves_trailing_punctuation():
    # Directly test diff_text for trailing token preservation
    old = 'End of line!'
    new = 'End of new line!'
    diffed = diff_text(old, new, user='T')
    # Expect '!'' from old and new to appear at end
    assert diffed.endswith('line!')
    assert 'new' in diffed


def test_diff_text_multiple_changes():
    # Test multiple inserts and deletes in same sentence
    old = 'A B C D'
    new = 'A X B Z D'
    diffed = diff_text(old, new, user='Test')
    # Expect X inserted before B, Z inserted before D, C removed
    assert '<span' in diffed
    # Check insertion and deletion markers
    assert 'X' in diffed and 'Z' in diffed
    assert 'C' in diffed
    # Ensure D remains at end
    assert diffed.strip().endswith('D')


def test_compute_diff_no_changes():
    # If no changes, HTML should remain identical (minus whitespace structuring)
    html = '<div><p>No changes here.</p></div>'
    diffed = compute_diff(html, html, user='U1')
    # Parse and compare contents
    assert BeautifulSoup(diffed, 'html.parser').get_text() == BeautifulSoup(html, 'html.parser').get_text()



def test_diff_text_alpha_beta_gamma():
    # Direct test for the core scenario dropping "gamma."
    old = 'Alpha beta gamma.'
    new = 'Alpha delta gamma.'
    diffed = diff_text(old, new, user='U1')
    # Must highlight 'delta' and preserve 'gamma.'
    assert '<span' in diffed and 'delta' in diffed, "Insertion span missing"
    assert 'gamma.' in diffed, f"Trailing token dropped: {diffed}"


def test_compute_diff_simple_paragraph():
    # Simplest HTML wrapper scenario
    old = '<p>Alpha beta gamma.</p>'
    new = '<p>Alpha delta gamma.</p>'
    result = compute_diff(old, new, user='U1')
    # Should preserve trailing punctuation in the <p>
    assert 'gamma.' in result, f"compute_diff dropped trailing token: {result}"

if __name__ == '__main__':
    pytest.main()
