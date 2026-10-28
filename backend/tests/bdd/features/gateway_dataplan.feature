Feature: Gateway DataPlan dissemination
  The super-node gateway evaluates the active DataPlan when a product
  becomes available and announces only toward listed destinations via
  unicast-over-tunnels. A local monitor prunes destinations when tunnels drop.

  Scenario: DataPlan evaluation announces only to named destinations
    Given the overlay-mesh scenario is loaded with a gateway DataPlan
    When product prod-isr-001 of type imagery becomes available on the gateway
    Then the gateway announces product_meta and product_loc
    And announcement unicasts go only to DataPlan destinations that are connected
    And no announcement unicast targets a node outside the destination set

  Scenario: Connectivity loss updates DataPlan destinations
    Given the overlay-mesh scenario is loaded with a gateway DataPlan
    And the gateway DataPlan lists destinations 1 and 2 for imagery
    When tunnel peer 2 disconnects from the gateway
    And the gateway monitor ticks
    Then destination 2 is removed from the active DataPlan
    And a subsequent imagery product is announced only to destination 1
