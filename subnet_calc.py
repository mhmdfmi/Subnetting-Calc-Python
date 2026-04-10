#!/usr/bin/env python3
"""
Subnet Calculator CLI
Usage examples:
  python3 subnet_calc.py count --network 192.168.1.0/24
  python3 subnet_calc.py count --network 192.168.1.0/24 --count 4
  python3 subnet_calc.py count --network 2001:db8::/32 --ip-version v6 --count 2
"""

__version__ = "0.1.3"

import argparse
import ipaddress
import math
import sys
import json
import os
from typing import Dict, Any, List, Optional, Tuple

try:
    import yaml  # type: ignore[import]

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from subnet_utils import (
    print_subnet_details,
    calculate_subnets,
    find_smallest_subnet,
    check_overlap,
    generate_eui64,
    find_supernet,
    handle_vlsm,
    output_json,
    output_csv,
    output_table,
    # output_text,
    output_markdown,
    output_pretty,
    get_subnet_data,
    compare_networks,
    expand_ipv6,
    compress_ipv6,
    network_to_range,
    summarize_address_range,
    SubnetCalculatorError,
    validate_cidr,
    validate_host_count,
)


def load_config(config_file: Optional[str]) -> Dict[str, Any]:
    """Load config from a YAML or JSON file.

    Parameters:
        config_file: Optional path to a YAML or JSON configuration file.

    Returns:
        A dictionary with configuration values, or an empty dict if no file is provided.
    """
    if not config_file or not os.path.exists(config_file):
        return {}
    with open(config_file, "r") as f:
        if (config_file.endswith(".yaml") or config_file.endswith(".yml")) and HAS_YAML:
            return yaml.safe_load(f) or {}
        elif config_file.endswith(".json"):
            return json.load(f) or {}
        elif (
            config_file.endswith(".yaml") or config_file.endswith(".yml")
        ) and not HAS_YAML:
            raise ImportError(
                "YAML support requires 'pyyaml' package. Install with: pip install pyyaml"
            )
    return {}


def resolve_preset(value: str, config: Dict[str, Any], key: str) -> str:
    """Resolve a preset name to its value from config.

    Parameters:
        value: Preset name or raw value.
        config: Config dictionary loaded from YAML/JSON.
        key: Config section to look up (for example, 'presets').

    Returns:
        Resolved value from config or the original value if not found.
    """
    if config and key in config and value in config[key]:
        return config[key][value]
    return value


def parse_arguments() -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Parse command line arguments and return the populated parser and namespace.

    Returns:
        A tuple containing the configured argparse parser and parsed arguments.
    """
    # First, parse global arguments
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--config", help="Path to YAML/JSON config file for presets and scenarios"
    )
    global_parser.add_argument(
        "--scenario",
        help="Load a scenario from the config and auto-fill command and args",
    )
    global_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode for guided input",
    )
    global_parser.add_argument(
        "--verbose", action="store_true", help="Show detailed output"
    )
    global_parser.add_argument(
        "--quiet", action="store_true", help="Show minimal output"
    )
    global_parser.add_argument(
        "--input",
        help="Path to input file containing networks, host lists, or export data",
    )
    global_parser.add_argument(
        "--output",
        help="Output file for results (JSON/CSV/Markdown export formats)",
    )
    global_parser.add_argument(
        "--format",
        choices=["text", "table", "json", "csv", "markdown", "pretty"],
        default="text",
        help="Output format",
    )

    # Parse known args to get global options
    args, remaining = global_parser.parse_known_args()

    # Now create the full parser
    parser = argparse.ArgumentParser(
        description="Subnet Calculator CLI for IPv4/IPv6 subnetting, VLSM, supernet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[global_parser],
        epilog="""Examples:
  subnet-calc --help (show this help)
  subnet-calc count --network 192.168.1.0/24
  subnet-calc count --network 192.168.1.0/24 --count 4
  subnet-calc count --network 192.168.1.0/24 --prefix 26
  subnet-calc count --network 192.168.1.0/24 --hosts "100,50,20"
  subnet-calc vlsm --network 10.0.0.0/16 --hosts "500,200,100,50"
  subnet-calc supernet --networks "192.168.1.0/24,192.168.2.0/24"
  subnet-calc reverse --hosts "100,50" --ip-version v4
  subnet-calc overlap --networks "192.168.1.0/24,192.168.2.0/24"
  subnet-calc eui64 --mac "00:11:22:33:44:55" --prefix "2001:db8::/64"
  subnet-calc --config config.yaml --scenario home_vlsm
  subnet-calc --config config.yaml --scenario office_split
  subnet-calc --config config.yaml --scenario ipv6_deployment
  subnet-calc --config config.yaml --scenario home_vlsm --ip-version v4

  IPv6 Examples:
  subnet-calc count --network 2001:db8::/32 --ip-version v6 --count 2
  subnet-calc vlsm --network 2001:db8::/48 --hosts "1000,500" --ip-version v6
  subnet-calc eui64 --mac "00:11:22:33:44:55" --prefix "2001:db8::/64"
  subnet-calc summarize --networks "192.168.1.0/24,192.168.2.0/24"
  subnet-calc range --network 192.168.1.0/24
  subnet-calc compare --network1 192.168.1.0/24 --network2 192.168.1.0/25
  subnet-calc expand --address 2001:db8::1
  subnet-calc compress --address 2001:0db8:0000:0000:0000:0000:0000:0001

  Output Formats:
  subnet-calc --format table count --network 192.168.1.0/24
  subnet-calc --format json --output results.json vlsm --network 10.0.0.0/16 --hosts "500,200"
  subnet-calc --format csv --output subnets.csv count --network 192.168.1.0/24

  Interactive Mode:
  subnet-calc --interactive
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=False, help="Commands")

    count_parser = subparsers.add_parser(
        "count", help="Show subnet details or split (use --count, --prefix, or --hosts)"
    )
    count_parser.add_argument(
        "--network",
        required=False,
        help="CIDR or preset name (e.g. 192.168.1.0/24 or home)",
    )
    count_parser.add_argument("--count", type=int, help="Split to N equal subnets")
    count_parser.add_argument("--prefix", type=int, help="Split to /PREFIX subnets")
    count_parser.add_argument(
        "--hosts", help='VLSM hosts "subnet1:100,subnet2:50" or preset name'
    )
    count_parser.add_argument(
        "--ip-version", choices=["v4", "v6"], default="v4", help="IPv4 or IPv6"
    )

    vlsm_parser = subparsers.add_parser(
        "vlsm", help="VLSM subnet allocation (supports named hosts and presets)"
    )
    vlsm_parser.add_argument("--network", required=False, help="CIDR or preset name")
    vlsm_parser.add_argument(
        "--hosts", required=False, help='Hosts "subnet1:500,subnet2:200" or preset name'
    )
    vlsm_parser.add_argument("--ip-version", choices=["v4", "v6"], default="v4")

    supernet_parser = subparsers.add_parser("supernet", help="Find supernet")
    supernet_parser.add_argument(
        "--networks", required=False, help='CIDRs "192.168.1.0/24,192.168.2.0/24"'
    )

    summarize_parser = subparsers.add_parser(
        "summarize",
        aliases=["aggregate"],
        help="Find the minimal covering supernet for a list of CIDRs",
    )
    summarize_parser.add_argument(
        "--networks", required=False, help='CIDRs "192.168.1.0/24,192.168.2.0/24"'
    )

    range_parser = subparsers.add_parser(
        "range",
        help="Convert between network/CIDR and IP host range",
    )
    range_parser.add_argument(
        "--network",
        help="CIDR to convert to host range (e.g. 192.168.1.0/24)",
    )
    range_parser.add_argument(
        "--start",
        help="Start IP for range-to-network conversion (e.g. 192.168.1.1)",
    )
    range_parser.add_argument(
        "--end",
        help="End IP for range-to-network conversion (e.g. 192.168.1.254)",
    )

    compare_parser = subparsers.add_parser("compare", help="Compare two CIDR networks")
    compare_parser.add_argument("--network1", required=False, help="First network CIDR")
    compare_parser.add_argument(
        "--network2", required=False, help="Second network CIDR"
    )

    expand_parser = subparsers.add_parser(
        "expand", help="Expand an IPv6 address to full notation"
    )
    expand_parser.add_argument(
        "--address", required=True, help="IPv6 address to expand"
    )

    compress_parser = subparsers.add_parser(
        "compress", help="Compress an IPv6 address to shortest notation"
    )
    compress_parser.add_argument(
        "--address", required=True, help="IPv6 address to compress"
    )

    reverse_parser = subparsers.add_parser(
        "reverse", help="Find smallest subnet for given hosts or host preset"
    )
    reverse_parser.add_argument(
        "--hosts", required=False, help='Hosts "100,50,25" or preset name'
    )
    reverse_parser.add_argument("--ip-version", choices=["v4", "v6"], default="v4")

    overlap_parser = subparsers.add_parser("overlap", help="Check if subnets overlap")
    overlap_parser.add_argument(
        "--networks", required=False, help='CIDRs "192.168.1.0/24,192.168.2.0/24"'
    )

    eui64_parser = subparsers.add_parser(
        "eui64", help="Generate IPv6 EUI-64 address from MAC and /64 prefix"
    )
    eui64_parser.add_argument(
        "--mac", required=True, help="MAC address (e.g. 00:11:22:33:44:55)"
    )
    eui64_parser.add_argument(
        "--prefix", required=True, help="IPv6 prefix (e.g. 2001:db8::/64)"
    )
    # version_parser = subparsers.add_parser(
    #     "version", help="Show package version and release metadata"
    # )
    subparsers.add_parser("version", help="Show package version and release metadata")

    # Parse the remaining args
    remaining_args = parser.parse_args(remaining, namespace=args)
    return parser, remaining_args


def apply_scenario(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Apply a scenario from config to the parsed arguments.

    The scenario can specify a command, network, hosts, and other defaults.
    Scenario values are only applied when the same argument was not provided
    explicitly on the command line.
    """
    if args.scenario:
        if "scenarios" not in config or args.scenario not in config["scenarios"]:
            raise ValueError(f"Scenario '{args.scenario}' not found in config")
        scenario = config["scenarios"][args.scenario]
        # Merge scenario values into args when not explicitly provided
        for key, value in scenario.items():
            if getattr(args, key, None) is None:
                setattr(args, key, value)
        if (
            getattr(args, "ip_version", None) is None
            and getattr(args, "version", None) is not None
        ):
            args.ip_version = args.version
        if args.command is None:
            if "command" in scenario:
                args.command = scenario["command"]
            elif "hosts" in scenario:
                args.command = "vlsm"
            elif "networks" in scenario:
                args.command = "supernet"
            else:
                args.command = "count"


def resolve_presets(args: argparse.Namespace, config: Dict[str, Any]) -> None:
    """Resolve preset names from config for network and hosts fields."""
    if hasattr(args, "network") and args.network:
        args.network = resolve_preset(args.network, config, "presets")
    if hasattr(args, "hosts") and args.hosts:
        args.hosts = resolve_preset(args.hosts, config, "host_presets")


def load_input_file(path: str) -> List[str]:
    """Load a list of items from a text, CSV, JSON, or YAML input file."""
    if not os.path.exists(path):
        raise ValueError(f"Input file not found: {path}")

    extension = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as f:
        if extension in [".yaml", ".yml"]:
            if not HAS_YAML:
                raise ImportError(
                    "YAML input support requires 'pyyaml'. Install with: pip install pyyaml"
                )
            content = yaml.safe_load(f)
        elif extension == ".json":
            content = json.load(f)
        else:
            raw_lines = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
            if extension == ".csv":
                items: List[str] = []
                for line in raw_lines:
                    items.extend(
                        [item.strip() for item in line.split(",") if item.strip()]
                    )
                return items
            return raw_lines

    if content is None:
        return []
    if isinstance(content, dict):
        if "networks" in content:
            return [str(item).strip() for item in content["networks"]]
        if "hosts" in content:
            return [str(item).strip() for item in content["hosts"]]
        items: List[str] = []
        for value in content.values():
            if isinstance(value, (list, tuple)):
                items.extend([str(item).strip() for item in value])
            else:
                items.append(str(value).strip())
        return [item for item in items if item]
    if isinstance(content, (list, tuple)):
        return [str(item).strip() for item in content if item]
    raise ValueError(
        "Input file must contain a list, mapping, or line-delimited values"
    )


def resolve_input_args(args: argparse.Namespace) -> None:
    """Resolve missing operation inputs from a provided file."""
    if not getattr(args, "input", None):
        return

    items = load_input_file(args.input)
    command = getattr(args, "command", None)

    if command in ["supernet", "summarize", "overlap"]:
        if not getattr(args, "networks", None):
            args.networks = ",".join(items)

    if command == "compare":
        if not getattr(args, "network1", None) and not getattr(args, "network2", None):
            if len(items) >= 2:
                args.network1 = items[0]
                args.network2 = items[1]
            else:
                raise ValueError(
                    "Compare input file must contain at least two network entries"
                )

    if command == "range":
        if not getattr(args, "network", None):
            if len(items) == 1 and "/" in items[0]:
                args.network = items[0]
            elif len(items) >= 2:
                args.start = items[0]
                args.end = items[1]

    if command == "count":
        if not getattr(args, "network", None):
            if len(items) == 1:
                args.network = items[0]
            elif len(items) > 1:
                raise ValueError(
                    "Count input file must contain exactly one network entry"
                )
        if not getattr(args, "hosts", None) and len(items) > 1:
            args.hosts = ",".join(items)

    if command == "vlsm":
        if not getattr(args, "network", None) and items:
            args.network = items[0]
        if not getattr(args, "hosts", None) and len(items) > 1:
            args.hosts = ",".join(items[1:])

    if command == "reverse" and not getattr(args, "hosts", None):
        args.hosts = ",".join(items)


def validate_required_args(args: argparse.Namespace) -> None:
    """Validate that required command inputs are supplied after input file resolution."""
    if args.command == "count" and not getattr(args, "network", None):
        raise ValueError("count command requires --network or --input file")
    if args.command == "vlsm":
        if not getattr(args, "network", None):
            raise ValueError("vlsm command requires --network or --input file")
        if not getattr(args, "hosts", None):
            raise ValueError("vlsm command requires --hosts or --input file")
    if args.command in ["supernet", "summarize", "overlap"] and not getattr(
        args, "networks", None
    ):
        raise ValueError(f"{args.command} command requires --networks or --input file")
    if args.command == "compare":
        if not getattr(args, "network1", None) or not getattr(args, "network2", None):
            raise ValueError(
                "compare command requires --network1 and --network2 or --input file"
            )
    if args.command == "reverse" and not getattr(args, "hosts", None):
        raise ValueError("reverse command requires --hosts or --input file")


def interactive_mode(config: Dict[str, Any]) -> argparse.Namespace:
    """Run interactive mode for guided input.

    Returns:
        Parsed arguments namespace built from interactive prompts.
    """
    print("=== Subnet Calculator - Interactive Mode ===")

    # Choose command
    commands = {
        "1": "count",
        "2": "vlsm",
        "3": "supernet",
        "4": "reverse",
        "5": "overlap",
        "6": "eui64",
        "7": "summarize",
        "8": "range",
        "9": "compare",
        "10": "expand",
        "11": "compress",
    }

    try:
        while True:
            print("\nChoose operation:")
            print("1. Show subnet details / split network")
            print("2. VLSM subnet allocation")
            print("3. Find supernet")
            print("4. Find smallest subnet for hosts")
            print("5. Check network overlap")
            print("6. Generate EUI-64 address")
            print("7. Summarize networks into a minimal supernet")
            print("8. Convert network to host range or host range to CIDR")
            print("9. Compare two networks")
            print("10. Expand IPv6 address")
            print("11. Compress IPv6 address")
            choice = input("Enter choice (1-6): ").strip()
            if choice in commands:
                command = commands[choice]
                break
            print("Invalid choice. Try again.")
    except EOFError:
        print("\nNo input provided. Using default operation: count")
        command = "count"

    # Create args namespace
    args = argparse.Namespace()
    args.command = command
    args.config = None  # Will be set later if needed
    args.scenario = None
    args.interactive = True
    args.verbose = True
    args.quiet = False
    args.output = None
    args.format = "text"

    # Gather inputs based on command
    try:
        if command == "count":
            args.network = input("Enter network (e.g. 192.168.1.0/24): ").strip()
            args.ip_version = input("IP version (v4/v6) [v4]: ").strip() or "v4"

            split_choice = (
                input("Split network? (count/prefix/hosts/none) [none]: ")
                .strip()
                .lower()
            )
            if split_choice == "count":
                args.count = int(input("Number of subnets: ").strip())
            elif split_choice == "prefix":
                args.prefix = int(input("Target prefix length: ").strip())
            elif split_choice == "hosts":
                args.hosts = input("Hosts (e.g. 100,50,20): ").strip()

        elif command == "vlsm":
            args.network = input("Enter network (e.g. 10.0.0.0/16): ").strip()
            args.hosts = input("Hosts (e.g. servers:500,clients:200): ").strip()
            args.ip_version = input("IP version (v4/v6) [v4]: ").strip() or "v4"

        elif command == "supernet":
            args.networks = input(
                "Networks (comma-separated, e.g. 192.168.1.0/24,192.168.2.0/24): "
            ).strip()

        elif command == "reverse":
            args.hosts = input("Hosts (comma-separated, e.g. 100,50,25): ").strip()
            args.ip_version = input("IP version (v4/v6) [v4]: ").strip() or "v4"

        elif command == "overlap":
            args.networks = input("Networks (comma-separated): ").strip()

        elif command == "eui64":
            args.mac = input("MAC address (e.g. 00:11:22:33:44:55): ").strip()
            args.prefix = input("IPv6 prefix (e.g. 2001:db8::/64): ").strip()

        elif command == "summarize":
            args.networks = input(
                "Networks (comma-separated, e.g. 192.168.1.0/24,192.168.2.0/24): "
            ).strip()

        elif command == "range":
            args.network = input(
                "Enter CIDR network or leave blank to use range conversion: "
            ).strip()
            if not args.network:
                args.start = input("Start IP: ").strip()
                args.end = input("End IP: ").strip()

        elif command == "compare":
            args.network1 = input("First network CIDR: ").strip()
            args.network2 = input("Second network CIDR: ").strip()

        elif command == "expand":
            args.address = input("IPv6 address to expand: ").strip()

        elif command == "compress":
            args.address = input("IPv6 address to compress: ").strip()

        # Output options
        format_choice = (
            input("Output format (text/table/json/csv/markdown/pretty) [text]: ")
            .strip()
            .lower()
        )
        if format_choice in ["table", "json", "csv", "markdown", "pretty"]:
            args.format = format_choice
            if format_choice in ["json", "csv", "markdown"]:
                args.output = input("Output file path: ").strip() or None
    except EOFError:
        print("\nInput ended early. Using defaults for remaining options.")
        # Use defaults for missing inputs
        if command == "count" and not hasattr(args, "network"):
            args.network = "192.168.1.0/24"
            args.ip_version = "v4"
        elif command == "vlsm" and not hasattr(args, "network"):
            args.network = "10.0.0.0/16"
            args.hosts = "500,200"
            args.ip_version = "v4"
        # Add similar defaults for other commands if needed

    return args


def handle_reverse(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the reverse command by finding the smallest subnet for hosts."""
    host_reqs = [int(h.strip()) for h in args.hosts.split(",") if h]
    for h in host_reqs:
        validate_host_count(h)
    prefix = find_smallest_subnet(tuple(host_reqs), args.ip_version)
    result = f"Smallest subnet for {host_reqs} hosts: /{prefix}"
    data = [{"hosts": ",".join(map(str, host_reqs)), "prefix": prefix}]
    if format_type == "json":
        output_json([{"hosts": host_reqs, "prefix": prefix}], output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(result)


def handle_overlap(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the overlap command by checking for intersecting networks."""
    networks = [n.strip() for n in args.networks.split(",")]
    for net in networks:
        validate_cidr(net)
    overlaps, msg = check_overlap(networks)
    data = [{"networks": ",".join(networks), "overlaps": overlaps, "message": msg}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(msg)


def handle_eui64(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the eui64 command by generating an IPv6 EUI-64 address."""
    validate_cidr(args.prefix)
    ipv6_addr = generate_eui64(args.mac, args.prefix)
    result = f"EUI-64 IPv6 address: {ipv6_addr}"
    data = [{"mac": args.mac, "prefix": args.prefix, "eui64_address": str(ipv6_addr)}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(result)


def handle_supernet(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the supernet command by finding the smallest covering supernet."""
    nets = []
    for n in args.networks.split(","):
        nets.append(validate_cidr(n.strip()))
    supernet = find_supernet(nets)
    data = [{"networks": args.networks, "supernet": str(supernet)}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(f"Supernet for {args.networks}: {supernet}")
        print_subnet_details(
            supernet, format_type=format_type, output_file=output_file, verbose=verbose
        )


def handle_version(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the version command by printing release metadata."""
    data = {
        "package": "subnet-calculator",
        "version": __version__,
        "python": sys.version.split()[0],
    }
    if format_type == "json":
        output_json([data], output_file)
    elif format_type == "csv":
        output_csv([data], output_file)
    elif format_type == "markdown":
        output_markdown([data], output_file)
    elif format_type == "pretty":
        output_pretty([data], output_file)
    else:
        print(f"subnet-calc version {__version__}")
        print(f"Python: {data['python']}")


def handle_summarize(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the summarize command by finding the minimal covering supernet."""
    nets = [validate_cidr(n.strip()) for n in args.networks.split(",")]
    supernet = find_supernet(nets)
    data = [{"networks": args.networks, "supernet": str(supernet)}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(f"Summarize supernet for {args.networks}: {supernet}")
        print_subnet_details(
            supernet, format_type=format_type, output_file=output_file, verbose=verbose
        )


def handle_range(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the range command for CIDR/range conversion."""
    if getattr(args, "network", None):
        network = validate_cidr(args.network)
        first_host, last_host, total = network_to_range(network)
        data = [
            {
                "network": str(network),
                "first_host": first_host,
                "last_host": last_host,
                "total_addresses": total,
            }
        ]
    elif getattr(args, "start", None) and getattr(args, "end", None):
        nets = summarize_address_range(args.start, args.end)
        data = [{"summary": ", ".join(str(net) for net in nets), "count": len(nets)}]
    else:
        raise ValueError("Provide either --network or both --start and --end")

    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        if getattr(args, "network", None):
            print(f"Network: {args.network}")
            print(f"First host: {first_host}")
            print(f"Last host: {last_host}")
            print(f"Total addresses: {total}")
        else:
            print(f"Summarized networks: {data[0]['summary']}")
            print(f"CIDR count: {data[0]['count']}")


def handle_compare(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the compare command by checking network relationship."""
    message = compare_networks(args.network1, args.network2)
    data = [
        {
            "network1": args.network1,
            "network2": args.network2,
            "relationship": message,
        }
    ]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(message)


def handle_expand(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the expand command for IPv6 address formatting."""
    expanded = expand_ipv6(args.address)
    data = [{"address": args.address, "expanded": expanded}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(f"Expanded IPv6: {expanded}")


def handle_compress(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the compress command for IPv6 address formatting."""
    compressed = compress_ipv6(args.address)
    data = [{"address": args.address, "compressed": compressed}]
    if format_type == "json":
        output_json(data, output_file)
    elif format_type == "csv":
        output_csv(data, output_file)
    elif format_type == "markdown":
        output_markdown(data, output_file)
    elif format_type == "pretty":
        output_pretty(data, output_file)
    else:
        print(f"Compressed IPv6: {compressed}")


def handle_count(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the count command for subnet details, splitting, or VLSM."""
    # Auto-detect version if not specified
    ip_net = validate_cidr(args.network)

    if getattr(args, "hosts", None):
        handle_vlsm(ip_net, args.hosts, format_type, output_file, verbose)
        return

    if (
        getattr(args, "prefix", None) is not None
        or getattr(args, "count", None) is not None
    ):
        if getattr(args, "count", None) is not None:
            validate_host_count(args.count)
        subnets = calculate_subnets(
            ip_net,
            count=getattr(args, "count", None),
            prefix=getattr(args, "prefix", None),
        )
        if getattr(args, "count", None) is not None:
            new_pl = ip_net.prefixlen + math.ceil(math.log2(args.count))
            num = args.count
        else:
            new_pl = args.prefix
            num = 2 ** (new_pl - ip_net.prefixlen)
        if format_type in ["json", "csv", "table", "markdown", "pretty"]:
            subnet_data = []
            for i, subnet in enumerate(subnets):
                data = get_subnet_data(subnet, i)
                data["split_info"] = f"{num} /{new_pl} subnets"
                subnet_data.append(data)
            if format_type == "json":
                output_json(subnet_data, output_file)
            elif format_type == "csv":
                output_csv(subnet_data, output_file)
            elif format_type == "table":
                output_table(subnet_data, output_file)
            elif format_type == "markdown":
                output_markdown(subnet_data, output_file)
            elif format_type == "pretty":
                output_pretty(subnet_data, output_file)
        else:
            print(f"Split {ip_net} into {num} /{new_pl} subnets:")
            for i, subnet in enumerate(subnets):
                print_subnet_details(
                    subnet,
                    i,
                    format_type=format_type,
                    output_file=output_file,
                    verbose=verbose,
                )
    else:
        print_subnet_details(
            ip_net, format_type=format_type, output_file=output_file, verbose=verbose
        )


def handle_vlsm_command(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle the vlsm command by parsing and allocating hosts into subnets."""
    ip_net = validate_cidr(args.network)
    handle_vlsm(ip_net, args.hosts, format_type, output_file, verbose)


def dispatch_command(
    args: argparse.Namespace,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Dispatch a parsed command to the appropriate handler."""
    command_handlers = {
        "reverse": handle_reverse,
        "overlap": handle_overlap,
        "eui64": handle_eui64,
        "supernet": handle_supernet,
        "summarize": handle_summarize,
        "range": handle_range,
        "compare": handle_compare,
        "expand": handle_expand,
        "compress": handle_compress,
        "version": handle_version,
        "count": handle_count,
        "vlsm": handle_vlsm_command,
    }
    if args.command in command_handlers:
        command_handlers[args.command](args, format_type, output_file, verbose)
    else:
        raise ValueError(f"Unknown command: {args.command}")


def main() -> int:
    """Entry point for the CLI.

    Returns:
        Exit status code (0 for success, 1 for failure).
    """
    parser, args = parse_arguments()

    # Interactive mode
    if args.interactive:
        config = load_config(args.config)
        args = interactive_mode(config)
        # Re-load config if specified in interactive
        config = load_config(args.config)

    # Load config
    config = load_config(args.config)

    # Apply scenario if provided
    apply_scenario(args, config)

    # Resolve presets
    resolve_presets(args, config)

    # Resolve input file values if provided
    resolve_input_args(args)
    validate_required_args(args)

    # Determine output options
    verbose = args.verbose and not args.quiet
    format_type = args.format
    output_file = args.output

    # Handle no subcommand by warning user and suggesting -h
    if not hasattr(args, "command") or args.command is None:
        print(
            "Error: No command provided. Use -h to see the available commands.",
            file=sys.stderr,
        )
        return 1

    # if output_file is None and format_type in ["json", "csv", "markdown"]:
    #     output_file = f"subnet-calc-{args.command}.{ 'md' if format_type == 'markdown' else format_type }"
    #     if not args.quiet:
    #         print(f"Writing output to {output_file}")

    if output_file is None and format_type in ["json", "csv", "markdown"]:
        ext = "md" if format_type == "markdown" else format_type
        output_file = f"subnet-calc-{args.command}.{ext}"
        if not args.quiet:
            print(f"Writing output to {output_file}")

    try:
        dispatch_command(args, format_type, output_file, verbose)
        return 0
    except SubnetCalculatorError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ipaddress.AddressValueError as e:
        print(f"Invalid network address: {e}", file=sys.stderr)
        return 1
    except ipaddress.NetmaskValueError as e:
        print(f"Invalid netmask: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
