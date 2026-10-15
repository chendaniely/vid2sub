import subprocess
import sys

import pytest

from vid2sub.cli import main


def test_vid2sub_with_no_arguments_prints_help_and_exits_0(capsys):
    assert main([]) == 0
    assert "usage: vid2sub" in capsys.readouterr().out


def test_python_dash_m_vid2sub_prints_the_version():
    proc = subprocess.run([sys.executable, "-m", "vid2sub", "--version"],
                          check=False, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.startswith("vid2sub ")


def test_a_usage_error_exits_64_not_2():
    with pytest.raises(SystemExit) as err:
        main(["--no-such-option"])
    assert err.value.code == 64
