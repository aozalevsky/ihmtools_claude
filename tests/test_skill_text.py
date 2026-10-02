"""Pins safety-relevant instructions in skill text that review found missing."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validate_local_route_asks_instead_of_searching_the_filesystem():
    text = (ROOT / 'skills' / 'validate' / 'SKILL.md').read_text(encoding='utf-8')
    local = text.split('## Local route', 1)[1].split('\n## ', 1)[0]
    local = ' '.join(local.split())          # Markdown wraps lines anywhere
    assert 'ask the user for the path' in local
    assert 'Never search the filesystem for images' in local


def _skill(name):
    text = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
    return ' '.join(text.split())


def test_upload_confirmation_required_even_for_fully_specified_requests():
    # Live smoke: "Deposit X to the dev server as a draft" was taken as consent
    # and uploaded without showing the account first.
    rule = ('A request that already names the file, server, or options is not '
            'the confirmation')
    for name in ('validate', 'deposit'):
        text = _skill(name)
        assert rule in text, name
        assert 'end your turn' in text, name
