import pytest
from sqlalchemy import Column, MetaData, String, Table, select
from sqlalchemy.dialects import postgresql

from dsystem.utils.search import fold, fold_text, matches


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("O'ZBEKISTON MILLIY METROLOGIYA INSTITUTI", "ЎЗБЕКИСТОН МИЛЛИЙ МЕТРОЛОГИЯ ИНСТИТУТИ"),
        ("Oʻzbekiston", "Ўзбекистон"),
        ("Qashqadaryo", "Қашқадарё"),
        ("G'alla", "Ғалла"),
        ("Hikmatov Elyor", "Ҳикматов Элёр"),
        ("Xorazm", "Хоразм"),
        ("Jizzax", "Жиззах"),
        ("Shurtan gaz kimyo", "Шуртан газ кимё"),
        ("ma'no", "маъно"),
        ("Toshkent", "Тошкент"),
        ("Tashkent", "Ташкент"),
        ("Zhuravlev", "Журавлёв"),
        ("Mikhail", "Михаил"),
        ("Natsionalnyy", "Национальный"),
    ],
)
def test_latin_and_cyrillic_fold_to_one_key(latin, cyrillic):
    assert fold_text(latin) == fold_text(cyrillic)


def test_fold_drops_quotes_and_joins_spaces():
    assert fold_text('ГП «УЗБЕКСКИЙ   НАЦИОНАЛЬНЫЙ»  "X"') == "gp uzbekskiy natsionalnyy h"


def test_matches_keeps_the_plain_search_and_folds_both_sides_in_sql():
    table = Table("t", MetaData(), Column("name", String))
    sql = str(
        select(table)
        .where(matches("o'z_%", table.c.name))
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "ILIKE" in sql.upper()
    assert "translate(" in sql
    assert "regexp_replace(" in sql
    # LIKE's own wildcards in the term stay literal.
    assert "o''z/_/%" in sql


def test_fold_is_built_from_builtin_functions():
    table = Table("t", MetaData(), Column("name", String))
    sql = str(fold(table.c.name).compile(dialect=postgresql.dialect()))
    assert sql.startswith("regexp_replace(")
    assert "lower(t.name)" in sql


@pytest.mark.parametrize(
    ("latin", "cyrillic"),
    [
        ("FedEx", "Федекс"),
        ("Coca-Cola", "Кока-Кола"),
        ("Xerox", "Ксерокс"),
        ("Microsoft", "Микрософт"),
        ("Pharma", "Фарма"),
        ("Wolt", "Волт"),
        ("Citroen", "Ситроен"),
    ],
)
def test_a_borrowed_word_meets_its_cyrillic_spelling_on_the_loan_key(latin, cyrillic):
    assert fold_text(latin, loan=True) == fold_text(cyrillic, loan=True)


def test_the_loan_key_leaves_ch_and_uzbek_x_to_the_native_one():
    assert fold_text("Chevron", loan=True) == "chevron"
    assert fold_text("Xorazm") == fold_text("Хоразм")
