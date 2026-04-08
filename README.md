# Subnet Calculator

Version 0.1.2 — Updated April 8, 2026.

A lightweight Python CLI and library for IPv4/IPv6 subnetting, VLSM allocation, supernet calculation, overlap detection, and EUI-64 generation.

Supports Python 3.8+ on Windows, macOS, and Linux.

Optional dependencies enable nicer table output and YAML-based presets. The core library itself only requires the Python standard library.

## Installation

Install locally from the project root:

```bash
pip install .
```

Install optional features for table output, YAML config support, and development tools:

```bash
pip install .[dev]
```

Install optional enhanced dependencies via requirements.txt:

```bash
pip install -r requirements.txt
```

## Usage

Run the CLI with a command and required arguments:

```bash
subnet-calc count --network 192.168.1.0/24
subnet-calc count --network 192.168.1.0/24 --count 4
subnet-calc vlsm --network 10.0.0.0/16 --hosts "servers:500,clients:200"
subnet-calc supernet --networks "192.168.1.0/24,192.168.2.0/24"
subnet-calc summarize --networks "192.168.1.0/24,192.168.2.0/24"
subnet-calc range --network 192.168.1.0/24
subnet-calc range --start 192.168.1.1 --end 192.168.1.254
subnet-calc compare --network1 192.168.1.0/24 --network2 192.168.1.0/25
subnet-calc expand --address 2001:db8::1
subnet-calc compress --address 2001:0db8:0000:0000:0000:0000:0000:0001
subnet-calc reverse --hosts "100,50" --ip-version v4
subnet-calc overlap --networks "192.168.1.0/24,192.168.2.0/24"
subnet-calc eui64 --mac "00:11:22:33:44:55" --prefix "2001:db8::/64"
```

For help:

```bash
subnet-calc -h
```

## Output formats

Use the `--format` option to choose output style:

```bash
subnet-calc --format table count --network 192.168.1.0/24
subnet-calc --format json --output results.json vlsm --network 10.0.0.0/16 --hosts "500,200"
subnet-calc --format csv --output subnets.csv count --network 192.168.1.0/24
```

## Features

- Efficient IPv4/IPv6 subnet calculations
- Generator-based subnet splitting for large networks
- VLSM host allocation with named subnets
- Supernet and overlap detection
- IPv6 EUI-64 address generation
- Config-driven scenarios via YAML/JSON
- Optional formatted table, JSON, and CSV output
- Automated tests, linting, and CI workflow for quality assurance

## Sample output

```text
Error: No command provided. Use -h to see the available commands.
```

```text
Split 192.168.1.0/24 into 4 /26 subnets:
Network: 192.168.1.0/26
Version: IPv4
Class: Class C (/17-/24)
Netmask: 255.255.255.192
Broadcast: 192.168.1.63
Total Addresses: 64
Usable Hosts: 62
First Host: 192.168.1.1
Last Host: 192.168.1.62
```

## Packaging

This project is installable with `pip` and includes a console script entry point:

```bash
pip install .
```

Once installed, use the `subnet-calc` command.

## Build and install globally

Use the helper scripts in the project root to build the wheel and install the CLI for your current user.

Windows PowerShell:

```powershell
.\build_global.ps1
```

macOS / Linux / Git Bash:

```bash
./build_global.sh
```

If the `subnet-calc` command is not found after installation, make sure the user scripts directory is in your PATH:

- Windows: `%APPDATA%\Python\PythonXX\Scripts`
- macOS/Linux: `~/.local/bin`

### Publishing to PyPI

Build the package and upload with `twine`:

```bash
python -m build
python -m twine upload dist/*
```

You can also install a local editable copy for development:

```bash
pip install -e .
```

## Continuous integration

Automated tests are provided through GitHub Actions for Windows, Linux, and macOS using Python 3.8+.

## Changelog

See `CHANGELOG.md` for release notes.
