# Product Recommender System - Helm Deployment

This directory contains the Helm chart and deployment configuration for the Product Recommender System. The deployment is managed through a Makefile that provides various commands for installation, uninstallation, and status checking.

## Prerequisites

- OpenShift CLI (`oc`) installed and configured
- Helm 3.x installed
- Access to an OpenShift cluster with necessary permissions

## Configuration

The following environment variables can be configured:

- `NAMESPACE` (Required): The OpenShift namespace where the system will be deployed

## Available Commands

### Install the System

To install the product recommender system:

```bash
make install NAMESPACE=your-namespace storage.accessKeyId=fred storage.secretAccessKey=pass0123
```

The storage.accessKeyId and storage.secretAccessKey configure the S3-compatible storage credentials used by the OpenShift Pipeline Application Server.

Both `storage.accessKeyId` and `storage.secretAccessKey` must be provided.

The install command will:

1. Create the specified namespace if it doesn't exist
2. Update Helm dependencies
3. Install/upgrade the Helm chart with the configured settings
4. Install S3-compatible object storage, create the recommender bucket, and install the pipeline application server.
5. Wait for the deployment to complete (typically 10-15 minutes depending on the model size)

### Check Deployment Status

To check the status of your deployment:

```bash
make status NAMESPACE=your-namespace
```

This will show:

- Running pods
- Active services
- Available routes
- Hugging Face secrets
- Persistent Volume Claims (PVCs)

### Uninstall the System

To uninstall the product recommender system:

```bash
make uninstall NAMESPACE=your-namespace
```

This will:

1. Uninstall the Helm chart
2. Delete all pods in the namespace
3. Display remaining resources in the namespace

CAUTION: THE UNINSTALL WILL REMOVE YOUR NAMESPACE AND ALL RESOURCES AND DATA IT CONTAINS.

## Additional Configuration

You can pass additional Helm arguments using the `EXTRA_HELM_ARGS` variable:

```bash
make install NAMESPACE=your-namespace EXTRA_HELM_ARGS="--set key=value"
```
