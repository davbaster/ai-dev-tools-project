"""Share text and WhatsApp link, without a server."""

from frontend.share import share_text, whatsapp_url


def item(title, url="https://example.com/a", note=None):
    return {"title": title, "url": url, "note": note}


def test_title_note_and_url_one_per_line():
    text = share_text(item("Un artículo", note="Para Luis: te va a gustar"))
    assert text == "Un artículo\nPara Luis: te va a gustar\nhttps://example.com/a"


def test_without_note():
    assert share_text(item("Un artículo")) == "Un artículo\nhttps://example.com/a"


def test_url_appears_once_when_it_is_the_title():
    url = "https://example.com/a"
    assert share_text(item(url, url=url)) == url
    assert share_text(item(url, url=url, note="Mirá")) == f"Mirá\n{url}"


def test_special_characters_are_kept():
    text = share_text(item('Canción "<b>" & más 🎵', note="línea #1?"))
    assert text.startswith('Canción "<b>" & más 🎵\nlínea #1?\n')


def test_whatsapp_url_encodes_everything():
    link = whatsapp_url(
        item("A & B #1", url="https://example.com/?q=1&r=2", note="Hola Ana")
    )
    assert link == (
        "https://wa.me/?text=A%20%26%20B%20%231%0AHola%20Ana%0A"
        "https%3A%2F%2Fexample.com%2F%3Fq%3D1%26r%3D2"
    )


def test_whatsapp_url_encodes_accents_and_emoji():
    assert whatsapp_url(item("Canción 🎵")).startswith(
        "https://wa.me/?text=Canci%C3%B3n%20%F0%9F%8E%B5%0A"
    )
