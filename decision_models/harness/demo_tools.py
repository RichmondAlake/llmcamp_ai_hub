"""Eleven demo tools for the agent. They return canned data, except search_memory, which reads the store.

The docstrings matter: memorizz embeds them for the tool search, and the decision model reads them
as Choice options, so each one says what the tool does in plain terms.
"""

from __future__ import annotations

from typing import Any

_provider: Any = None


def bind(provider: Any) -> None:
    """Give search_memory a store to read."""
    global _provider
    _provider = provider


def search_memory(query: str) -> str:
    """Search the assistant's long-term memory for what is already known. Use it to find facts,
    agreements, names, dates and notes from earlier conversations and from ingested documents, when
    the answer depends on something stored rather than on live data."""
    from memorizz.enums import MemoryType

    rows = _provider.retrieve_by_query(query, memory_store_type=MemoryType.KNOWLEDGE_BASE, limit=3) or []
    return "\n---\n".join(str(row.get("content", "")) for row in rows) or "Nothing found."


def get_weather(city: str, day: str = "today") -> str:
    """Get the weather forecast for a place on a given day: temperature, rain, wind and snow. Use it
    for any question about current or expected conditions outdoors."""
    return f"{day} in {city}: 14C, light rain, wind 20 km/h."


def convert_currency(amount: float, source: str, target: str) -> str:
    """Convert an amount of money from one currency to another at today's exchange rate. Use it
    whenever a price, invoice or credit has to be expressed in a different currency."""
    return f"{amount} {source} is about {round(amount * 1.17, 2)} {target}."


def create_calendar_event(title: str, when: str, attendees: str = "") -> str:
    """Create an event in the calendar with a title, a time and optional attendees. Use it to book
    calls and meetings, reserve rooms, block out time and schedule reviews."""
    return f"Booked '{title}' at {when}" + (f" with {attendees}." if attendees else ".")


def summarise_thread(style: str = "bullets") -> str:
    """Summarise the current conversation thread into a shorter form. Use it to recap what has been
    discussed, produce a handover note, or condense a long chat into a few points."""
    return f"Summary of the thread as {style}: migration, outage, lunch, review, billing."


def lookup_order(order_id: str) -> str:
    """Look up one customer order or purchase by its id or description and return its delivery status
    and tracking details. Use it to find out where a shipment is and when it will arrive."""
    return f"Order {order_id} left the depot and arrives on Thursday."


def reset_password(email: str) -> str:
    """Send a password reset link for an account. Use it when someone is locked out, cannot sign in,
    has forgotten their login, or has an expired password."""
    return f"Reset link sent to {email}."


def recommend_book(topic: str) -> str:
    """Recommend a book on a topic or for an occasion. Use it when someone wants something to read
    or listen to, whether fiction, a management primer or an audiobook."""
    return f"For {topic}, try Thinking in Systems by Donella Meadows."


def send_email(to: str, subject: str, body: str = "") -> str:
    """Send an email to a person or address, with a subject and a message, and optionally a file.
    Use it when the user asks to email, mail or forward something to someone."""
    return f"Email '{subject}' sent to {to}."


def post_to_slack(channel: str, message: str) -> str:
    """Post a message in a Slack channel or send it to a person on Slack. Use it when the user asks to
    post, ping, tell or let a team or colleague know something on Slack."""
    return f"Posted in {channel}: {message[:40]}"


def generate_report(topic: str, period: str = "last week") -> str:
    """Build a report document from the business numbers for a topic and a period: sales, revenue,
    tickets, KPIs or incidents, with tables and charts. It creates the report; it does not send it."""
    return f"Report on {topic} for {period} is ready."


TOOLS = [search_memory, get_weather, convert_currency, create_calendar_event,
         summarise_thread, lookup_order, reset_password, recommend_book,
         send_email, post_to_slack, generate_report]
