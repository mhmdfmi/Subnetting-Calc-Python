import sys
import tempfile
import os

from subnet_calc import main, load_config, resolve_preset


def test_cli_no_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["subnet_calc.py"])
    exit_code = main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No command provided" in captured.err


def test_load_config_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"presets": {"home": "192.168.1.0/24"}}')
        f.flush()
        config = load_config(f.name)
        assert config["presets"]["home"] == "192.168.1.0/24"
    os.unlink(f.name)


def test_load_config_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("presets:\n  home: 192.168.1.0/24\n")
        f.flush()
        config = load_config(f.name)
        assert config["presets"]["home"] == "192.168.1.0/24"
    os.unlink(f.name)


def test_resolve_preset():
    config = {"presets": {"home": "192.168.1.0/24"}}
    assert resolve_preset("home", config, "presets") == "192.168.1.0/24"
    assert resolve_preset("raw", config, "presets") == "raw"
