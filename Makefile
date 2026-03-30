PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: backend-install frontend-install backend-test frontend-build preflight preflight-strict migrate migrate-down-one migrate-down-base migrate-verify upgrade-dev release-gate release-gate-dev

backend-install:
	$(PIP) install -r backend/requirements.txt

frontend-install:
	cd frontend && npm install

backend-test:
	$(PYTHON) -m unittest discover -s backend/tests -p "test_*.py"

frontend-build:
	cd frontend && npm run build

preflight:
	PYTHONPATH=backend $(PYTHON) backend/scripts/preflight.py

preflight-strict:
	PYTHONPATH=backend $(PYTHON) backend/scripts/preflight.py --strict

migrate:
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini upgrade head

migrate-down-one:
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini downgrade -1

migrate-down-base:
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini downgrade base

migrate-verify:
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini upgrade head
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini downgrade base
	cd backend && ../.venv/bin/python -m alembic -c alembic.ini upgrade head

upgrade-dev:
	$(MAKE) backend-test
	$(MAKE) frontend-build
	$(MAKE) preflight

release-gate:
	$(MAKE) migrate-verify
	$(MAKE) backend-test
	$(MAKE) frontend-build
	$(MAKE) preflight-strict

release-gate-dev:
	$(MAKE) migrate-verify
	$(MAKE) backend-test
	$(MAKE) frontend-build
	$(MAKE) preflight
