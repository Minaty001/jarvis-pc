import pytest

from jarvis.tools.confirmation import (
    hash_arguments,
    create_confirmation_token,
    verify_confirmation_token,
)


def test_confirmation_token_valid():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s1", secret, token) is True


def test_confirmation_token_tampered_args_fails():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "bob"}, "s1", secret, token) is False


def test_confirmation_token_tampered_tool_fails():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("delete_msg", {"to": "alice"}, "s1", secret, token) is False


def test_confirmation_token_tampered_session_fails():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s2", secret, token) is False


def test_confirmation_token_invalid_secret_fails():
    secret = "test-secret"
    token = create_confirmation_token("send_msg", {"to": "alice"}, "s1", secret)
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s1", "wrong-secret", token) is False


def test_hash_arguments_key_order_invariant():
    args1 = {"b": 2, "a": 1}
    args2 = {"a": 1, "b": 2}
    assert hash_arguments(args1) == hash_arguments(args2)


def test_verify_confirmation_token_invalid_token_format():
    secret = "test-secret"
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s1", secret, "invalid_token") is False
    assert verify_confirmation_token("send_msg", {"to": "alice"}, "s1", secret, "") is False
