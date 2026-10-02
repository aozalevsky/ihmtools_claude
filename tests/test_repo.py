"""Repository-level checks: manifests, disclaimer, skills, agents, portability."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHORT_DISCLAIMER = ('Unofficial, community plugin, not affiliated with RCSB PDB, '
                    'Rutgers, or UCSF.')
README_DISCLAIMER = """\
> **Unofficial plugin.** ihmtools is an independent project. It is not
> affiliated with, endorsed by, or supported by RCSB PDB, Rutgers, The State
> University of New Jersey, or the University of California, San Francisco
> (UCSF). PDB-IHM, IHMValidation, python-ihm, and the `ihmv`/`ihmdep`
> command-line tools are developed and maintained by their own authors; this
> plugin only helps Claude use them. Names are used solely to identify those
> tools and services."""
REPO_URL = 'https://github.com/aozalevsky/ihmtools_claude'
SHIPPED = ['.claude-plugin', 'skills', 'agents', 'scripts', 'README.md']
EXPECTED_FILES = [
    '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json', 'README.md',
    'LICENSE', '.gitignore', 'pytest.ini',
    'scripts/probe.sh',
    'skills/ihmcif/SKILL.md',
    'skills/ihmcif/references/data-model.md',
    'skills/ihmcif/references/tooling.md',
    'skills/check/SKILL.md',
]
SKILLS = sorted(p.parent for p in ROOT.glob('skills/*/SKILL.md'))
AGENTS = sorted(ROOT.glob('agents/*.md'))


def frontmatter(path):
    """Parse the simple YAML frontmatter used here: scalars and '- item' lists."""
    text = path.read_text(encoding='utf-8')
    assert text.startswith('---\n'), f'{path} has no frontmatter'
    block = text.split('---\n', 2)[1]
    data, key = {}, None
    for line in block.splitlines():
        if line.startswith('  - ') and key:
            data.setdefault(key, []).append(line[4:].strip())
        elif ':' in line:
            key, _, value = line.partition(':')
            key, value = key.strip(), value.strip()
            if value:
                data[key] = value
    return data, text.split('---\n', 2)[2]


def manifest(name):
    return json.loads((ROOT / '.claude-plugin' / name).read_text(encoding='utf-8'))


@pytest.mark.parametrize('rel', EXPECTED_FILES)
def test_expected_file_exists(rel):
    assert (ROOT / rel).is_file()


def test_plugin_manifest():
    m = manifest('plugin.json')
    assert m['name'] == 'ihmtools'
    assert re.fullmatch(r'\d+\.\d+\.\d+', m['version'])
    assert m['description'].startswith(SHORT_DISCLAIMER)
    assert m['author'] == {'name': 'Arthur Zalevsky'}
    assert m['license'] == 'MIT'
    assert m['homepage'] == m['repository'] == REPO_URL


def test_marketplace_manifest_agrees_with_plugin():
    plugin, market = manifest('plugin.json'), manifest('marketplace.json')
    assert market['owner'] == {'name': 'Arthur Zalevsky'}
    assert market['description'].startswith(SHORT_DISCLAIMER)
    [entry] = market['plugins']
    assert (entry['name'], entry['source'], entry['version']) == \
        (plugin['name'], './', plugin['version'])
    assert entry['description'].startswith(SHORT_DISCLAIMER)
    assert entry['homepage'] == REPO_URL


def test_readme_opens_with_disclaimer():
    lines = (ROOT / 'README.md').read_text(encoding='utf-8').split('\n')
    assert lines[0] == '# ihmtools'
    assert '\n'.join(lines[2:9]) == README_DISCLAIMER


def test_license_is_mit():
    assert (ROOT / 'LICENSE').read_text(encoding='utf-8').startswith('MIT License')


@pytest.mark.parametrize('skill', SKILLS, ids=lambda p: p.name)
def test_skill_frontmatter(skill):
    meta, body = frontmatter(skill / 'SKILL.md')
    assert meta['name'] == skill.name
    assert 50 <= len(meta['description']) <= 1024
    assert body.strip()


@pytest.mark.parametrize('agent', AGENTS, ids=lambda p: p.stem)
def test_agent_frontmatter(agent):
    meta, body = frontmatter(agent)
    assert meta['name'] == agent.stem
    assert 50 <= len(meta['description']) <= 1024
    for skill in meta.get('skills', []):
        assert (ROOT / 'skills' / skill / 'SKILL.md').is_file(), skill
    assert body.strip()


def _shipped_text_files():
    for name in SHIPPED:
        path = ROOT / name
        files = [path] if path.is_file() else sorted(path.rglob('*'))
        yield from (f for f in files if f.is_file() and f.suffix in ('.md', '.json', '.py', '.sh'))


def test_referenced_plugin_paths_exist():
    for path in _shipped_text_files():
        text = path.read_text(encoding='utf-8')
        for rel in re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)', text):
            assert (ROOT / rel).exists(), f'{path}: {rel}'
        for rel in re.findall(r'\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)', text):
            assert (path.parent / rel).exists(), f'{path}: {rel}'


@pytest.mark.parametrize('pattern', ['/home/', 'arthur/', 'ihm_latest',
                                     'work/validation', 'pdb-ihm-ops'])
def test_nothing_machine_specific_is_shipped(pattern):
    hits = [str(p.relative_to(ROOT)) for p in _shipped_text_files()
            if pattern in p.read_text(encoding='utf-8')]
    assert hits == []
