from odmrp_sim.protocol import seqnum


def test_fresher():
    assert seqnum.is_fresher(11, 10)
    assert not seqnum.is_fresher(10, 11)
    assert not seqnum.is_fresher(10, 10)


def test_wraparound():
    assert seqnum.is_fresher(0, 0xFFFFFFFF)
    assert not seqnum.is_fresher(0xFFFFFFFF, 0)
