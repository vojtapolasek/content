# platform = multi_platform_sle,multi_platform_slmicro,Red Hat Virtualization 4,multi_platform_fedora,multi_platform_ol,multi_platform_rhel,multi_platform_ubuntu,multi_platform_almalinux

{{%- if "sle" in product or "slmicro" in product or "ubuntu" in product %}}
{{%- set pam_lastlog_path = "/etc/pam.d/login" %}}
{{%- if "ubuntu" in product %}}
{{%- set after_match = "BOF" %}}
{{%- else %}}
{{%- set after_match = "^\s*session.*include\s+common-session$" %}}
{{%- endif %}}
{{%- else %}}
{{%- set pam_lastlog_path = "/etc/pam.d/postlogin" %}}
{{%- set after_match = "^\s*session\s+.*pam_succeed_if\.so.*" %}}
{{%- endif %}}

{{%- if "ol" in product or "slmicro" in product or "ubuntu" in product %}}
{{%- set control = "required" %}}
{{%- elif "sle" in product %}}
{{%- set control = "optional" %}}
{{%- else %}}
{{%- set control = "[default=1]" %}}
{{%- endif %}}

{{{ bash_pam_lastlog_enable_showfailed(pam_lastlog_path, control, after_match) }}}
