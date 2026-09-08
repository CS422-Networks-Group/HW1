PYVER   := $(shell cut -d. -f1,2 .python-version)
VENV    := .venv
PYTHON  := $(VENV)/bin/python

.PHONY: venv install clean

# Create the venv with the interpreter version pinned in .python-version
# (falls back to whatever `python3` resolves to, with a warning, if that
# exact version isn't installed).
venv:
	@if command -v python$(PYVER) >/dev/null 2>&1; then \
		PY=python$(PYVER); \
	else \
		PY=python3; \
		echo "WARNING: python$(PYVER) not found on PATH, falling back to $$PY ($$($$PY --version)). Install Python $(shell cat .python-version) to match everyone else."; \
	fi; \
	$$PY -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

clean:
	rm -rf $(VENV)
