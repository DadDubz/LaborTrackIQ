PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: backend-install frontend-install backend-test frontend-build preflight preflight-strict migrate upgrade-dev release-gate

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
	cd backend && ../.venv/bin/alembic -c alembic.ini upgrade head

upgrade-dev:
	$(MAKE) backend-test
	$(MAKE) frontend-build
	$(MAKE) preflight

release-gate:
	$(MAKE) backend-test
	$(MAKE) frontend-build
	$(MAKE) preflight-strict
