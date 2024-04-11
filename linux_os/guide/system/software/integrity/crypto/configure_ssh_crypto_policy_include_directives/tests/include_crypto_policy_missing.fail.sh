#!/usr/bin/bash

sed -i '/\s*Include /etc/crypto-policies/back-ends/opensshserver.config/d' /etc/ssh/sshd_config.d/*
