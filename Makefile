install:
	python3 -m venv venv && . venv/bin/activate && pip install -q -U pip && pip install -q -e . -r requirements-dev.txt

lint:
	. venv/bin/activate && ruff check --select E,F,I,W --ignore E501 --line-length 120 dsystem/ tests/ --fix && ruff format --line-length 120 dsystem/ tests/

test:
	. venv/bin/activate && pytest tests/ -q
