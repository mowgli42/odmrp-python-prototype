Feature: JREAP-A situational-awareness feed
  A node expresses interest; the gateway evaluates the DataPlan and may mint
  a ProductLocation at the thin JREAP-A endpoint. SA bytes move over tunnels;
  FG forwarders consume locally without opening a second endpoint connection.

  Scenario: Interest leads to ProductLocation and mock SA stream
    Given the overlay-mesh scenario has settled with FG formed
    When node 3 expresses interest in Link16-JREAP-A
    Then the gateway authorizes node 3 and mints a ProductLocation
    And the ProductLocation URI points at the thin JREAP endpoint
    When the gateway pumps the SA feed
    Then node 3 has consumed SA bytes
    And only the gateway opened the JREAP endpoint connection

  Scenario: Forwarder consumes without a second connection
    Given the overlay-mesh scenario has settled with FG formed
    And node 3 has an authorized Link16-JREAP-A subscription
    When the gateway pumps the SA feed
    Then FG forwarder node 1 consumes the stream locally
    And node 1 did not open a second JREAP endpoint connection
    And node 1 forwarded SA chunks downstream toward node 3
