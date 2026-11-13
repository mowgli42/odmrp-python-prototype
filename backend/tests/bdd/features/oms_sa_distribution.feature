Feature: OMS SA distribution over ODMRP
  Peer OMS system status (1/20 Hz) and position (1/5 Hz) on group oms.sa
  without Join Query storms after mesh_established (ADR-008).

  Scenario: Subsequent position reports are pure DATA
    Given an overlay mesh with oms.sa members and an established source mesh
    When the source originates oms_position reports
    Then those packets have no Join Query header
    And only Forwarding Group members rebroadcast them

  Scenario: Mesh refresh still emits Join Query on interval
    Given an established oms.sa mesh with ongoing pure DATA positions
    When ROUTE_REFRESH_INTERVAL elapses
    Then a Join Query is originated for oms.sa

  Scenario: Multi-source status delivery without re-originate
    Given the oms-sa-mesh scenario with multiple active publishers
    When the simulation settles through formation and a pure DATA burst
    Then each member has peer OMS views
    And the pure DATA burst does not increase Join Query flood count

  Scenario: Reject unsafe production rates
    Given a production OMS SA configuration
    When status_period_s is set below 1.0
    Then configuration validation fails
