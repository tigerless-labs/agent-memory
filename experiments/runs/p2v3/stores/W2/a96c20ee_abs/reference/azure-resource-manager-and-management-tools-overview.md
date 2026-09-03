---
name: azure-resource-manager-and-management-tools-overview
abstract: Azure Resource Manager and management tools overview
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-21
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

# Azure Resource Manager (ARM)

Azure Resource Manager enables managing resources in Azure as a group. You can deploy, update, or delete all resources for a solution in a single coordinated operation using templates for deployment across environments (testing, staging, production). ARM provides security, auditing, and tagging features. It provides a consistent management layer accessible through Azure PowerShell, Azure CLI, Azure portal, REST API, and client SDKs.

## Azure Management Tools Comparison

**Azure PowerShell**: A module that extends PowerShell with Azure-specific commands. Requires PowerShell to function, available on Windows PowerShell and PowerShell Core. Allows connection to Azure subscriptions and resource management.

**Azure CLI**: A cross-platform command-line program for executing administrative commands on Azure resources. Runs on Linux, macOS, and Windows. Can be installed locally on computers.

**Azure Cloud Shell**: An interactive, browser-accessible shell for managing Azure resources. Runs on a temporary host provided per-session, per-user basis. Requires a resource group, storage account, and Azure File share. Includes integrated graphical text editor (Monaco Editor) and automatic authentication.

## Benefits of Resource Manager Templates

1. **Consistency**: Common language for deployments—structure, format, and expressions remain the same regardless of deployment tool or SDK
2. **Complex deployments**: Enable deploying multiple resources in correct order; ARM maps resources and dependencies, creating dependent resources first
3. **Reduced manual errors**: Ensures deployment happens the same way every time
4. **Code-based (Infrastructure as Code)**: Templates can be shared, tested, versioned, and documented; creates paper trail
5. **Reusability**: Parameters enable creating multiple infrastructure versions (staging/production) using exact same template
6. **Modularity**: Templates are linkable—combine small modular templates to create complete systems
7. **Simplified orchestration**: Deploy single template to deploy all resources instead of multiple operations
