# Makefile for RAG Deployment
# Replaces the original deploy.sh script with additional uninstall functionality
ifeq ($(NAMESPACE),)
ifeq (,$(filter depend% help,$(MAKECMDGOALS)))
$(error NAMESPACE is not set)
endif
endif

MAKEFLAGS += --no-print-directory

# Default values
POSTGRES_USER ?= postgres
POSTGRES_PASSWORD ?= recsys_password
POSTGRES_DBNAME ?= recsys
# HF_TOKEN ?= $(shell bash -c 'read -r -p "Enter Hugging Face Token: " HF_TOKEN; echo $$HF_TOKEN')
PRODUCT_RECOMMENDER_CHART := product-recommender-system
MINIO_CHART := minio
PIPELINE_SERVER_CHART := pipeline-server
# Do we need this??
TOLERATIONS_TEMPLATE=[{"key":"$(1)","effect":"NoSchedule","operator":"Exists"}]
MINIMUM_OC_VERSION = "4.17.0"
MINIMUM_USERID_LENGTH = 3
MINIMUM_PASSWORD_LENGTH = 8
REQUIRED_PARAMS = minio.userId minio.password
# Model configuration defaults
OLLAMA_MODEL ?= meta-llama/Llama-3.1-8B-Instruct
MODEL_ENDPOINT ?= https://llama-3-1-8b-instruct-predictor-kickstart-llms.apps.ai-dev02.kni.syseng.devcluster.openshift.com/v1

# Helm argument helpers
helm_pgvector_args = \
	--set pgvector.secret.user=$(POSTGRES_USER) \
	--set pgvector.secret.password=$(POSTGRES_PASSWORD) \
	--set pgvector.secret.dbname=$(POSTGRES_DBNAME)

dataset_args = \
	--set datasetUrl=$(DATASET_URL)

model_args = \
	--set llmModel.ollamaModel=$(OLLAMA_MODEL) \
	--set llmModel.modelEndpoint=$(MODEL_ENDPOINT)

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install       - Installs recommender system and supporting resources; provide userId and password for minio; e.g., make install minio.userId=fred minio.password=pass1"
	@echo "  uninstall     - Uninstall the recommender system app and clean up resources"
	@echo "  status        - Check status of the deployment"
	@echo ""
	@echo "Configuration options (set via environment variables or make arguments):"
	@echo "  NAMESPACE                - Target namespace"
	@echo "  minio.userId             - User ID to use for minio installation"
	@echo "  minio.password           - Password to use for minio installation"
	@echo "  OLLAMA_MODEL             - Ollama model to use (default: meta-llama/Llama-3.1-8B-Instruct)"
	@echo "  MODEL_ENDPOINT           - Model endpoint URL"

# Older version of oc will raise error processing some of the commands in this make file; enforce a minimum version
.PHONY: check-oc-version
check-oc-version:
	$(eval USER_OC_VERSION = $(shell oc version --client=true -o json | jq -r .clientVersion.gitVersion))
	@echo "Detected oc version on your machine: $(USER_OC_VERSION)"
	@echo "NOTE: This install script has only been tested for oc version $(MINIMUM_OC_VERSION) and the bash and zsh shells."

# Minio internally rejects user id and password values less than 3 and 8 characters, respectively
# The install will fail if this occurs, so let's catch it early
.PHONY: check-minio-credentials
check-minio-credentials:
	@if [ -z "$(minio.userId)" ]; then \
		echo "Set minio.userId to a value that is at least $(MINIMUM_USERID_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ $$(wc -m <<< $(minio.userId)) -lt $$(expr $(MINIMUM_USERID_LENGTH) + 1) ]; then \
		echo "Set minio.userId to a value that is at least $(MINIMUM_USERID_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ -z "$(minio.password)" ]; then \
		echo "Set minio.password to a value that is at least $(MINIMUM_PASSWORD_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ $$(wc -m <<< $(minio.password)) -lt $$(expr $(MINIMUM_PASSWORD_LENGTH) + 1) ]; then \
		echo "Set minio.password to a value that is at least $(MINIMUM_PASSWORD_LENGTH) characters in length."; \
		exit 1; \
	fi

# Create namespace and deploy
namespace:
	@oc create namespace $(NAMESPACE) &> /dev/null && oc label namespace $(NAMESPACE) modelmesh-enabled=false ||:
	@oc project $(NAMESPACE) &> /dev/null ||:

.PHONY: depend
depend:
	@echo "Updating Helm dependencies for $(PRODUCT_RECOMMENDER_CHART)"
	@helm dependency update $(PRODUCT_RECOMMENDER_CHART) &> /dev/null
	@echo "Updating Helm dependencies for $(MINIO_CHART)"
	@helm dependency update $(MINIO_CHART) &> /dev/null

.PHONY: install
install: check-oc-version check-minio-credentials namespace depend minio-install pipeline-server-install create-dynamic-secret product-recommender-install

.PHONY: minio-install
minio-install:
	@echo "Installing Minio helm chart and default bucket for recommender pipeline..."
	@helm -n $(NAMESPACE) upgrade --install minio $(MINIO_CHART) \
		--set minio.userId=$(minio.userId) \
		--set minio.password=$(minio.password) \
		--timeout 5m
	@echo "Waiting for Minio route 'minio-api' to become ready in namespace $(NAMESPACE)..."
	@oc wait pod -l app=minio -n $(NAMESPACE) --for=condition=Ready --timeout=60s
	@oc wait --for=jsonpath='{.status.ingress[0].conditions[?(@.type=="Admitted")].status}=True' \
		route/minio-api -n $(NAMESPACE) --timeout=60s
	@echo "Minio installation complete."

.PHONY: pipeline-server-install
pipeline-server-install:
	@echo "Discovering Minio API endpoint..."
	$(eval MINIO_API_HOST = $(shell oc get route minio-api -n $(NAMESPACE) -o jsonpath='{.spec.host}'))
	@echo "Discovered Minio API Endpoint: https://$(MINIO_API_HOST)"
	@echo "Looking up bucket and region name from config map ..."
	$(eval DEFAULT_BUCKET= $(shell oc get configmap minio-config -n $(NAMESPACE) -o json | jq -r '.data["DEFAULT_BUCKET"]'))
	@echo "Default bucket name: $(DEFAULT_BUCKET)"
	$(eval DEFAULT_REGION= $(shell oc get configmap minio-config -n $(NAMESPACE) -o json | jq -r '.data["DEFAULT_REGION"]'))
	@echo "Default region name: $(DEFAULT_REGION)"
	@echo "Installing pipeline server chart..."
	@helm -n $(NAMESPACE) upgrade --install pipeline-server $(PIPELINE_SERVER_CHART) \
		--set minio.apiEndpoint=$(MINIO_API_HOST) \
		--set minio.defaultBucket=$(DEFAULT_BUCKET) \
		--set minio.defaultRegion=$(DEFAULT_REGION) \
		--timeout 300m
	@echo "Waiting for pipeline server to start in namespace $(NAMESPACE)..."
	@for i in {1..25}; do \
        oc get pod -l app=ds-pipeline-dspa -n $(NAMESPACE) 2>/dev/null | grep -q "Running\|ContainerCreating\|Pending" && break; \
        echo "Pod not found yet, retrying (wait)..."; \
        sleep 5; \
    done
	oc wait pod -l app=ds-pipeline-dspa -n $(NAMESPACE) --for=condition=Ready --timeout=180s
	@echo "Pipeline server ready."

.PHONY: create-dynamic-secret
create-dynamic-secret:
	@echo "Creating backward compatible secret for dspa settings (temporary workaround)"
	$(eval MINIO_SERVICE_HOST = $(shell oc get svc minio-service -n $(NAMESPACE) -o=jsonpath='{.spec.clusterIP}'))
	$(eval MINIO_SERVICE_PORT = $(shell oc get svc minio-service -n $(NAMESPACE) -o=jsonpath='{.spec.ports[?(@.name=="api")].port}'))
	$(eval MINIO_ACCESS_KEY_VALUE = $(shell oc get secret minio-secret -n $(NAMESPACE) -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 --decode))
	$(eval MINIO_SECRET_KEY_VALUE = $(shell oc get secret minio-secret -n $(NAMESPACE) -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 --decode))
	@oc create secret generic ds-pipeline-s3-dspa -n $(NAMESPACE) \
		--from-literal=host=$(MINIO_SERVICE_HOST) \
		--from-literal=port=$(MINIO_SERVICE_PORT) \
		--from-literal=accesskey=$(MINIO_ACCESS_KEY_VALUE) \
		--from-literal=secretkey=$(MINIO_SECRET_KEY_VALUE) \
		--from-literal=secure=false \
		--dry-run=client -o yaml | oc apply -f -

.PHONY: product-recommender-install
product-recommender-install:
	@$(eval PGVECTOR_ARGS := $(call helm_pgvector_args))
	@$(eval DATASET_ARGS := $(call dataset_args))
	@$(eval MODEL_ARGS := $(call model_args))
	@echo "Installing $(PRODUCT_RECOMMENDER_CHART) helm chart"
	@echo "Waiting for model services to deploy. It may take around 10-15 minutes depending on the size of the database..."
	@helm -n $(NAMESPACE) upgrade --install $(PRODUCT_RECOMMENDER_CHART) $(PRODUCT_RECOMMENDER_CHART) -n $(NAMESPACE) \
		$(PGVECTOR_ARGS) \
		$(DATASET_ARGS) \
		$(MODEL_ARGS) \
		$(EXTRA_HELM_ARGS) --set strimzi-kafka-operator.createGlobalResources=false --timeout 300m
	@oc rollout status deploy
	@echo "$(PRODUCT_RECOMMENDER_CHART) installed successfully"
	@echo "Frontend URL: https://$$(oc get route product-recommender-system-frontend -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

# Uninstall the deployment and clean up
.PHONY: uninstall
uninstall: check-oc-version product-recommender-uninstall pipeline-server-uninstall minio-uninstall delete-project

.PHONY: product-recommender-uninstall
product-recommender-uninstall:
	@echo "Uninstalling $(PRODUCT_RECOMMENDER_CHART) helm chart"
	@helm -n $(NAMESPACE) uninstall $(PRODUCT_RECOMMENDER_CHART) || true
	@echo "Deleting remaining pods in namespace $(NAMESPACE) for $(PRODUCT_RECOMMENDER_CHART)"
	@oc delete jobs -n $(NAMESPACE) --all --grace-period=60 --ignore-not-found
	@oc delete pods -n $(NAMESPACE) --all --grace-period=60 --ignore-not-found

.PHONY: minio-uninstall
minio-uninstall:
	@echo "Uninstalling Minio helm chart"
	@helm -n $(NAMESPACE) uninstall minio || true
	@echo "Removing pgvector and minio PVCs from $(NAMESPACE)"
	@oc get pvc -n $(NAMESPACE) -o custom-columns=NAME:.metadata.name | grep -E '^(pg|minio)-data' | xargs -I {} oc delete pvc -n $(NAMESPACE) {} ||:
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

# Check deployment status
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

	@echo "Listing pvcs..."
	oc get pvc -n $(NAMESPACE) || true
