"""Titles as stored, with and without the demo flag BUG_SAVE_ITEM (#19)."""

import pytest

from backend.items import display_title

LONG = "Un artículo muy largo sobre cómo guardar cosas para leer más tarde"


def test_titles_are_kept_as_typed_by_default(monkeypatch):
    monkeypatch.delenv("BUG_SAVE_ITEM", raising=False)
    assert display_title(LONG) == LONG
    monkeypatch.setenv("BUG_SAVE_ITEM", "yes")  # solo "1" lo activa
    assert display_title(LONG) == LONG


def test_short_titles_are_unchanged_with_the_flag(monkeypatch):
    monkeypatch.setenv("BUG_SAVE_ITEM", "1")
    assert display_title("Corto") == "Corto"


def test_long_titles_fail_with_the_flag(monkeypatch):
    # El bug de la demo (#19): la respuesta de guardia lo encuentra y lo arregla.
    monkeypatch.setenv("BUG_SAVE_ITEM", "1")
    with pytest.raises(IndexError):
        display_title(LONG)
