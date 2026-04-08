import ipaddress
import pytest

from subnet_utils import (
    calculate_subnets,
    find_smallest_subnet,
    check_overlap,
    find_supernet,
    generate_eui64,
    handle_vlsm,
    parse_hosts,
    InvalidCIDRError,
    InvalidHostCountError,
    MixedIPVersionError,
    validate_cidr,
    validate_host_count,
    validate_hosts_in_network,
    NetworkCapacityError,
    get_classful,
    get_subnet_data,
    output_text,
    output_json,
    output_csv,
    output_table,
)


def test_calculate_subnets_iterator():
    network = ipaddress.ip_network("192.168.0.0/24")
    subnets = calculate_subnets(network, count=4)
    assert hasattr(subnets, "__iter__")
    assert not isinstance(subnets, list)
    subnets_list = list(subnets)
    assert len(subnets_list) == 4
    assert subnets_list[0].prefixlen == 26


def test_calculate_subnets_prefix():
    network = ipaddress.ip_network("192.168.0.0/24")
    subnets = list(calculate_subnets(network, prefix=26))
    assert len(subnets) == 4
    assert subnets[0].prefixlen == 26


def test_parse_hosts_named():
    hosts, names = parse_hosts("servers:100,clients:50")
    assert hosts == [100, 50]
    assert names == ["servers", "clients"]


def test_parse_hosts_invalid():
    with pytest.raises(InvalidHostCountError):
        parse_hosts("badcount")


def test_vlsm_allocation_output(capsys):
    network = ipaddress.ip_network("192.168.0.0/24")
    handle_vlsm(
        network, "app:50,db:20", format_type="text", output_file=None, verbose=False
    )
    captured = capsys.readouterr()
    assert "VLSM for app:50,db:20 in 192.168.0.0/24:" in captured.out
    assert "app" in captured.out
    assert "db" in captured.out


def test_find_supernet_ipv4():
    nets = [
        ipaddress.ip_network("192.168.1.0/24"),
        ipaddress.ip_network("192.168.2.0/24"),
    ]
    supernet = find_supernet(nets)
    assert supernet.prefixlen == 22
    assert str(supernet) == "192.168.0.0/22"


def test_generate_eui64():
    address = generate_eui64("00:11:22:33:44:55", "2001:db8::/64")
    assert str(address).startswith("2001:db8")


def test_generate_eui64_invalid_mac():
    with pytest.raises(InvalidCIDRError):
        generate_eui64("00:11:22:33:44", "2001:db8::/64")


def test_check_overlap_false():
    overlaps, message = check_overlap(["192.168.1.0/24", "192.168.2.0/24"])
    assert overlaps is False
    assert "No overlaps" in message


def test_check_overlap_true():
    overlaps, message = check_overlap(["192.168.1.0/24", "192.168.1.128/25"])
    assert overlaps is True
    assert "overlaps" in message


def test_check_overlap_mixed_versions():
    with pytest.raises(MixedIPVersionError):
        check_overlap(["192.168.1.0/24", "2001:db8::/32"])


def test_find_smallest_subnet_cached():
    assert find_smallest_subnet((100, 10), "v4") == 25
    assert find_smallest_subnet((100, 10), "v4") == 25


def test_validate_cidr():
    net = validate_cidr("192.168.1.0/24")
    assert str(net) == "192.168.1.0/24"


def test_validate_cidr_invalid():
    with pytest.raises(InvalidCIDRError):
        validate_cidr("invalid")


def test_validate_host_count():
    validate_host_count(10)


def test_validate_host_count_negative():
    with pytest.raises(InvalidHostCountError):
        validate_host_count(-1)


def test_validate_hosts_in_network():
    network = ipaddress.ip_network("192.168.1.0/24")
    validate_hosts_in_network(network, [10, 20])


def test_validate_hosts_in_network_exceed():
    network = ipaddress.ip_network("192.168.1.0/24")
    with pytest.raises(NetworkCapacityError):
        validate_hosts_in_network(network, [1000])


def test_get_classful():
    assert get_classful(24) == 'Class C (/17-/24)'


def test_get_subnet_data():
    network = ipaddress.ip_network("192.168.1.0/24")
    data = get_subnet_data(network)
    assert data['network'] == '192.168.1.0/24'
    assert data['version'] == 'IPv4'


def test_output_text(capsys):
    data = {'index': '1', 'name': 'test', 'network': '192.168.1.0/24', 'version': 'IPv4', 'class': 'Class C (/17-/24)', 'netmask': '255.255.255.0', 'broadcast': '192.168.1.255', 'total_addresses': 256, 'usable_hosts': 254, 'first_host': '192.168.1.1', 'last_host': '192.168.1.254'}
    output_text(data, verbose=True)
    captured = capsys.readouterr()
    assert 'Network: 192.168.1.0/24' in captured.out


def test_output_json(capsys):
    data_list = [{'network': '192.168.1.0/24'}]
    output_json(data_list)
    captured = capsys.readouterr()
    assert '"network": "192.168.1.0/24"' in captured.out


def test_output_csv(capsys):
    data_list = [{'network': '192.168.1.0/24', 'version': 'IPv4'}]
    output_csv(data_list)
    captured = capsys.readouterr()
    assert 'network,version' in captured.out


def test_find_supernet_ipv6():
    nets = [ipaddress.ip_network("2001:db8::/32"), ipaddress.ip_network("2001:db9::/32")]
    supernet = find_supernet(nets)
    assert supernet.prefixlen == 31

