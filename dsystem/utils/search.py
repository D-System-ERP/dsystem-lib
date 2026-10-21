"""One search across Latin and Cyrillic (2026-10-21, the owner: «hamma searchlarda lotin va kirilni bittada topiladigan
qilib common funksiya»).

The data is written in Russian, Uzbek Cyrillic and Uzbek Latin, and the person searching types whichever their
keyboard has: «O'ZBEKISTON» is «ЎЗБЕКИСТОН», «Qashqadaryo» is «Қашқадарё», «Hikmatov» is «Ҳикматов». So the text and
the query are both folded to one Latin key before they are compared — a normalisation, not a translation:

1. lowercase;
2. Cyrillic to the Latin people type — ``ц ts``, ``ч ch``, ``ш sh``, ``щ sh``, ``ю yu``, ``я ya``, then one letter for
   one, Uzbek's own included (``ў o``, ``ғ g``, ``қ k``, ``ҳ h``, ``ж j``, ``ё e``);
3. the letters the two scripts disagree on folded together: ``q k`` and ``x h`` (Uzbek Latin's қ and х), ``kh h``,
   ``zh j``, ``yo e``;
4. the signs and apostrophes dropped (``ъ ь ʻ ʼ ' ` " « »``), so «oʻ», «o'» and «ў» meet;
5. runs of whitespace made one space.

The frontend's ``fold`` (``src/lib/translit.ts``) applies the same steps, so a list filtered in the browser and one
searched here agree. Folding loses letters — ``kh`` and ``h``, ``q`` and ``k`` read alike — so a fold only ever adds
matches: ``matches`` keeps the plain case-insensitive one beside it.
"""

from __future__ import annotations

import re

from sqlalchemy import ColumnElement, Text, func, literal, or_

_CYRILLIC_PAIRS = (("ц", "ts"), ("ч", "ch"), ("ш", "sh"), ("щ", "sh"), ("ю", "yu"), ("я", "ya"))
_SINGLE_FROM = "абвгдеёжзийклмнопрстуфхыэўғқҳqx"
_SINGLE_TO = "abvgdeejziyklmnoprstufhyeogkhkh"
_DROPPED = "ъь'ʻʼ‘’`\"«»“”„"
_LATIN_PAIRS = (("kh", "h"), ("zh", "j"), ("yo", "e"))

assert len(_SINGLE_FROM) == len(_SINGLE_TO)

_TABLE = str.maketrans(_SINGLE_FROM, _SINGLE_TO, _DROPPED)
_SPACES = re.compile(r"\s+")

# The escape character for LIKE: ``/``, as SQLAlchemy's own ``autoescape`` uses.
_ESCAPE = "/"


def fold_text(value: str) -> str:
    """The search key of ``value``, in Python — the same steps ``fold`` runs in SQL.

    >>> fold_text("ГП «ЎЗБЕКИСТОН» Қашқадарё")
    'gp ozbekiston kashkadare'
    >>> fold_text("GP O'zbekiston Qashqadaryo")
    'gp ozbekiston kashkadare'
    """
    text = value.lower()
    for cyrillic, latin in _CYRILLIC_PAIRS:
        text = text.replace(cyrillic, latin)
    text = text.translate(_TABLE)
    for pair, single in _LATIN_PAIRS:
        text = text.replace(pair, single)
    return _SPACES.sub(" ", text)


def fold(expression: ColumnElement) -> ColumnElement:
    """The search key of a text column or value, in SQL (built-in functions only — no extension, no migration)."""
    text = func.lower(expression)
    for cyrillic, latin in _CYRILLIC_PAIRS:
        text = func.replace(text, cyrillic, latin)
    # ``translate`` drops every character of its first set past the second set's length.
    text = func.translate(text, _SINGLE_FROM + _DROPPED, _SINGLE_TO)
    for pair, single in _LATIN_PAIRS:
        text = func.replace(text, pair, single)
    return func.regexp_replace(text, r"\s+", " ", "g")


def _escaped(term: str) -> str:
    return term.replace(_ESCAPE, _ESCAPE * 2).replace("%", f"{_ESCAPE}%").replace("_", f"{_ESCAPE}_")


def matches(term: str, *columns: ColumnElement) -> ColumnElement:
    """Any of ``columns`` holds ``term``: case-insensitively as written, or folded across the scripts.

    The query is folded by the same SQL as the columns, so the two can never drift apart.
    """
    pattern = fold(literal(f"%{_escaped(term)}%", type_=Text))
    return or_(
        *(
            or_(column.icontains(term, autoescape=True), fold(column).like(pattern, escape=_ESCAPE))
            for column in columns
        )
    )
