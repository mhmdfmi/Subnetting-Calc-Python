"""
Subnet Calculator Utilities
Utility functions for subnet calculations and output.
"""

import ipaddress
import itertools
import math
import json
import csv
import sys
from functools import lru_cache
from typing import List, Tuple, Optional, Union, Dict, Any, Iterator, cast

try:
    from tabulate import tabulate  # type: ignore[import]

    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False
try:
    from rich.console import Console  # type: ignore[import]
    from rich.table import Table  # type: ignore[import]

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    import openpyxl  # type: ignore[import]

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# Custom Exceptions
class SubnetCalculatorError(Exception):
    """Base exception for subnet calculator errors."""

    pass


class InvalidCIDRError(SubnetCalculatorError):
    """Raised when an invalid CIDR is provided."""

    pass


class InvalidHostCountError(SubnetCalculatorError):
    """Raised when invalid host count is provided."""

    pass


class NetworkCapacityError(SubnetCalculatorError):
    """Raised when hosts exceed network capacity."""

    pass


class VLSMExceedError(SubnetCalculatorError):
    """Raised when VLSM allocation exceeds parent network."""

    pass


class MixedIPVersionError(SubnetCalculatorError):
    """Raised when mixing IPv4 and IPv6 networks."""

    pass


def validate_cidr(cidr: str) -> Union[ipaddress.IPv4Network, ipaddress.IPv6Network]:
    """Validate and parse CIDR notation."""
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        raise InvalidCIDRError(f"Invalid CIDR '{cidr}': {e}")


def validate_host_count(count: int) -> None:
    """Validate host count."""
    if count <= 0:
        raise InvalidHostCountError(f"Host count must be positive, got {count}")
    if count > 2**31:  # Reasonable upper limit
        raise InvalidHostCountError(f"Host count too large: {count}")


def validate_hosts_in_network(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network], hosts: List[int]
) -> None:
    """Validate that hosts can fit in the network."""
    total_hosts_needed = sum(hosts)
    max_hosts = network.num_addresses - (
        2 if network.version == 4 else 1
    )  # Reserve network and broadcast for IPv4, network for IPv6
    if total_hosts_needed > max_hosts:
        raise NetworkCapacityError(
            f"Total hosts ({total_hosts_needed}) exceed network capacity ({max_hosts}) for {network}"
        )


def validate_vlsm_allocation(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network], hosts: List[int]
) -> None:
    """Validate VLSM allocation doesn't exceed the parent network.

    This checks whether the requested subnets can fit inside the parent network
    before any allocations occur.

    Parameters:
        network: Parent IPv4 or IPv6 network.
        hosts: A list of required host counts for each subnet.

    Raises:
        VLSMExceedError: If the parent network cannot allocate one or more subnets.
    """
    remaining: Union[ipaddress.IPv4Network, ipaddress.IPv6Network] = network
    for req in sorted(hosts, reverse=True):
        bits = math.ceil(math.log2(req + (2 if network.version == 4 else 1)))
        prefix = remaining.max_prefixlen - bits
        if prefix < network.prefixlen:
            raise VLSMExceedError(
                f"VLSM allocation requires prefix /{prefix} but parent is /{network.prefixlen}"
            )
        try:
            if isinstance(remaining, ipaddress.IPv4Network):
                subnet = next(remaining.subnets(new_prefix=prefix))
                remaining = next(remaining.address_exclude(subnet))
            else:
                subnet = next(remaining.subnets(new_prefix=prefix))
                remaining = next(remaining.address_exclude(subnet))
        except StopIteration:
            raise VLSMExceedError(
                f"Cannot allocate subnet for {req} hosts in remaining space {remaining}"
            )


def validate_mixed_versions(
    networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> None:
    """Validate no mixed IPv4/IPv6."""
    if not networks:
        return
    version = networks[0].version
    if any(net.version != version for net in networks):
        raise MixedIPVersionError("Cannot mix IPv4 and IPv6 networks")


def get_classful(prefixlen: int) -> str:
    if prefixlen > 32:
        return "N/A"
    if prefixlen <= 8:
        return "Class A (/1-/8)"
    elif prefixlen <= 16:
        return "Class B (/9-/16)"
    elif prefixlen <= 24:
        return "Class C (/17-/24)"
    elif prefixlen <= 27:
        return "Class D (/25-/27)"
    else:
        return "Class E (/28-/32)"


def get_subnet_data(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network],
    index: int = 0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get subnet data as a dictionary.

    Parameters:
        network: The IPv4 or IPv6 network to describe.
        index: Optional output index for ordered results.
        name: Optional name for the subnet, used in reporting.

    Returns:
        A dictionary with subnet details such as network address, mask,
        broadcast address, usable hosts, and host range.
    """
    total_hosts = network.num_addresses
    if isinstance(network, ipaddress.IPv4Network):
        version = "IPv4"
        broadcast = str(network.broadcast_address)
        if total_hosts > 2:
            first_host = str(network.network_address + 1)
            last_host = str(network.broadcast_address - 1)
            usable_hosts = total_hosts - 2
        else:
            first_host = None
            last_host = None
            usable_hosts = 0
        classful = get_classful(network.prefixlen)
    else:  # IPv6
        version = "IPv6"
        broadcast = None
        if total_hosts > 1:
            first_host = str(network.network_address + 1)
            last_host = str(network.broadcast_address)
            usable_hosts = total_hosts - 1
        else:
            first_host = None
            last_host = None
            usable_hosts = 0
        classful = "N/A"

    return {
        "index": index + 1 if index > 0 else "",
        "name": name or "",
        "network": str(network),
        "version": version,
        "class": classful,
        "netmask": str(network.netmask),
        "broadcast": broadcast or "",
        "total_addresses": total_hosts,
        "usable_hosts": usable_hosts,
        "first_host": first_host or "",
        "last_host": last_host or "",
    }


def print_subnet_details(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network],
    index: int = 0,
    name: Optional[str] = None,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Print subnet details in the requested format.

    Parameters:
        network: The IPv4 or IPv6 network to describe.
        index: Optional sequence index when printing multiple subnets.
        name: Optional subnet name to include in the output.
        format_type: One of 'text', 'table', 'json', or 'csv'.
        output_file: Optional file path to save the output.
        verbose: Whether to include verbose fields.
    """
    data = get_subnet_data(network, index, name)

    if format_type == "json":
        output_json([data], output_file)
    elif format_type == "csv":
        output_csv([data], output_file)
    elif format_type == "table":
        output_table([data], output_file)
    elif format_type == "markdown":
        output_markdown([data], output_file)
    elif format_type == "pretty":
        output_pretty([data], output_file)
    else:  # text
        output_text(data, verbose)


def output_text(data: Dict[str, Any], verbose: bool = True) -> None:
    """Output subnet data in plain text format.

    Parameters:
        data: Subnet data dictionary.
        verbose: Whether to include extra fields such as broadcast and host range.
    """
    prefix = f"{data['index']}" if data["index"] else ""
    if data["name"]:
        prefix = data["name"]
    label = f"{prefix} " if prefix else ""

    print(f"{label}Network: {data['network']}")
    print(f"{label}Version: {data['version']}")
    print(f"{label}Class: {data['class']}")
    print(f"{label}Netmask: {data['netmask']}")
    if data["broadcast"] and verbose:
        print(f"{label}Broadcast: {data['broadcast']}")
    print(f"{label}Total Addresses: {data['total_addresses']}")
    print(f"{label}Usable Hosts: {data['usable_hosts']}")
    if data["first_host"] and verbose:
        print(f"{label}First Host: {data['first_host']}")
    if data["last_host"] and verbose:
        print(f"{label}Last Host: {data['last_host']}")
    print()


def output_table(
    data_list: List[Dict[str, Any]], output_file: Optional[str] = None
) -> None:
    """Output subnet data in a human-readable table.

    Parameters:
        data_list: List of subnet data dictionaries.
        output_file: Optional path to write the table to.
    """
    headers = [
        "Index",
        "Name",
        "Network",
        "Version",
        "Class",
        "Netmask",
        "Broadcast",
        "Total Addresses",
        "Usable Hosts",
        "First Host",
        "Last Host",
    ]
    table_data = []
    for data in data_list:
        row = [
            data["index"] or "",
            data["name"] or "",
            data["network"],
            data["version"],
            data["class"],
            data["netmask"],
            data["broadcast"] or "",
            data["total_addresses"],
            data["usable_hosts"],
            data["first_host"] or "",
            data["last_host"] or "",
        ]
        table_data.append(row)

    if HAS_RICH:
        table = Table(show_header=True, header_style="bold cyan")
        for header in headers:
            table.add_column(header)
        for row in table_data:
            table.add_row(*[str(item) for item in row])

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                Console(file=f, force_terminal=False).print(table)
        else:
            Console().print(table)
        return

    if not HAS_TABULATE:
        print("Tabulate library not available. Install with: pip install tabulate")
        return

    table_str = tabulate(table_data, headers=headers, tablefmt="grid")

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(table_str)
    else:
        print(table_str)


def output_json(
    data_list: List[Dict[str, Any]], output_file: Optional[str] = None
) -> None:
    """Output subnet data as JSON.

    Parameters:
        data_list: List of subnet data dictionaries.
        output_file: Optional file path to write JSON to.
    """
    if output_file:
        with open(output_file, "w") as f:
            json.dump(data_list, f, indent=2)
    else:
        print(json.dumps(data_list, indent=2))


def output_csv(
    data_list: List[Dict[str, Any]], output_file: Optional[str] = None
) -> None:
    """Output subnet data as CSV.

    Parameters:
        data_list: List of subnet data dictionaries.
        output_file: Optional file path to write CSV to.
    """
    if not data_list:
        return

    fieldnames = []
    for row in data_list:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    if output_file and output_file.lower().endswith(".xlsx"):
        output_excel(data_list, output_file)
        return
    if output_file:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_list)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_list)


def output_markdown(
    data_list: List[Dict[str, Any]], output_file: Optional[str] = None
) -> None:
    """Output subnet data as Markdown."""
    if not data_list:
        return

    fieldnames: List[str] = []
    for row in data_list:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    lines: List[str] = []
    lines.append("| " + " | ".join(fieldnames) + " |")
    lines.append("| " + " | ".join(["---"] * len(fieldnames)) + " |")
    for row in data_list:
        lines.append(
            "| " + " | ".join(str(row.get(key, "")) for key in fieldnames) + " |"
        )

    content = "\n".join(lines)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content + "\n")
    else:
        print(content)


def output_pretty(
    data_list: List[Dict[str, Any]], output_file: Optional[str] = None
) -> None:
    """Output subnet data in a rich pretty/table format."""
    if not data_list:
        return

    if not HAS_RICH:
        print("Rich library not available. Install with: pip install rich")
        output_json(data_list, output_file)
        return

    fieldnames: List[str] = []
    for row in data_list:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    table = Table(show_header=True, header_style="bold magenta")
    for header in fieldnames:
        table.add_column(header)

    for row in data_list:
        table.add_row(*[str(row.get(key, "")) for key in fieldnames])

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            Console(file=f, force_terminal=False).print(table)
    else:
        Console().print(table)


def output_excel(
    data_list: List[Dict[str, Any]], output_file: str
) -> None:
    """Output subnet data as an Excel workbook."""
    if not HAS_OPENPYXL:
        raise ImportError(
            "Excel export requires openpyxl. Install with: pip install openpyxl"
        )

    workbook = openpyxl.Workbook()
    sheet = workbook.active

    fieldnames: List[str] = []
    for row in data_list:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    sheet.append(fieldnames)
    for row in data_list:
        sheet.append([row.get(key, "") for key in fieldnames])

    workbook.save(output_file)


def calculate_subnets(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network],
    count: Optional[int] = None,
    prefix: Optional[int] = None,
) -> Iterator[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Generate subnets from a parent network.

    The function returns an iterator so that large networks do not require
    storing all subnets in memory at once.

    Parameters:
        network: Parent network to split.
        count: Optional number of equal subnets to return.
        prefix: Optional target prefix length for generated subnets.

    Returns:
        An iterator over generated subnets.

    Raises:
        InvalidCIDRError: If the target prefix is invalid.
        ValueError: If neither count nor prefix is provided.
    """
    if count is not None:
        validate_host_count(count)
        prefixlen = network.prefixlen
        bits_needed = math.ceil(math.log2(count))
        new_prefix = prefixlen + bits_needed
    elif prefix is not None:
        new_prefix = prefix
    else:
        raise ValueError("Must provide --count or --prefix")

    max_prefix = 32 if isinstance(network, ipaddress.IPv4Network) else 128
    if new_prefix > max_prefix:
        raise InvalidCIDRError(f"Prefix /{new_prefix} exceeds max /{max_prefix}")
    if new_prefix < network.prefixlen:
        raise InvalidCIDRError(
            f"Cannot create subnets with prefix /{new_prefix} from /{network.prefixlen}"
        )

    subnets = network.subnets(new_prefix=new_prefix)
    if count is not None:
        return itertools.islice(subnets, count)
    return subnets


@lru_cache(maxsize=128)
def find_smallest_subnet(hosts: Tuple[int, ...], version: str = "v4") -> int:
    """Find the smallest subnet that can accommodate the given number of hosts.

    Parameters:
        hosts: A tuple of host counts.
        version: 'v4' or 'v6' to choose address family.

    Returns:
        The smallest prefix length that can support the largest host requirement.

    Example:
        >>> find_smallest_subnet((100, 50), 'v4')
        25
    """
    for h in hosts:
        validate_host_count(h)
    max_hosts = max(hosts)
    bits_needed = math.ceil(
        math.log2(max_hosts + 2)
    )  # +2 for network and broadcast in IPv4
    prefixlen = 32 - bits_needed if version == "v4" else 128 - bits_needed
    if version == "v4":
        prefixlen = max(0, min(32, prefixlen))
    else:
        prefixlen = max(0, min(128, prefixlen))
    return prefixlen


def check_overlap(networks: List[str]) -> Tuple[bool, str]:
    """Check if the given networks overlap.

    Parameters:
        networks: List of CIDR strings.

    Returns:
        A tuple (overlaps, message).
    """
    nets = []
    for net_str in networks:
        nets.append(validate_cidr(net_str))
    validate_mixed_versions(nets)
    for i, net1 in enumerate(nets):
        for j, net2 in enumerate(nets):
            if i != j and net1.overlaps(net2):
                return True, f"{net1} overlaps with {net2}"
    return False, "No overlaps found"


def generate_eui64(mac: str, prefix: str) -> ipaddress.IPv6Address:
    """Generate an IPv6 EUI-64 address from a MAC address and prefix.

    Parameters:
        mac: MAC address string like '00:11:22:33:44:55'.
        prefix: IPv6 prefix in CIDR notation.

    Returns:
        An IPv6 address generated from the prefix and MAC.
    """
    mac = mac.replace(":", "").replace("-", "")
    if len(mac) != 12:
        raise InvalidCIDRError("Invalid MAC address")
    try:
        int(mac, 16)
    except ValueError:
        raise InvalidCIDRError("Invalid MAC address format")
    eui64 = mac[:6] + "fffe" + mac[6:]
    eui64_int = int(eui64, 16) ^ 0x0200000000000000  # Flip bit 7
    ipv6_net = validate_cidr(prefix)
    if not isinstance(ipv6_net, ipaddress.IPv6Network):
        raise InvalidCIDRError("Prefix must be IPv6")
    if ipv6_net.prefixlen > 64:
        raise InvalidCIDRError("Prefix must be /64 or shorter for EUI-64")
    # Combine prefix (first 64 bits) with EUI-64 (last 64 bits)
    prefix_int = (int(ipv6_net.network_address) >> 64) << 64  # Keep upper 64 bits
    full_int = prefix_int | eui64_int
    return ipaddress.IPv6Address(full_int)


def validate_ip_address(address: str) -> Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
    """Validate a single IP address string."""
    try:
        return ipaddress.ip_address(address)
    except ValueError as e:
        raise InvalidCIDRError(f"Invalid IP address '{address}': {e}")


def network_to_range(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
) -> Tuple[str, str, int]:
    """Return the first and last usable hosts for a network."""
    total_hosts = network.num_addresses
    if isinstance(network, ipaddress.IPv4Network):
        if total_hosts > 2:
            first_host = str(network.network_address + 1)
            last_host = str(network.broadcast_address - 1)
        else:
            first_host = str(network.network_address)
            last_host = str(network.broadcast_address)
    else:
        if total_hosts > 1:
            first_host = str(network.network_address + 1)
            last_host = str(network.broadcast_address)
        else:
            first_host = str(network.network_address)
            last_host = str(network.network_address)
    return first_host, last_host, total_hosts


def summarize_address_range(
    start: str, end: str
) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Convert an IP address range into the smallest set of CIDR networks."""
    start_ip = validate_ip_address(start)
    end_ip = validate_ip_address(end)
    if type(start_ip) is not type(end_ip):
        raise MixedIPVersionError("Start and end addresses must be the same IP version")
    if int(end_ip) < int(start_ip):
        raise InvalidCIDRError("End address must be greater than or equal to start address")
    return list(ipaddress.summarize_address_range(start_ip, end_ip))


def compare_networks(net1: str, net2: str) -> str:
    """Compare two CIDR networks and describe their relationship."""
    network1 = validate_cidr(net1)
    network2 = validate_cidr(net2)
    if network1 == network2:
        return f"Networks are identical: {network1}"
    if network1.supernet_of(network2):
        return f"{network1} contains {network2}"
    if network2.supernet_of(network1):
        return f"{network2} contains {network1}"
    if network1.overlaps(network2):
        return f"Networks overlap: {network1} and {network2}"
    return f"Networks are distinct: {network1} and {network2}"


def expand_ipv6(address: str) -> str:
    """Expand an IPv6 address to full notation."""
    ip = validate_ip_address(address)
    if not isinstance(ip, ipaddress.IPv6Address):
        raise InvalidCIDRError("Address must be IPv6")
    return ip.exploded


def compress_ipv6(address: str) -> str:
    """Compress an IPv6 address to shortest notation."""
    ip = validate_ip_address(address)
    if not isinstance(ip, ipaddress.IPv6Address):
        raise InvalidCIDRError("Address must be IPv6")
    return ip.compressed


def find_supernet(
    nets: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> Union[ipaddress.IPv4Network, ipaddress.IPv6Network]:
    """Find the smallest supernet that covers all provided networks.

    Parameters:
        nets: A list of IPv4 or IPv6 networks.

    Returns:
        The smallest network containing all provided networks.
    """
    if not nets:
        raise InvalidCIDRError("No networks provided")
    validate_mixed_versions(nets)
    version = nets[0].version
    total_bits = 32 if version == 4 else 128
    min_addr = min(int(net.network_address) for net in nets)
    max_addr = max(int(net.broadcast_address) for net in nets)
    diff = min_addr ^ max_addr
    if diff == 0:
        prefixlen = total_bits
    else:
        prefixlen = total_bits - diff.bit_length()
    mask = (
        (1 << total_bits) - (1 << (total_bits - prefixlen))
        if prefixlen < total_bits
        else (1 << total_bits) - 1
    )
    network_address = min_addr & mask
    return ipaddress.ip_network((network_address, prefixlen))


def parse_hosts(hosts_str: str) -> Tuple[List[int], List[Optional[str]]]:
    """Parse hosts string into requirements and optional subnet names.

    Parameters:
        hosts_str: String like "servers:500,clients:200" or "100,50".

    Returns:
        A tuple containing a list of host counts and a parallel list of names.
    """
    host_reqs: List[int] = []
    host_names: List[Optional[str]] = []
    for h in hosts_str.split(","):
        h = h.strip()
        if ":" in h:
            name, num = h.split(":", 1)
            host_names.append(name.strip())
            try:
                num_int = int(num.strip())
                validate_host_count(num_int)
                host_reqs.append(num_int)
            except ValueError:
                raise InvalidHostCountError(f"Invalid host count '{num}' in '{h}'")
        else:
            try:
                num_int = int(h)
                validate_host_count(num_int)
                host_reqs.append(num_int)
                host_names.append(None)
            except ValueError:
                raise InvalidHostCountError(f"Invalid host count '{h}'")
    return host_reqs, host_names


def handle_vlsm(
    network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network],
    hosts_str: str,
    format_type: str = "text",
    output_file: Optional[str] = None,
    verbose: bool = True,
) -> None:
    """Handle VLSM allocation.

    Parameters:
        network: Parent network for the VLSM allocation.
        hosts_str: Hosts requirement string.
        format_type: Output format (text, table, json, csv).
        output_file: Optional output file path.
        verbose: Whether to include verbose details.
    """
    host_reqs, host_names = parse_hosts(hosts_str)
    validate_hosts_in_network(network, host_reqs)
    validate_vlsm_allocation(network, host_reqs)
    host_reqs_with_names = sorted(
        zip(host_reqs, host_names), key=lambda pair: pair[0], reverse=True
    )
    remaining = network
    title = f"VLSM for {hosts_str} in {network}:"
    print(title)

    subnet_data: List[Dict[str, Any]] = []
    for i, (req, name) in enumerate(host_reqs_with_names):
        bits = math.ceil(math.log2(req + (2 if network.version == 4 else 1)))
        prefix = remaining.max_prefixlen - bits
        if isinstance(remaining, ipaddress.IPv4Network):
            subnet = next(remaining.subnets(new_prefix=prefix))
            remaining = cast(Union[ipaddress.IPv4Network, ipaddress.IPv6Network], next(remaining.address_exclude(subnet)))
        else:
            subnet = next(remaining.subnets(new_prefix=prefix))
            remaining = cast(Union[ipaddress.IPv4Network, ipaddress.IPv6Network], next(remaining.address_exclude(subnet)))
        subnet_data.append(get_subnet_data(subnet, i, name))

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
    else:  # text
        for data in subnet_data:
            output_text(data, verbose)
