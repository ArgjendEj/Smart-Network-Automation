from services.subnet_calculator import plan_departments, prefix_for_users


def test_prefix_sizing():
    assert prefix_for_users(2) == 30      # 2 hosts -> /30 (2 usable)
    assert prefix_for_users(50) == 26     # needs 52 -> 64 -> /26
    assert prefix_for_users(100) == 25    # needs 102 -> 128 -> /25
    assert prefix_for_users(500) == 23   # 502 -> 512 -> /23


def test_plan_no_overlap_and_vlan_ids():
    plan = plan_departments(
        [("Sales", 100), ("IT", 20), ("HR", 10)], base_pool="10.10.0.0/16", vlan_start=10
    )
    nets = [d.network for d in plan.departments]
    assert [d.vlan_id for d in plan.departments] == [10, 20, 30]
    for i, a in enumerate(nets):
        for b in nets[i + 1 :]:
            assert not a.overlaps(b), f"{a} overlaps {b}"


def test_gateway_and_dhcp_range():
    plan = plan_departments([("Sales", 100)], base_pool="10.10.0.0/16")
    d = plan.departments[0]
    assert str(d.gateway).endswith(".1")
    assert d.network.prefixlen == 25
    assert d.dhcp_end in d.network


def test_pool_too_small_raises():
    try:
        plan_departments([("Big", 5000)], base_pool="192.168.1.0/28")
    except ValueError:
        return
    raise AssertionError("expected ValueError for undersized pool")
