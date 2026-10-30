"""Parser for .eml files to extract security-relevant headers and body content."""

import email
from email import policy
import re
from typing import Any, Dict, List
from html.parser import HTMLParser


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: List[Dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for k, v in attrs:
                if k.lower() == "href":
                    self._current_href = v
                    self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href is not None:
            text = "".join(self._current_text).strip()
            self.links.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._current_text = []


def parse_eml_bytes(data: bytes) -> Dict[str, Any]:
    msg = email.message_from_bytes(data, policy=policy.default)

    subject = str(msg.get("Subject", "") or "").strip()
    sender = str(msg.get("From", "") or "").strip()
    reply_to = str(msg.get("Reply-To", "") or "").strip()
    return_path = str(msg.get("Return-Path", "") or "").strip()
    date_header = str(msg.get("Date", "") or "").strip()

    # Authentication headers (SPF, DKIM, DMARC)
    auth_header = str(msg.get("Authentication-Results", "") or "")
    rec_spf = str(msg.get("Received-SPF", "") or "")

    spf_status = "none"
    dkim_status = "none"
    dmarc_status = "none"

    full_auth = f"{auth_header} {rec_spf}".lower()
    if "spf=pass" in full_auth or "pass" in rec_spf.lower():
        spf_status = "pass"
    elif "spf=fail" in full_auth or "softfail" in full_auth or "fail" in rec_spf.lower():
        spf_status = "fail"

    if "dkim=pass" in full_auth:
        dkim_status = "pass"
    elif "dkim=fail" in full_auth:
        dkim_status = "fail"

    if "dmarc=pass" in full_auth:
        dmarc_status = "pass"
    elif "dmarc=fail" in full_auth:
        dmarc_status = "fail"

    # Extract body content (prefers plain, falls back to html)
    body_text = ""
    html_content = ""
    try:
        plain_part = msg.get_body(preferencelist=("plain",))
        if plain_part:
            body_text = plain_part.get_content()
    except Exception:
        pass

    try:
        html_part = msg.get_body(preferencelist=("html",))
        if html_part:
            html_content = html_part.get_content()
            if not body_text:
                # Strip HTML tags simply if plain text was missing
                body_text = re.sub(r"<[^>]+>", " ", html_content)
                body_text = re.sub(r"\s+", " ", body_text).strip()
    except Exception:
        pass

    if not body_text and not html_content:
        # Fallback raw walk
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not body_text:
                try:
                    body_text = part.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    pass
            elif content_type == "text/html" and not html_content:
                try:
                    html_content = part.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    pass

    # Link discrepancies inspection
    links: List[Dict[str, Any]] = []
    suspicious_links: List[Dict[str, Any]] = []
    if html_content:
        parser = LinkExtractor()
        try:
            parser.feed(html_content)
            links = parser.links
        except Exception:
            pass

    for link in links:
        href = link["href"].strip()
        text = link["text"].strip()
        # Check if text looks like a URL (e.g. https://paypal.com) but points elsewhere
        url_match = re.match(r"^https?://([^/]+)", text, re.IGNORECASE)
        href_match = re.match(r"^https?://([^/]+)", href, re.IGNORECASE)
        if url_match and href_match:
            display_host = url_match.group(1).lower().replace("www.", "")
            actual_host = href_match.group(1).lower().replace("www.", "")
            if display_host != actual_host and not actual_host.endswith(f".{display_host}"):
                suspicious_links.append({
                    "display": text,
                    "target": href,
                    "reason": f"Link text displays '{display_host}' but points to '{actual_host}'"
                })

    # Display name spoof check (e.g. "Paypal Support <hacker@gmail.com>")
    name_spoof = False
    sender_lower = sender.lower()
    famous_brands = ["paypal", "microsoft", "google", "apple", "amazon", "netflix", "bank", "support", "admin"]
    for brand in famous_brands:
        if brand in sender_lower and not sender_lower.endswith(f"@{brand}.com") and f"@{brand}." not in sender_lower:
            # If brand is in display name but actual email domain doesn't match
            if "<" in sender:
                display_name = sender.split("<")[0].lower()
                email_addr = sender.split("<")[1].lower()
                if brand in display_name and brand not in email_addr:
                    name_spoof = True
                    break

    # Attachments
    attachments = []
    for part in msg.walk():
        fn = part.get_filename()
        if fn:
            attachments.append(fn)

    return {
        "subject": subject,
        "from": sender,
        "reply_to": reply_to,
        "return_path": return_path,
        "date": date_header,
        "spf": spf_status,
        "dkim": dkim_status,
        "dmarc": dmarc_status,
        "name_spoof": name_spoof,
        "suspicious_links": suspicious_links,
        "attachments": attachments,
        "body_preview": body_text[:400] + ("..." if len(body_text) > 400 else ""),
        "full_body": body_text,
    }
