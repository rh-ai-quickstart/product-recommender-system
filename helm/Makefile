# Makefile for product recommender system deployment.
ifeq ($(NAMESPACE),)
ifeq (,$(filter depend% help,$(MAKECMDGOALS)))
$(error NAMESPACE is not set)
endif
endif

MAKEFLAGS += --no-print-directory

POSTGRES_USER ?= postgres
POSTGRES_PASSWORD ?= recsys_password
POSTGRES_DBNAME ?= recsys
PRODUCT_RECOMMENDER_CHART := product-recommender-system
STORAGE_CHART := aws-compatible-storage
PIPELINE_SERVER_CHART := pipeline-server
STORAGE_SERVICE := aws-compatible-storage
STORAGE_API_PORT := 7480
STORAGE_BUCKET := recommender
STORAGE_REGION := us-east-1
STORAGE_SECRET := aws-compatible-storage-credentials
MINIMUM_OC_VERSION = 4.17.0
MODEL_NAME ?=
MODEL_ENDPOINT ?=

helm_pgvector_args = \
	--set pgvector.secret.user=$(POSTGRES_USER) \
	--set pgvector.secret.password=$(POSTGRES_PASSWORD) \
	--set pgvector.secret.dbname=$(POSTGRES_DBNAME)

dataset_args = \
	--set datasetUrl=$(DATASET_URL)

model_args = \
	--set llmModel.ollamaModel=$(MODEL_NAME) \
	--set llmModel.modelEndpoint=$(MODEL_ENDPOINT)

storage_args = \
	--set aws-compatible-storage.s3.accessKeyId=$(storage.accessKeyId) \
	--set aws-compatible-storage.s3.secretAccessKey=$(storage.secretAccessKey) \
	--set aws-compatible-storage.auth.username=$(storage.accessKeyId) \
	--set aws-compatible-storage.auth.password=$(storage.secretAccessKey)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install       - Install the recommender system and S3-compatible storage"
	@echo "  uninstall     - Uninstall the recommender system and supporting resources"
	@echo "  status        - Check the deployment status"
	@echo ""
	@echo "Configuration options:"
	@echo "  NAMESPACE                  - Target namespace (required)"
	@echo "  storage.accessKeyId        - S3 access key (required)"
	@echo "  storage.secretAccessKey    - S3 secret key (required)"
	@echo "  MODEL_NAME                 - Model name for review summarization (required)"
	@echo "  MODEL_ENDPOINT             - Model endpoint URL (required)"

.PHONY: check-oc-version
check-oc-version:
	$(eval USER_OC_VERSION = $(shell oc version --client=true -o json | jq -r .clientVersion.gitVersion))
	@echo "Detected oc version on your machine: $(USER_OC_VERSION)"
	@echo "NOTE: This install script has only been tested for oc version $(MINIMUM_OC_VERSION) and bash/zsh."

.PHONY: check-storage-credentials
check-storage-credentials:
	@if [ -z "$(storage.accessKeyId)" ]; then \
		echo "Set storage.accessKeyId to a non-empty value."; \
		exit 1; \
	fi
	@if [ -z "$(storage.secretAccessKey)" ]; then \
		echo "Set storage.secretAccessKey to a non-empty value."; \
		exit 1; \
	fi

.PHONY: check-model-config
check-model-config:
	@if [ -z "$(MODEL_NAME)" ]; then \
		echo "ERROR: MODEL_NAME is required but not set."; \
		echo "Please provide MODEL_NAME when running make install."; \
		exit 1; \
	fi
	@if [ -z "$(MODEL_ENDPOINT)" ]; then \
		echo "ERROR: MODEL_ENDPOINT is required but not set."; \
		echo "Please provide MODEL_ENDPOINT when running make install."; \
		exit 1; \
	fi

namespace:
	@oc create namespace $(NAMESPACE) &> /dev/null && oc label namespace $(NAMESPACE) modelmesh-enabled=false ||:
	@oc project $(NAMESPACE) &> /dev/null ||:

.PHONY: depend
depend:
	@echo "Updating Helm dependencies for $(PRODUCT_RECOMMENDER_CHART)"
	@helm dependency update $(PRODUCT_RECOMMENDER_CHART) &> /dev/null
	@echo "Updating Helm dependencies for $(STORAGE_CHART)"
	@helm dependency update $(STORAGE_CHART) &> /dev/null

.PHONY: install
install: check-oc-version check-storage-credentials check-model-config namespace depend storage-install pipeline-server-install product-recommender-install

.PHONY: storage-install
storage-install:
	@echo "Installing S3-compatible storage and creating the recommender bucket..."
	@helm -n $(NAMESPACE) upgrade --install $(STORAGE_SERVICE) $(STORAGE_CHART) \
		$(storage_args) \
		--timeout 5m
	@echo "Waiting for S3-compatible storage to become ready in namespace $(NAMESPACE)..."
	@oc wait deployment/$(STORAGE_SERVICE) -n $(NAMESPACE) --for=condition=Available --timeout=180s
	@oc wait job/aws-compatible-storage-upload-sample-docs -n $(NAMESPACE) --for=condition=complete --timeout=180s
	@oc wait --for=jsonpath='{.status.ingress[0].conditions[?(@.type=="Admitted")].status}=True' \
		route/$(STORAGE_SERVICE)-api -n $(NAMESPACE) --timeout=60s
	@echo "S3-compatible storage installation complete."

.PHONY: pipeline-server-install
pipeline-server-install:
	@echo "Installing pipeline server with S3-compatible artifact storage..."
	@helm -n $(NAMESPACE) upgrade --install pipeline-server $(PIPELINE_SERVER_CHART) \
		--set storage.apiEndpoint=$(STORAGE_SERVICE).$(NAMESPACE).svc.cluster.local \
		--set storage.apiPort=$(STORAGE_API_PORT) \
		--set storage.defaultBucket=$(STORAGE_BUCKET) \
		--set storage.defaultRegion=$(STORAGE_REGION) \
		--set storage.credentialsSecret=$(STORAGE_SECRET) \
		--timeout 300m
	@echo "Waiting for pipeline server to start in namespace $(NAMESPACE)..."
	@for i in {1..25}; do \
		oc get pod -l app=ds-pipeline-dspa -n $(NAMESPACE) 2>/dev/null | grep -q "Running\|ContainerCreating\|Pending" && break; \
		echo "Pod not found yet, retrying (wait)..."; \
		sleep 5; \
	done
	@oc wait pod -l app=ds-pipeline-dspa -n $(NAMESPACE) --for=condition=Ready --timeout=180s
	@echo "Pipeline server ready."

.PHONY: product-recommender-install
product-recommender-install:
	@$(eval PGVECTOR_ARGS := $(call helm_pgvector_args))
	@$(eval DATASET_ARGS := $(call dataset_args))
	@$(eval MODEL_ARGS := $(call model_args))
	@echo "Installing $(PRODUCT_RECOMMENDER_CHART)"
	@echo "Waiting for model services to deploy. This may take 10-15 minutes..."
	@helm -n $(NAMESPACE) upgrade --install $(PRODUCT_RECOMMENDER_CHART) $(PRODUCT_RECOMMENDER_CHART) \
		$(PGVECTOR_ARGS) \
		$(DATASET_ARGS) \
		$(MODEL_ARGS) \
		$(EXTRA_HELM_ARGS) --set strimzi-kafka-operator.createGlobalResources=false --timeout 300m
	@oc rollout status deploy --timeout=20m || true
	@echo "$(PRODUCT_RECOMMENDER_CHART) installed successfully"
	@echo "Frontend URL: https://$$(oc get route product-recommender-system-frontend -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

.PHONY: uninstall
uninstall: check-oc-version product-recommender-uninstall pipeline-server-uninstall storage-uninstall delete-project

.PHONY: product-recommender-uninstall
product-recommender-uninstall:
	@echo "Uninstalling $(PRODUCT_RECOMMENDER_CHART)"
	@helm -n $(NAMESPACE) uninstall $(PRODUCT_RECOMMENDER_CHART) || true
	@echo "Deleting remaining pods in namespace $(NAMESPACE) for $(PRODUCT_RECOMMENDER_CHART)"
	@oc delete jobs -n $(NAMESPACE) --all --grace-period=60 --ignore-not-found
	@oc delete pods -n $(NAMESPACE) --all --grace-period=60 --ignore-not-found

.PHONY: storage-uninstall
storage-uninstall:
	@echo "Uninstalling S3-compatible storage"
	@helm -n $(NAMESPACE) uninstall $(STORAGE_SERVICE) || true
	@echo "Removing pgvector and storage PVCs from $(NAMESPACE)"
	@oc get pvc -n $(NAMESPACE) -o custom-columns=NAME:.metadata.name | grep -E '^(pg|aws-compatible-storage)' | xargs -I {} oc delete pvc -n $(NAMESPACE) {} ||:
	@echo "Checking for any remaining resources in namespace $(NAMESPACE)..."
	@echo "Remaining resources in namespace $(NAMESPACE):"
	@$(MAKE) status

.PHONY: pipeline-server-uninstall
pipeline-server-uninstall:
	@echo "Uninstalling pipeline server chart"
	@helm -n $(NAMESPACE) uninstall pipeline-server || true

.PHONY: delete-project
delete-project:
	@echo "Attempting to delete OpenShift project $(NAMESPACE)..."
	@oc delete project $(NAMESPACE)

.PHONY: status
status:
	@echo "Listing pods..."
	oc get pods -n $(NAMESPACE) || true
	@echo "Listing services..."
	oc get svc -n $(NAMESPACE) || true
	@echo "Listing routes..."
	oc get routes -n $(NAMESPACE) || true
	@echo "Listing secrets..."
	oc get secrets -n $(NAMESPACE) | grep huggingface-secret || true
	@echo "Listing PVCs..."
	oc get pvc -n $(NAMESPACE) || true
