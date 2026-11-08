"""Share text for WhatsApp and the Copy button, built from an `Item` (api/openapi.yaml)."""

from urllib.parse import quote

WHATSAPP_URL = "https://wa.me/?text="


def share_text(item: dict) -> str:
    """Title, note (if any) and URL, one per line; the URL once if it is the title."""
    url = item["url"]
    lines = [] if item["title"] == url else [item["title"]]
    if item.get("note"):
        lines.append(item["note"])
    lines.append(url)
    return "\n".join(lines)


def whatsapp_url(item: dict) -> str:
    return WHATSAPP_URL + quote(share_text(item), safe="")
