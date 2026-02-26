#!/bin/bash
# PDSNO Installation Script
# Supports: Ubuntu 20.04+, CentOS 8+, Debian 11+

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PDSNO_VERSION="${PDSNO_VERSION:-1.0.0}"
PDSNO_HOME="${PDSNO_HOME:-/opt/pdsno}"
PDSNO_USER="${PDSNO_USER:-pdsno}"
INSTALL_TYPE="${INSTALL_TYPE:-global}"  # global, regional, local

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "Cannot detect OS"
        exit 1
    fi
    
    log_info "Detected OS: $OS $VER"
}

install_dependencies() {
    log_info "Installing dependencies..."
    
    case "$OS" in
        ubuntu|debian)
            apt-get update
            apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                postgresql-client \
                mosquitto \
                git \
                curl \
                openssl
            ;;
        centos|rhel|rocky)
            yum install -y \
                python3 \
                python3-pip \
                postgresql \
                mosquitto \
                git \
                curl \
                openssl
            ;;
        *)
            log_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    
    log_info "✓ Dependencies installed"
}

create_user() {
    if id "$PDSNO_USER" &>/dev/null; then
        log_info "User $PDSNO_USER already exists"
    else
        log_info "Creating user $PDSNO_USER..."
        useradd -r -s /bin/bash -d "$PDSNO_HOME" -m "$PDSNO_USER"
    fi
}

create_directories() {
    log_info "Creating directories..."
    
    mkdir -p "$PDSNO_HOME"/{data,logs,config,backups}
    mkdir -p /etc/pdsno/certs
    
    chown -R "$PDSNO_USER:$PDSNO_USER" "$PDSNO_HOME"
    chmod 755 "$PDSNO_HOME"
    
    log_info "✓ Directories created"
}

install_pdsno() {
    log_info "Installing PDSNO $PDSNO_VERSION..."
    
    cd "$PDSNO_HOME"
    
    # Clone repository or download release
    if [ -d ".git" ]; then
        log_info "Git repository exists, pulling latest..."
        sudo -u "$PDSNO_USER" git pull
    else
        log_info "Cloning repository..."
        sudo -u "$PDSNO_USER" git clone https://github.com/your-org/pdsno.git .
    fi
    
    # Create virtual environment
    log_info "Creating Python virtual environment..."
    sudo -u "$PDSNO_USER" python3 -m venv venv
    
    # Install Python dependencies
    log_info "Installing Python packages..."
    sudo -u "$PDSNO_USER" bash -c "source venv/bin/activate && pip install -r requirements.txt"
    
    log_info "✓ PDSNO installed"
}

generate_certificates() {
    log_info "Generating TLS certificates..."
    
    if [ -f /etc/pdsno/certs/controller-cert.pem ]; then
        log_warn "Certificates already exist, skipping..."
        return
    fi
    
    cd "$PDSNO_HOME"
    bash scripts/generate_certs.sh
    
    log_info "✓ Certificates generated"
}

initialize_database() {
    log_info "Initializing database..."
    
    sudo -u "$PDSNO_USER" bash -c "source venv/bin/activate && python scripts/init_db.py --db $PDSNO_HOME/data/pdsno.db"
    
    log_info "✓ Database initialized"
}

generate_secrets() {
    log_info "Generating secrets..."
    
    # Generate master key
    MASTER_KEY=$(openssl rand -hex 32)
    echo "$MASTER_KEY" > "$PDSNO_HOME/config/master.key"
    chmod 600 "$PDSNO_HOME/config/master.key"
    
    # Generate bootstrap secret
    BOOTSTRAP_SECRET=$(openssl rand -hex 32)
    echo "$BOOTSTRAP_SECRET" > "$PDSNO_HOME/config/bootstrap_secret.key"
    chmod 600 "$PDSNO_HOME/config/bootstrap_secret.key"
    
    chown "$PDSNO_USER:$PDSNO_USER" "$PDSNO_HOME/config"/*.key
    
    log_info "✓ Secrets generated"
}

configure_systemd() {
    log_info "Configuring systemd service..."
    
    # Copy service file
    cp "$PDSNO_HOME/deployment/pdsno-controller.service" /etc/systemd/system/
    
    # Customize for controller type
    sed -i "s/--type global/--type $INSTALL_TYPE/" /etc/systemd/system/pdsno-controller.service
    
    # Reload systemd
    systemctl daemon-reload
    systemctl enable pdsno-controller
    
    log_info "✓ Systemd service configured"
}

configure_firewall() {
    log_info "Configuring firewall..."
    
    # UFW (Ubuntu/Debian)
    if command -v ufw &> /dev/null; then
        ufw allow 8001/tcp  # REST API
        ufw allow 9090/tcp  # Metrics
        log_info "✓ UFW rules added"
    fi
    
    # firewalld (CentOS/RHEL)
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=8001/tcp
        firewall-cmd --permanent --add-port=9090/tcp
        firewall-cmd --reload
        log_info "✓ firewalld rules added"
    fi
}

show_completion() {
    log_info ""
    log_info "======================================"
    log_info "PDSNO Installation Complete!"
    log_info "======================================"
    log_info ""
    log_info "Controller Type: $INSTALL_TYPE"
    log_info "Installation Path: $PDSNO_HOME"
    log_info "User: $PDSNO_USER"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit configuration: $PDSNO_HOME/config/context_runtime.yaml"
    log_info "  2. Start controller: systemctl start pdsno-controller"
    log_info "  3. Check status: systemctl status pdsno-controller"
    log_info "  4. View logs: journalctl -u pdsno-controller -f"
    log_info ""
    log_info "Important files:"
    log_info "  - Master key: $PDSNO_HOME/config/master.key"
    log_info "  - Bootstrap secret: $PDSNO_HOME/config/bootstrap_secret.key"
    log_info "  - TLS certs: /etc/pdsno/certs/"
    log_info ""
    log_info "⚠️  BACKUP THE SECRET FILES SECURELY!"
    log_info ""
}

# Main installation flow
main() {
    echo ""
    echo "======================================"
    echo "PDSNO Installer"
    echo "======================================"
    echo ""
    
    check_root
    detect_os
    
    log_info "Installing PDSNO ($INSTALL_TYPE controller)..."
    echo ""
    
    install_dependencies
    create_user
    create_directories
    install_pdsno
    generate_certificates
    initialize_database
    generate_secrets
    configure_systemd
    configure_firewall
    
    show_completion
}

# Run main function
main "$@"