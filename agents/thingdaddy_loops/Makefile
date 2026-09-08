# ThingDaddy Loops — Mac mini operations
PY ?= python3
VENV = .venv
BIN = $(VENV)/bin
DB ?= civilization.db
OUT ?= out

.PHONY: venv install selftest run-a run-b run-all graph install-launchd uninstall-launchd clean

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

selftest:
	$(PY) tests/selftest.py

run-a:
	$(BIN)/python loop_a/run.py run-all --db $(DB) --config config.yaml --out $(OUT)

run-b:
	$(BIN)/python loop_b/run.py run-all --db $(DB) --config config.yaml --out $(OUT)

run-all:
	$(BIN)/python run_all.py --db $(DB) --config config.yaml --out $(OUT)

graph:
	$(BIN)/python loop_b/run.py export-graph --db $(DB) --out $(OUT)

install-launchd:
	./install_launchd.sh

uninstall-launchd:
	launchctl unload ~/Library/LaunchAgents/com.thingdaddy.loops.plist 2>/dev/null || true
	rm -f ~/Library/LaunchAgents/com.thingdaddy.loops.plist

clean:
	rm -rf $(OUT) *.db logs __pycache__ */__pycache__ */*/__pycache__
