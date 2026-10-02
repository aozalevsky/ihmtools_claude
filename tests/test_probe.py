import os
import shutil
import subprocess
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / 'scripts' / 'probe.sh'
BASH = shutil.which('bash')
NAMES = ['python', 'ihm', 'msgpack', 'gemmi', 'ihmv', 'ihmdep', 'uv', 'apptainer',
         'chimerax', 'IHMV_SIF']


def probe(**env):
    out = subprocess.run([BASH, str(PROBE)], env=env, capture_output=True,
                         text=True, check=True).stdout
    return dict(line.split(None, 1) for line in out.splitlines())


def test_reports_every_tool_in_order():
    out = subprocess.run([BASH, str(PROBE)], capture_output=True, text=True,
                         check=True).stdout
    assert [line.split()[0] for line in out.splitlines()] == NAMES


def test_missing_tools_get_install_hints(tmp_path):
    rows = probe(PATH=str(tmp_path))          # empty PATH: nothing is found
    assert rows['python'].startswith('missing')
    assert rows['ihmv'] == 'missing (install: pip install ihmtools)'
    assert rows['IHMV_SIF'].startswith('unset')


def test_ihmv_sif_reported(tmp_path):
    sif = tmp_path / 'ihmv.sif'
    assert probe(PATH=os.environ['PATH'], IHMV_SIF=str(sif))['IHMV_SIF'] == \
        f'set to {sif} but no such file'
    sif.write_text('')
    assert probe(PATH=os.environ['PATH'], IHMV_SIF=str(sif))['IHMV_SIF'] == str(sif)
