import pytest
from pydantic import ValidationError

from backend.auth import RegisterRequest
from backend.security import (
    hash_password,
    hash_token,
    new_token,
    normalize_username,
    verify_password,
)


def test_password_hash_verifies_and_hides_the_password():
    stored = hash_password("correct horse")
    assert "correct horse" not in stored
    assert verify_password("correct horse", stored)


def test_wrong_password_fails():
    assert not verify_password("wrong", hash_password("correct horse"))


def test_same_password_gives_different_hashes():
    assert hash_password("same password") != hash_password("same password")


def test_garbage_hash_never_verifies():
    assert not verify_password("anything", "not-a-hash")


def test_tokens_are_random_and_stored_as_sha256():
    token = new_token()
    assert token != new_token()
    assert len(hash_token(token)) == 64
    assert token not in hash_token(token)


def test_username_is_trimmed_and_lowercased():
    assert normalize_username("  Ana.Maria ") == "ana.maria"
    assert RegisterRequest(username=" Ana ", password="12345678").username == "ana"


@pytest.mark.parametrize("username", ["ab", "a" * 51, "ana maria", "<b>ana</b>", "añá"])
def test_invalid_usernames_are_refused(username):
    with pytest.raises(ValidationError):
        RegisterRequest(username=username, password="12345678")


@pytest.mark.parametrize("password", ["1234567", "x" * 129])
def test_invalid_password_lengths_are_refused(password):
    with pytest.raises(ValidationError):
        RegisterRequest(username="ana", password=password)


def test_password_is_not_trimmed():
    assert RegisterRequest(username="ana", password="  spaces  ").password == (
        "  spaces  "
    )
