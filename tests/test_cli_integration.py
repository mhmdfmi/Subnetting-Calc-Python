import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from subnet_calc import main


def test_cli_count_split(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["subnet_calc.py", "count", "--network", "192.168.1.0/24", "--count", "2"],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Split 192.168.1.0/24 into 2 /25 subnets" in captured.out


def test_cli_reverse_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["subnet_calc.py", "reverse", "--hosts", "100,50"])
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Smallest subnet for [100, 50] hosts: /" in captured.out


def test_cli_vlsm_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["subnet_calc.py", "vlsm", "--network", "10.0.0.0/16", "--hosts", "500,200"],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "VLSM for 500,200 in 10.0.0.0/16:" in captured.out


def test_cli_supernet_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "subnet_calc.py",
            "supernet",
            "--networks",
            "192.168.1.0/24,192.168.2.0/24",
        ],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Supernet for 192.168.1.0/24,192.168.2.0/24:" in captured.out


def test_cli_overlap_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["subnet_calc.py", "overlap", "--networks", "192.168.1.0/24,192.168.2.0/24"],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "No overlaps found" in captured.out


def test_cli_eui64_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "subnet_calc.py",
            "eui64",
            "--mac",
            "00:11:22:33:44:55",
            "--prefix",
            "2001:db8::/64",
        ],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "EUI-64 IPv6 address:" in captured.out


def test_cli_version_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["subnet_calc.py", "version"])
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "subnet-calc version" in captured.out


def test_cli_range_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["subnet_calc.py", "range", "--network", "192.168.1.0/24"],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "First host:" in captured.out


def test_cli_compare_command(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "subnet_calc.py",
            "compare",
            "--network1",
            "192.168.1.0/24",
            "--network2",
            "192.168.1.0/25",
        ],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "contains" in captured.out


def test_cli_input_file_networks(tmp_path, monkeypatch, capsys):
    input_file = tmp_path / "networks.txt"
    input_file.write_text("192.168.1.0/24\n192.168.2.0/24\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["subnet_calc.py", "summarize", "--input", str(input_file)],
    )
    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Summarize supernet" in captured.out


def test_cli_default_json_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["subnet_calc.py", "version", "--format", "json"])
    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "subnet-calc-version.json").exists()


def test_cli_summarize_markdown_output(tmp_path, monkeypatch):
    output_file = tmp_path / "summary.md"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "subnet_calc.py",
            "summarize",
            "--networks",
            "192.168.1.0/24,192.168.2.0/24",
            "--format",
            "markdown",
            "--output",
            str(output_file),
        ],
    )
    exit_code = main()

    assert exit_code == 0
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "| networks |" in content
    assert "| supernet |" in content

