---
documentation_complete: true

platform: ocp4-node

metadata:
    version: 4.0.0
    SMEs:
        - rhmdnd
        - Vincent056
        - yuumasato

reference: https://www.pcisecuritystandards.org/document_library/

title: 'PCI-DSS v4.0.0 Control Baseline for Red Hat OpenShift Container Platform 4'

description: |-
    Ensures PCI-DSS v4.0.0 security configuration settings are applied.

filter_rules: '"ocp4-node" in platform or "ocp4-master-node" in platform or "ocp4-node-on-sdn" in platform
    or "ocp4-node-on-ovn" in platform'

selections:
    - pcidss_4_ocp4:all:base
