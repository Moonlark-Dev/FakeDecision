.PHONY: install dev web build test preview executable clean

install:
	cd frontend && pnpm install

dev:
	bash scripts/dev.sh

web:
	cd frontend && pnpm dev

build:
	cd frontend && pnpm build

test:
	PYTHONPATH=backend python3 -m pytest -q

preview:
	bash scripts/preview.sh

executable:
	bash scripts/build_executable.sh

clean:
	rm -rf build dist frontend/node_modules backend/fake_decision/web/dist .pytest_cache
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
