Feature: ODMRP over IPsec tunnel overlay (unicast-over-neighbors)
  Neighbor-send unicasts the same packet once per active tunnel peer.
  Join Query / Join Reply / FG / duplicate-cache logic is unchanged;
  data is forwarded only by current FG members, still via neighbor-send.

  Scenario: Tunnel mode TX is unicast over address-book peers only
    Given the overlay-mesh scenario is loaded in tunnel mode
    When the simulation settles
    Then every transmission uses mode unicast_over_neighbors
    And source 0 unicasts only to its address-book tunnel peers
    And no transmission lists a peer outside the sender's active neighbor set

  Scenario: Sparse FG mesh delivers data without IP multicast
    Given the overlay-mesh scenario is loaded in tunnel mode
    When the simulation settles
    Then the neighbor graph is not a full mesh
    And receivers 3 and 5 have delivered the overlay text payload
    And non-FG node 4 does not forward DATA for group "demo"
    And FG members for "demo" are among the relay nodes
