import json
import pytest

from trackingmap_agent.trackingmap_agent import on_message


class DummyMQTTMessage:
    def __init__(self, payload: bytes):
        self.payload = payload


def test_on_message_ignores_invalid_json(caplog):
    msg = DummyMQTTMessage(b"{invalid-json}")

    on_message(None, None, msg)

    assert "Json Decoding error" in caplog.text


def test_on_message_ignores_missing_uplink_payload(caplog):
    payload = {
        "end_device_ids": {"device_id": "test-device"},
        "uplink_message": {"decoded_payload": {}}
    }
    msg = DummyMQTTMessage(json.dumps(payload).encode("utf-8"))

    on_message(None, None, msg)

    assert "Error in message processing" in caplog.text
    assert "uplink_message.decoded_payload.messages is empty or missing" in caplog.text
