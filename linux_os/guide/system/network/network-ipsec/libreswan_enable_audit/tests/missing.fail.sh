#!/bin/bash

cat > /etc/ipsec.conf << EOM
# some comment
config setup
 somevalue true


EOM
