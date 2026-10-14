# Messaging and File Transfer Capability

## Overview
Users (or tests) can inject text messages or files into a source node destined for a multicast group. The ODMRP layer delivers them to all current group members via the forwarding mesh. File transfers are chunked and reassembled at receivers.

## ADDED Requirements

### Requirement: Text message can be sent to a multicast group
The system SHALL allow a source node to send a text message to a named multicast group. All current members of that group that are reachable via the ODMRP mesh SHALL receive the message.

#### Scenario: Message delivered to group members
```gherkin
Given nodes R1 and R2 have joined multicast group "chat"
And source S has established a forwarding group to "chat"
When S sends the text message "hello team"
Then R1 receives "hello team"
And R2 receives "hello team"
```

### Requirement: File can be transferred to a multicast group
The system SHALL allow a source to send a file (up to a prototype limit, e.g. 1 MB) to a multicast group. Receivers SHALL reassemble the file and make it available for download.

#### Scenario: Small file is delivered intact
```gherkin
Given R1 has joined group "files"
And S has a 10 KB file "demo.txt"
When S initiates a file transfer of "demo.txt" to group "files"
Then R1 eventually receives a complete, byte-identical copy of "demo.txt"
```

### Requirement: Delivery status is observable
The system SHALL report, for each injected message or file transfer, which receivers successfully obtained it and the path(s) taken (for debugging).

#### Scenario: Delivery report lists receivers
```gherkin
Given a message was sent to group "chat"
When the delivery report is requested
Then the report lists every receiver that obtained the message
```
