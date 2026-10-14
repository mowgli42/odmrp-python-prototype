from odmrp_sim.model.topology import Topology


def test_neighbors_within_range():
    t = Topology(default_range=100)
    t.add(0, 0, 0)
    t.add(1, 50, 0)
    assert t.neighbors_of(0) == {1}
    assert t.neighbors_of(1) == {0}


def test_not_neighbors_outside_range():
    t = Topology(default_range=100)
    t.add(0, 0, 0)
    t.add(1, 150, 0)
    assert t.neighbors_of(0) == set()


def test_basic_mesh_links():
    t = Topology(default_range=130)
    coords = [
        (0, 100, 200),
        (1, 200, 120),
        (2, 200, 280),
        (3, 300, 120),
        (4, 300, 280),
        (5, 400, 200),
    ]
    for i, x, y in coords:
        t.add(i, x, y)
    links = {tuple(sorted(e)) for e in t.links()}
    expected = {(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5)}
    assert links == expected
