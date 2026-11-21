# SDP sync fixtures (#195)

- `product_repo/`: a product repository as the sender sees it (`.draft/sdp.yaml`).
- `central_workspace/`: the central DRAFT workspace as the receiver sees it, with the
  `ProductRegistration` for `example-org/absence-service` and the component the SDP places.

Tests copy both to a temporary directory; nothing here is changed by a test run.
