---
documentation_complete: true

metadata:
    SMEs:
        - marcusburghardt

reference: https://www.cisecurity.org/benchmark/red_hat_linux/

title: 'DRAFT - CIS Red Hat Enterprise Linux 10 Benchmark for Level 1 - Server'

description: |-
    This is a draft profile for experimental purposes.
    It is based on the CIS RHEL 9 profile, because an equivalent policy for RHEL 10 didn't yet
    exist at time of the release.

selections:
    - cis_rhel10:all:l1_server
    - var_authselect_profile=local
