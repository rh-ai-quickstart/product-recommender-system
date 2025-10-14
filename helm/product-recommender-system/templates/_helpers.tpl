{{/*
Expand the name of the chart.
*/}}
{{- define "product-recommender-system.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "product-recommender-system.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "product-recommender-system.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "product-recommender-system.labels" -}}
helm.sh/chart: {{ include "product-recommender-system.chart" . }}
{{ include "product-recommender-system.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "product-recommender-system.selectorLabels" -}}
app.kubernetes.io/name: {{ include "product-recommender-system.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "product-recommender-system.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "product-recommender-system.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "product-recommender-system.feastEnv" -}}
- name: FEAST_PROJECT_NAME
  value: {{ .Values.feast.project }}
- name: FEAST_SECRET_NAME
  value: {{ .Values.feast.secret }}
- name: FEAST_REGISTRY_URL
  value: {{ .Values.feast.registry }}.{{ .Release.Namespace }}.svc.cluster.local
{{- end }}

{{/*
Define the pipeline job template that can be reused in both Job and CronJob
*/}}
{{- define "product-recommender-system.pipeline-job-template" -}}
metadata:
  labels:
    pipelines.kubeflow.org/v2_component: 'true'
spec:
  serviceAccountName: pipeline-runner-dspa
  initContainers:
    - name: wait-for-pipeline
      image: {{ .Values.pipelineJobImage }}
      command:
        - /bin/bash
        - -c
        - |
          set -e
          url="https://ds-pipeline-dspa:8888/apis/v2beta1/healthz"
          echo "Waiting for $url..."
          until curl -ksf "$url"; do
            echo "Still waiting for $url ..."
            sleep 10
          done
    - name: wait-for-feast-apply
      image: registry.redhat.io/openshift4/ose-cli:latest
      command:
        - /bin/bash
        - -c
        - |
          set -e
          echo "Waiting for feast-apply-job to complete..."
          until oc get job feast-apply-job -n {{ .Release.Namespace }} -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' | grep -q "True"; do
            echo "Still waiting for feast-apply-job..."
            sleep 10
          done
          echo "Feast apply job completed successfully"
  containers:
  - name: kfp-runner
    image: {{ .Values.pipelineJobImage }}
    imagePullPolicy: Always
    env:
      - name: PIPELINE_NAME
        value: 'batch_training'
      - name: EXPERIMENT_NAME
        value: 'Default'
      - name: DS_PIPELINE_URL
        value: https://ds-pipeline-dspa.{{ .Release.Namespace }}.svc.cluster.local:8888
      - name: DB_SECRET_NAME
        value: pgvector
      - name: MINIO_SECRET_NAME
        value: ds-pipeline-s3-dspa
      - name: BASE_REC_SYS_IMAGE
        value: {{ .Values.applicationImage }}
      - name: DATASET_URL
        value: {{ .Values.datasetUrl }}
    {{- include "product-recommender-system.feastEnv" . | nindent 6 }}
    command: ['/bin/sh']
    args: ['-c', 'export RUN_NAME="batch_training_$(date +%Y_%m_%d_%H_%M_%S)" && ./entrypoint.sh']
  restartPolicy: Never
{{- end }}
