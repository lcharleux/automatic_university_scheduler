ROOT_PROJ_NAME = "ortools"
MODULE_NAME = "automatic_university_scheduler"
TAG = 0.0
ENV_FILE = ".env"

update-env-vars:
	touch .env
	cat /dev/null > .env ; \
	echo MODULE_NAME=$(MODULE_NAME) >> .env && \
	echo IMG_NAME=$(ROOT_PROJ_NAME) >> .env && \
	echo TAG=$(TAG) >> .env && \
	echo USERNAME=${USER} >> .env && \
	echo USER_UID=${shell id -u} >> .env && \
	echo USER_GID=${shell id -g} >> .env && \
	echo CONDA_ENV_NAME=$(ROOT_PROJ_NAME) >> .env
