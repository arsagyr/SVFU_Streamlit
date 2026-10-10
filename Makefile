ENGINE    ?= docker
IMAGE     ?= svfu-streamlit:latest
CONTAINER ?= svfu-streamlit
PORT      ?= 8501
DATA_DIR  ?= $(CURDIR)/data

ifeq ($(ENGINE),podman)
COMPOSE ?= podman-compose
else
COMPOSE ?= docker compose
endif

.DEFAULT_GOAL := help

.PHONY: help install build rebuild up down start stop restart logs ps shell test \
        health clean clean-data clean-image uninstall

help: ## Показать список доступных команд
	@echo "Использование: make <команда> [ENGINE=docker|podman]"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: build up ## Собрать образ и запустить контейнер (первый запуск)

build: ## Собрать образ
	$(ENGINE) build -t $(IMAGE) .

rebuild: ## Пересобрать образ без кэша
	$(ENGINE) build --no-cache -t $(IMAGE) .

up: ## Запустить контейнер через compose
	$(COMPOSE) up -d
	@echo "Приложение: http://localhost:$(PORT)"

down: ## Остановить и удалить контейнер (данные сохраняются)
	-$(COMPOSE) down

start: ## Запустить остановленный контейнер
	$(ENGINE) start $(CONTAINER)

stop: ## Остановить контейнер
	$(ENGINE) stop $(CONTAINER)

restart: ## Перезапустить контейнер
	$(ENGINE) restart $(CONTAINER)

logs: ## Показать логи (follow)
	$(ENGINE) logs -f $(CONTAINER)

ps: ## Статус контейнера
	$(ENGINE) ps -a --filter name=$(CONTAINER)

shell: ## Открыть shell внутри контейнера
	$(ENGINE) exec -it $(CONTAINER) bash

health: ## Проверить доступность приложения
	@curl -fs http://localhost:$(PORT)/_stcore/health && echo " — OK"

test: ## Запустить smoke-тест приложения внутри контейнера
	$(ENGINE) exec $(CONTAINER) python -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app.py', default_timeout=60); at.run(); assert not at.exception, [str(e.value) for e in at.exception]; print('Smoke-тест: OK')"

clean: ## Удалить контейнер (данные и образ сохраняются)
	-$(COMPOSE) down --remove-orphans
	-$(ENGINE) rm -f $(CONTAINER)

clean-data: ## Удалить данные приложения (БД и аудио)
	rm -rf $(DATA_DIR)

clean-image: ## Удалить образ
	-$(ENGINE) rmi -f $(IMAGE)

uninstall: clean clean-data clean-image ## Полное удаление: контейнер, данные, образ
	@echo "Удалено: контейнер, $(DATA_DIR), образ $(IMAGE)"
