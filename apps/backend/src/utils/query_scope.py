"""Static check that a read-only SPARQL query stays inside the events graph.

This is one half of the isolation of the audit graph; the other half is pinning the dataset in the HTTP request
(``default-graph-uri`` and ``named-graph-uri``). Both are needed:

- a ``FROM`` clause inside the query overrides the pinned dataset, and
- an explicit ``GRAPH <iri>`` inside ``FILTER EXISTS`` ignores it (Virtuoso 7.2.16 evaluates it against the real
  graph, which would turn ``EXISTS`` into a yes/no oracle over the audit trail).

rdflib's parse tree cannot be trusted for this: it drops patterns nested two levels deep in ``EXISTS``. So the check
reads the query text itself with a small lexer that follows the SPARQL terminals (comments, strings, IRIs, prefixes,
``BASE``, codepoint escapes) and looks at every ``GRAPH``, ``FROM`` and ``SERVICE``. It is deliberately conservative:
anything it cannot resolve to the allowed graph is rejected.

The same lexer closes a bigger hole. Virtuoso lets a SPARQL query call its internal functions (``bif:``) and stored
procedures (``sql:``), and ``bif:exec('SPARQL CLEAR GRAPH <g>')`` runs as ``dba`` even inside a SELECT, so a read-only
query could erase any graph, the audit trail included. Those namespaces are rejected under any prefix label, and so is
any function call that is not an XSD cast.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse


_XSD = "http://www.w3.org/2001/XMLSchema#"
_INTERNAL_SCHEMES = {"bif", "sql"}
_INTERNAL_NAMESPACES = ("http://www.openlinksw.com/schemas/bif#",)


class QueryScopeError(ValueError):
    """The query reaches a graph other than the allowed one, or a remote service."""


# Codepoint escapes are decoded before parsing (SPARQL 1.1, section 19.2), so GRAPH is GRAPH.
_CODEPOINT = re.compile(r"\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})")

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>\#[^\n\r]*)
  | (?P<iri><[^<>"{}|^`\\\x00-\x20]*>)
  | (?P<long1>'''(?:(?:'|'')?(?:[^'\\]|\\.))*''')
  | (?P<long2>\"\"\"(?:(?:"|"")?(?:[^"\\]|\\.))*\"\"\")
  | (?P<str1>'(?:[^'\\\n\r]|\\.)*')
  | (?P<str2>"(?:[^"\\\n\r]|\\.)*")
  | (?P<var>[?$][\w·À-￿]+)
  | (?P<pname>(?:[A-Za-zÀ-￿][\w·À-￿.\-]*)?:(?:[\w·À-￿:%.\-]|\\.)*)
  | (?P<word>[A-Za-z_][\w\-]*)
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass(slots=True, frozen=True)
class _Token:
    kind: str
    text: str

    @property
    def keyword(self) -> str:
        return self.text.upper() if self.kind == "word" else ""


def _decode_codepoints(query: str) -> str:
    return _CODEPOINT.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)), query)


def _tokens(query: str) -> list[_Token]:
    result = []
    for match in _TOKEN.finditer(_decode_codepoints(query)):
        kind = match.lastgroup or "other"
        if kind not in {"ws", "comment"}:
            result.append(_Token(kind, match.group()))
    return result


class _Resolver:
    """Resolves IRIREFs and prefixed names the way the query's prologue defines them."""

    def __init__(self) -> None:
        self.base = ""
        self.prefixes: dict[str, str] = {}

    def iri(self, text: str) -> str:
        reference = text[1:-1]
        if self.base:
            return urljoin(self.base, reference)
        if urlparse(reference).scheme:
            return reference
        raise QueryScopeError(f"Relative IRI <{reference}> cannot be checked without a BASE; write an absolute IRI.")

    def pname(self, text: str) -> str:
        prefix, _, local = text.partition(":")
        if prefix not in self.prefixes:
            raise QueryScopeError(f"Unknown prefix '{prefix}:' in a graph name.")
        return self.prefixes[prefix] + re.sub(r"\\(.)", r"\1", local.rstrip("."))

    def term(self, token: _Token | None, what: str) -> str | None:
        """The resolved IRI of a graph name; ``None`` for a variable; an error for anything else."""
        if token is None:
            raise QueryScopeError(f"{what} must be followed by an IRI or a variable.")
        if token.kind == "iri":
            return self.iri(token.text)
        if token.kind == "pname":
            return self.pname(token.text)
        if token.kind == "var":
            return None
        raise QueryScopeError(f"{what} must be followed by an IRI or a variable.")


def _lenient_iri(resolver: _Resolver, token: _Token) -> str | None:
    try:
        return resolver.iri(token.text) if token.kind == "iri" else resolver.pname(token.text)
    except QueryScopeError:
        return None


def _check_no_functions(token: _Token, following: _Token | None, resolver: _Resolver) -> None:
    """Rejects Virtuoso internals under any spelling, and every function call that is not an XSD cast."""
    label = token.text.partition(":")[0].lower() if token.kind == "pname" else ""
    iri = _lenient_iri(resolver, token)
    scheme = iri.partition(":")[0].lower() if iri else ""
    if (
        label in _INTERNAL_SCHEMES
        or scheme in _INTERNAL_SCHEMES
        or (iri is not None and iri.lower().startswith(_INTERNAL_NAMESPACES))
    ):
        raise QueryScopeError("Virtuoso internal functions and stored procedures (bif:, sql:) are not allowed.")
    if following is not None and following.kind == "other" and following.text == "(":
        if iri is None or not iri.startswith(_XSD):
            shown = iri or token.text
            raise QueryScopeError(f"Calling <{shown}> is not allowed; only XSD casts may be called as functions.")


def _check_graph(iri: str | None, allowed_graph: str) -> None:
    if iri is not None and iri != allowed_graph:
        raise QueryScopeError(f"Query reaches graph <{iri}>; only <{allowed_graph}> may be queried.")


def check_read_query_scope(query: str, allowed_graph: str) -> None:
    """Raises ``QueryScopeError`` unless every graph the query names is ``allowed_graph``.

    ``GRAPH ?g`` is accepted: with the dataset pinned in the request, the variable can only range over the allowed
    graph. ``SERVICE`` is never accepted.
    """
    tokens = _tokens(query)
    resolver = _Resolver()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        following = tokens[i + 1] if i + 1 < len(tokens) else None
        keyword = token.keyword

        if keyword == "BASE" and following is not None and following.kind == "iri":
            resolver.base = resolver.iri(following.text) if resolver.base else following.text[1:-1]
            i += 2
            continue
        if keyword == "PREFIX" and following is not None and following.kind == "pname":
            target = tokens[i + 2] if i + 2 < len(tokens) else None
            if target is not None and target.kind == "iri":
                resolver.prefixes[following.text.partition(":")[0]] = resolver.iri(target.text)
                i += 3
                continue

        if token.kind in {"iri", "pname"}:
            _check_no_functions(token, following, resolver)
        if keyword == "SERVICE":
            raise QueryScopeError("SERVICE (federated queries) is not allowed.")
        if keyword == "GRAPH":
            _check_graph(resolver.term(following, "GRAPH"), allowed_graph)
        elif keyword == "FROM":
            if following is not None and following.keyword == "NAMED":
                following = tokens[i + 2] if i + 2 < len(tokens) else None
            iri = resolver.term(following, "FROM")
            if iri is None:
                raise QueryScopeError("FROM must be followed by an IRI.")
            _check_graph(iri, allowed_graph)
        i += 1
