test:
	@echo "Running tests..."
	pytest

test-capture:
	@echo "Running tests with output capture..."
	pytest --capture-output