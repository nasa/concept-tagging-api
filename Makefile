.PHONY: tests help service
.DEFAULT_GOAL := help

BUCKET=your-bucket-name/path/to/your/project/dir
DOCKER_REGISTRY=your-docker-registry.com/your-namespace
PROFILE=default
IMAGE_NAME=concept_tagging_api
GIT_REMOTE=origin
MODELS_DIR=models
EXPERIMENT_NAME=test
DOCKERFILE_NAME=Dockerfile
MODELS_URL=https://data.nasa.gov/docs/datasets/public/concept_tagging_models/10_23_2019.zip
PRELOAD=True

## Install requirements to local python environment
requirements:
	pip install -r requirements.txt; \
	pip install git+https://github.com/nasa/concept-tagging-training.git@v1.0.3-open_source_release#egg=dsconcept \
    python -m spacy download en_core_web_sm

## Run test coverage with nosetests
tests:
	pip install nose; \
    pip install coverage==4.5.4; \
    export MODELS_DIR=models/test; \
	nosetests --with-coverage --cover-package service --cover-html; \
	open cover/index.html

examples:
	@echo "curl -X POST -H "Content-Type: application/json" -d @example.json http://0.0.0.0:5005/findterms/"



## Build docker image for service, automatically labeling image with link to most recent commit.
## Choose which Dockerfile to use with DOCKERFILE_NAME variable. The default requires you have downloaded the concept_tagging_training library.
## Dockerfile.tests includes testing in the docker build process.
build:
	export COMMIT=$$(git log -1 --format=%H); \
	export REPO_URL=$$(git remote get-url $(GIT_REMOTE)); \
	export REPO_DIR=$$(dirname $$REPO_URL); \
	export BASE_NAME=$$(basename $$REPO_URL .git); \
	export GIT_LOC=$$REPO_DIR/$$BASE_NAME/tree/$$COMMIT; \
	export VERSION=$$(python version.py); \
	echo $$GIT_LOC; \
	docker build -t $(IMAGE_NAME):$$VERSION \
		-f $(DOCKERFILE_NAME) \
		--build-arg GIT_URL=$$GIT_LOC \
		--build-arg VERSION=$$VERSION .

## Push the docker image to storage.analytics.nasa.gov
push:
	export VERSION=$$(python version.py); \
	docker tag $(IMAGE_NAME):$$VERSION $(DOCKER_REGISTRY)/$(IMAGE_NAME):$$VERSION; \
	docker tag $(IMAGE_NAME):$$VERSION $(DOCKER_REGISTRY)/$(IMAGE_NAME):latest; \
	docker push $(DOCKER_REGISTRY)/$(IMAGE_NAME):$$VERSION; \
	docker push $(DOCKER_REGISTRY)/$(IMAGE_NAME):latest

## Push docker image to storage.analytics.nasa.gov as stable version
push-stable:
	export VERSION=$$(python version.py); \
	docker tag $(IMAGE_NAME):$$VERSION $(DOCKER_REGISTRY)/$(IMAGE_NAME):stable; \
	docker push $(DOCKER_REGISTRY)/$(IMAGE_NAME):stable

## Run the service using docker
service:
	@echo $(MODELS_DIR)/$(EXPERIMENT_NAME)
	export VERSION=$$(python version.py); \
	docker run -it \
		-p 5001:5000 \
		-v $$(pwd)/$(MODELS_DIR)/$(EXPERIMENT_NAME):/home/service/models/experiment \
		-e PRELOAD=$(PRELOAD) \
		$(IMAGE_NAME):$$VERSION

## Run the service locally without docker
service-local:
	 export MODELS_DIR=$(MODELS_DIR)/$(EXPERIMENT_NAME); \
	 python service/app.py

TXT_DIR=$(MODELS_DIR)/$(EXPERIMENT_NAME)/tags_txts/
## Get txt files of keyword tags
get-tag-names:
	mkdir -p $(TXT_DIR); \
	python src/get_tag_names.py \
		--model_dir $(MODELS_DIR)/$(EXPERIMENT_NAME) \
		--text_dir $(TXT_DIR)

## sync models from s3 bucket
sync_models_from_s3:
ifeq (default,$(PROFILE))
	aws s3 sync s3://$(BUCKET)models/$(EXPERIMENT_NAME) models/$(EXPERIMENT_NAME)
else
	aws s3 sync s3://$(BUCKET)models/$(EXPERIMENT_NAME) models/$(EXPERIMENT_NAME) --profile $(PROFILE)
endif


## Download models from data.nasa.gov
get-models:
	wget -O models/models.zip $(MODELS_URL); \
	cd models && unzip models.zip

## zip files for service docker image for deployment to Elastic Beanstalk
zip-for-ebs:
	zip -r --include 'service/*' 'classifier_scripts/*' \
		'requirements.txt' '.dockerignore' 'Dockerfile' \
		'Dockerrun.aws.json' '.ebextensions/*' @ sti_tagger.zip .

help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
