"""Pins safety-relevant instructions in skill text that review found missing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validate_local_route_asks_instead_of_searching_the_filesystem():
    text = (ROOT / 'skills' / 'validate' / 'SKILL.md').read_text(encoding='utf-8')
    local = text.split('## Local route', 1)[1].split('\n## ', 1)[0]
    local = ' '.join(local.split())          # Markdown wraps lines anywhere
    assert 'ask the user for the path' in local
    assert 'Never search the filesystem for images' in local
