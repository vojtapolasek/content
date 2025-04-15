# platform = Red Hat Virtualization 4,multi_platform_fedora,multi_platform_ol,multi_platform_rhel,multi_platform_sle,multi_platform_slmicro,multi_platform_almalinux

(IFS=:
echo "$PATH"
for p in $PATH; do
    if [[ -d $p ]]; then
        chmod o-w,g-w $p
        echo "$p"
    fi
done)
