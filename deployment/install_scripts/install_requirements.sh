#!/bin/bash
# Install system requirements for PDSNO

set -e

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Installing requirements for $OS..."

case "$OS" in
    ubuntu|debian)
        apt-get update
        apt-get install -y \
            python3.10 \
            python3-pip \
            python3-venv \
            postgresql-15 \
            postgresql-client-15 \
            mosquitto \
            mosquitto-clients \
            redis-server \
            git \
            curl \
            wget \
            openssl \
            build-essential \
            libssl-dev \
            libffi-dev \
            python3-dev
        ;;
    
    centos|rhel|rocky)
        yum install -y epel-release
        yum install -y \
            python3 \
            python3-pip \
            python3-devel \
            postgresql15-server \
            postgresql15 \
            mosquitto \
            redis \
            git \
            curl \
            wget \
            openssl \
            gcc \
            gcc-c++ \
            make
        
        # Initialize PostgreSQL
        /usr/pgsql-15/bin/postgresql-15-setup initdb
        systemctl enable postgresql-15
        systemctl start postgresql-15
        ;;
    
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

echo "✓ Requirements installed successfully"