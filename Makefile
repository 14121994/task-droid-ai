PYTHON ?= python3

.PHONY: install test coverage lint generate-data gold-data gold-approved gold-ready release-gates train-baseline eval-baseline train-torch build-sft eval-planner api prod

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	pytest

coverage:
	COVERAGE_FILE=/tmp/taskdroid.coverage $(PYTHON) -m coverage run --branch --source=src/android_planner -m pytest
	COVERAGE_FILE=/tmp/taskdroid.coverage $(PYTHON) -m coverage json -o /tmp/taskdroid-coverage.json
	$(PYTHON) scripts/check_coverage_thresholds.py --coverage-json /tmp/taskdroid-coverage.json

lint:
	ruff check src tests scripts

generate-data:
	$(PYTHON) scripts/generate_seed_dataset.py

gold-data:
	$(PYTHON) scripts/create_gold_dataset.py --count 200

gold-approved:
	$(PYTHON) scripts/build_gold_approved_dataset.py

gold-ready:
	$(PYTHON) scripts/check_gold_readiness.py --min-approved 50

release-gates:
	$(PYTHON) scripts/release_gates.py --min-approved 50 --run-tests

train-baseline:
	$(PYTHON) scripts/train_baseline_classifier.py

eval-baseline:
	$(PYTHON) scripts/evaluate_baseline_classifier.py

train-torch:
	$(PYTHON) scripts/train_torch_classifier.py

build-sft:
	$(PYTHON) scripts/build_sft_dataset.py

eval-planner:
	$(PYTHON) scripts/evaluate_planner_outputs.py

api:
	bash scripts/run_api.sh

prod:
	bash scripts/run_prod_stack.sh
