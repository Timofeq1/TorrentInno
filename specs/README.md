# The overall flow

1) The peer announces itself to the tracker. In order to do that, the peer 
a) computes the *info-hash* of the `torrentinno` file. The details on computation can be found in the client `core.common.Resource` class (method `get_info_hash`).
b) sends the http query with `peer-announce.json` as request body.

2) The tracker accepts the peer request and returns the list of all currently online peers that have sent the announcement to the tracker with the same *info-hash*. The server response body is formatted according to `tracker-response.json`

3) After that, the peer maintains the connection with tracker. And periodically (around 30 seconds) repeats the announcement. If the tracker detects that some peer hasn't announced itself with `info-hash` for certain time, then it stops sending that peer in response to other peers' announcements.

4) Once the peer receives the list of peers, it begins communicating with them. The details on that communication are in `peer-message-exchange.md`.