VENV      ?= .venv
PYTHON    ?= $(VENV)/bin/python
PIP       ?= $(VENV)/bin/pip
STREAMLIT ?= $(VENV)/bin/streamlit
PORT      ?= 8501
DATA_DIR  ?= $(CURDIR)/data

.DEFAULT_GOAL := help

.PHONY: help venv install run test health clean clean-data clean-venv uninstall

help: ## Показать список доступных команд
	@echo "Использование: make <команда>"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv: ## Создать виртуальное окружение
	python3 -m venv $(VENV)

install: venv ## Установить зависимости в .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo
	@echo "Готово. Запуск: make run"

run: ## Запустить приложение (http://localhost:8501)
	$(STREAMLIT) run app.py --server.port $(PORT)

test: ## Smoke-тест приложения (без запуска сервера)
	$(PYTHON) -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app.py', default_timeout=120); at.run(); assert not at.exception, [str(e.value) for e in at.exception]; print('Smoke-тест: OK')"

health: ## Проверить доступность запущенного приложения
	@curl -fs http://localhost:$(PORT)/_stcore/health && echo " — OK"

clean: ## Удалить временные файлы Python
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

clean-data: ## Удалить данные приложения (тексты, заметки, аудио)
	rm -rf $(DATA_DIR)

clean-venv: ## Удалить виртуальное окружение
	rm -rf $(VENV)

uninstall: clean clean-data clean-venv ## Полное удаление: кэш, данные, окружение
	@echo "Удалено: __pycache__, $(DATA_DIR), $(VENV)"
