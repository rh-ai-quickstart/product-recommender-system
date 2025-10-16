# Recommendation Training Container

This directory contains the container image for the recommendation training workflow.

## Container Architecture

### Training Pipeline Image (`recommendation-training`)
- **Purpose**: ML training workflow and data processing
- **Base Image**: `registry.access.redhat.com/ubi9/python-311`
- **Contents**: Python dependencies, training scripts, ML libraries
- **Usage**: Training, data processing, model training, candidate generation

## Build Process

### Local Build

```bash
cd recommendation-training
podman build -t quay.io/rh-ai-quickstart/recommendation-training:latest .
```

### Push to Registry

```bash
podman push quay.io/rh-ai-quickstart/recommendation-training:latest
```

### Automated Build

The container is automatically built and pushed via GitHub Actions when:
- Changes are pushed to the `main` or `master` branch
- The workflow is manually triggered

**Workflow:**
- `.github/workflows/build-and-push.yaml` - Training pipeline image

## Container Contents

### Training Image (`recommendation-training`)
- **Base Image**: `registry.access.redhat.com/ubi9/python-311`
- **User**: `root`
- **Working Directory**: `/app`
- **Dependencies**:
  - Python packages via `uv`
  - ML training libraries (PyTorch, transformers, etc.)
  - Training scripts and utilities
  - Feast integration for feature store operations

## Key Files

- `Containerfile`: Container definition
- `train-workflow.py`: Kubeflow pipeline definition
- `entrypoint.sh`: Container entry point
- `pyproject.toml`: Python dependencies

## Pipeline Workflow

The training pipeline performs these key steps:

1. **Load Data from Feast**: Retrieves training data from the feature store
2. **Train Model**: Creates and trains the two-tower recommendation model
3. **Save Models**: Stores trained models in MinIO object storage
4. **Generate Candidates**: Creates embeddings and pre-calculated recommendations
5. **Update Feature Store**: Pushes new features and recommendations to Feast

## Usage

### Training Pipeline
```yaml
containers:
- name: kfp-runner
  image: quay.io/rh-ai-quickstart/recommendation-training:latest
  command: ['/bin/sh']
  args: ['-c', './entrypoint.sh']
```

### Model Management

The system uses a simplified model management approach:
- **Storage**: Models saved directly to MinIO object storage
- **Versioning**: Tracked via database `model_version` table
- **Loading**: Direct access from MinIO for better performance

## GitHub Actions

The automated build process requires:
- `QUAY_USERNAME`: Quay.io username
- `QUAY_PASSWORD`: Quay.io password/token

These secrets must be configured in the GitHub repository settings.

## Benefits of Current Architecture

1. **Simplified Design**: Single-purpose container for training operations
2. **Direct Model Access**: No intermediate model registry layers
3. **Better Performance**: Faster model loading and deployment
4. **Easier Maintenance**: Fewer moving parts and dependencies
5. **Resource Efficient**: Reduced infrastructure requirements
