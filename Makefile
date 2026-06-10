.PHONY: help install frontend frontend-dev build test clean

help:
	@echo "Targets:"
	@echo "  install       Install the package (editable) with dev extras"
	@echo "  frontend      Build the Angular bundle into theia_ng/static/theia_ng/"
	@echo "  frontend-dev  Run the Angular dev server (proxy -> Django API)"
	@echo "  build         Build the wheel (runs ng build via hatch hook)"
	@echo "  test          Run the Python test suite"
	@echo "  clean         Remove build artifacts and the staged bundle"

install:
	pip install -e ".[dev,drf]"

# Prod-like: build Angular and stage it into the Python package's static dir.
frontend:
	cd frontend && npm ci && npm run build
	rm -rf theia_ng/static/theia_ng
	mkdir -p theia_ng/static/theia_ng
	cp -R frontend/dist/theia-ng/browser/. theia_ng/static/theia_ng/

# Fast dev loop: Angular dev server with a proxy to the Django backend.
frontend-dev:
	cd frontend && npm start

build:
	python -m build

test:
	pytest

clean:
	rm -rf dist build *.egg-info
	rm -rf theia_ng/static/theia_ng frontend/dist
