# PDSNO Operational Runbook

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Common Tasks](#common-tasks)
4. [Troubleshooting](#troubleshooting)
5. [Emergency Procedures](#emergency-procedures)
6. [Maintenance](#maintenance)

---

## 1. System Overview

### Architecture
Global Controller (validates RCs, approves HIGH configs)
↓
Regional Controllers (validates LCs, approves MEDIUM, manages regions)
↓
Local Controllers (discovers devices, auto-approves LOW, executes configs)
↓
Network Devices (switches, routers being managed)

### Key Components
- **Controllers:** Global, Regional, Local
- **NIB:** Network Information Base (SQLite/PostgreSQL)
- **MQTT:** Message broker for async communication
- **REST API:** HTTP endpoints for external access
- **Automation:** Ansible playbooks for device configuration

### Critical Files
- Config: `/opt/pdsno/config/context_runtime.yaml`
- Database: `/opt/pdsno/data/pdsno.db`
- Secrets: `/opt/pdsno/config/*.key`
- Certificates: `/etc/pdsno/certs/`
- Logs: `/opt/pdsno/logs/` and `/var/log/pdsno/`

---

## 2. Daily Operations

### Morning Checklist
```bash
# 1. Check controller status
systemctl status pdsno-controller

# 2. Check health endpoint
curl http://localhost:8001/health

# 3. Check logs for errors
journalctl -u pdsno-controller --since "24 hours ago" | grep ERROR

# 4. Check database size
du -h /opt/pdsno/data/pdsno.db

# 5. Verify recent backups
ls -lh /opt/pdsno/data/backups/ | tail -5
```

### Monitoring Metrics

Check Prometheus metrics:
```bash
curl http://localhost:9090/metrics | grep pdsno
```

Key metrics to watch:
- `pdsno_active_controllers` - Should match expected count
- `pdsno_validation_requests_total` - Track validation activity
- `pdsno_config_approvals_total` - Monitor approval rate
- `pdsno_message_latency_seconds` - Check performance

### Log Rotation

Ensure logs are rotating properly:
```bash
# Check log rotation config
cat /etc/logrotate.d/pdsno

# Manual rotation if needed
logrotate -f /etc/logrotate.d/pdsno
```

---

## 3. Common Tasks

### Task 1: Starting/Stopping Controllers
```bash
# Start controller
sudo systemctl start pdsno-controller

# Stop controller
sudo systemctl stop pdsno-controller

# Restart controller
sudo systemctl restart pdsno-controller

# Check status
sudo systemctl status pdsno-controller

# View logs
journalctl -u pdsno-controller -f
```

### Task 2: Adding a New Device
```bash
# 1. Ensure device is reachable
ping 192.168.1.100

# 2. Add device credentials to secret manager
python scripts/add_device_credentials.py \
    --device-id switch-new-01 \
    --ip 192.168.1.100 \
    --username admin \
    --password <secure-password>

# 3. Run discovery
python scripts/run_discovery.py --subnet 192.168.1.0/24

# 4. Verify device in NIB
sqlite3 /opt/pdsno/data/pdsno.db \
    "SELECT device_id, ip_address, status FROM devices WHERE ip_address='192.168.1.100';"
```

### Task 3: Approving a Configuration
```bash
# 1. List pending configurations
curl http://localhost:8001/api/v1/configs?status=pending

# 2. Review configuration
curl http://localhost:8001/api/v1/configs/{config_id}

# 3. Approve (requires RBAC permissions)
curl -X POST http://localhost:8001/api/v1/configs/{config_id}/approve \
    -H "Authorization: Bearer {token}" \
    -d '{"approver_id": "admin_user"}'
```

### Task 4: Rolling Back a Configuration
```bash
# 1. List backups for device
curl http://localhost:8001/api/v1/devices/{device_id}/backups

# 2. Initiate rollback
ansible-playbook pdsno/automation/playbooks/rollback.yaml \
    -e "device_id=switch-01" \
    -e "backup_id={backup_id}"

# 3. Verify rollback
curl http://localhost:8001/api/v1/devices/{device_id}/status
```

### Task 5: Generating Bootstrap Token
```bash
# For Regional Controller
python scripts/generate_bootstrap_token.py \
    --region zone-A \
    --type regional

# Save the token and temp ID for controller provisioning
```

### Task 6: Database Backup
```bash
# Manual backup
sqlite3 /opt/pdsno/data/pdsno.db ".backup '/opt/pdsno/data/backups/pdsno_$(date +%Y%m%d_%H%M%S).db'"

# Automated backup (add to cron)
0 2 * * * /opt/pdsno/scripts/backup_database.sh
```

### Task 7: Certificate Renewal
```bash
# Check certificate expiration
openssl x509 -in /etc/pdsno/certs/controller-cert.pem -noout -enddate

# Renew certificates (generates new ones)
bash /opt/pdsno/scripts/generate_certs.sh

# Restart controller to load new certs
sudo systemctl restart pdsno-controller
```

---

## 4. Troubleshooting

### Issue: Controller Won't Start

**Symptoms:**
- `systemctl status pdsno-controller` shows failed
- Logs show startup errors

**Diagnosis:**
```bash
# Check logs
journalctl -u pdsno-controller -n 50

# Check configuration
python -c "import yaml; yaml.safe_load(open('/opt/pdsno/config/context_runtime.yaml'))"

# Check database
sqlite3 /opt/pdsno/data/pdsno.db ".schema"

# Check permissions
ls -la /opt/pdsno/config/*.key
```

**Resolution:**
```bash
# Fix permissions
sudo chown -R pdsno:pdsno /opt/pdsno
sudo chmod 600 /opt/pdsno/config/*.key

# Reinitialize database if corrupted
mv /opt/pdsno/data/pdsno.db /opt/pdsno/data/pdsno.db.backup
python scripts/init_db.py

# Restart
sudo systemctl restart pdsno-controller
```

### Issue: Device Discovery Failing

**Symptoms:**
- No new devices appearing in NIB
- Discovery logs show errors

**Diagnosis:**
```bash
# Check network connectivity
ping <device_ip>

# Check SNMP
snmpwalk -v2c -c public <device_ip> system

# Check ARP
arp -a | grep <device_ip>

# Check discovery logs
journalctl -u pdsno-controller | grep discovery
```

**Resolution:**
```bash
# Verify credentials
python scripts/test_device_connection.py --ip <device_ip>

# Run manual discovery
python scripts/run_discovery.py --subnet <subnet> --verbose

# Check firewall
sudo firewall-cmd --list-all
```

### Issue: Config Approval Stuck

**Symptoms:**
- Configuration remains in PENDING_APPROVAL state
- No approval workflow triggered

**Diagnosis:**
```bash
# Check config status
sqlite3 /opt/pdsno/data/pdsno.db \
    "SELECT config_id, status, sensitivity, created_at FROM config_records WHERE status='PENDING_APPROVAL';"

# Check approval engine logs
journalctl -u pdsno-controller | grep approval

# Verify approver permissions
python scripts/check_rbac.py --entity-id <approver_id>
```

**Resolution:**
```bash
# Manual approval via API
curl -X POST http://localhost:8001/api/v1/configs/{config_id}/approve \
    -H "Authorization: Bearer {admin_token}"

# Or reset config status
sqlite3 /opt/pdsno/data/pdsno.db \
    "UPDATE config_records SET status='DRAFT' WHERE config_id='{config_id}';"
```

### Issue: High Message Latency

**Symptoms:**
- Prometheus metrics show high latency
- Validation taking >1 second

**Diagnosis:**
```bash
# Check metrics
curl http://localhost:9090/metrics | grep pdsno_message_latency

# Check system resources
top
df -h
free -m

# Check database size
du -h /opt/pdsno/data/pdsno.db

# Check MQTT broker
systemctl status mosquitto
```

**Resolution:**
```bash
# Restart MQTT broker
sudo systemctl restart mosquitto

# Clean old data from database
python scripts/cleanup_old_data.py --older-than 30days

# Increase resources (if containerized)
# Edit docker-compose.yml or K8s deployment
```

---

## 5. Emergency Procedures

### Emergency: Critical Security Breach

1. **Immediate Actions:**
```bash
   # Stop all controllers
   sudo systemctl stop pdsno-controller
   
   # Block external access
   sudo firewall-cmd --add-rich-rule='rule family="ipv4" port port="8001" protocol="tcp" reject'
   
   # Alert team
```

2. **Investigation:**
```bash
   # Check audit logs
   sqlite3 /opt/pdsno/data/pdsno.db \
       "SELECT * FROM events WHERE severity='CRITICAL' ORDER BY timestamp DESC LIMIT 100;"
   
   # Check authentication attempts
   grep "authentication" /var/log/pdsno/controller.log
```

3. **Recovery:**
```bash
   # Rotate all secrets
   python scripts/rotate_secrets.py --all
   
   # Regenerate certificates
   bash scripts/generate_certs.sh
   
   # Restart with new credentials
   sudo systemctl start pdsno-controller
```

### Emergency: Database Corruption

1. **Immediate Actions:**
```bash
   # Stop controller
   sudo systemctl stop pdsno-controller
   
   # Backup corrupted database
   cp /opt/pdsno/data/pdsno.db /opt/pdsno/data/pdsno.db.corrupted
```

2. **Recovery:**
```bash
   # Try SQLite recovery
   sqlite3 /opt/pdsno/data/pdsno.db ".recover" | sqlite3 /opt/pdsno/data/pdsno_recovered.db
   
   # If recovery fails, restore from backup
   cp /opt/pdsno/data/backups/latest_backup.db /opt/pdsno/data/pdsno.db
   
   # Verify integrity
   sqlite3 /opt/pdsno/data/pdsno.db "PRAGMA integrity_check;"
   
   # Restart
   sudo systemctl start pdsno-controller
```

### Emergency: Controller Crash Loop

1. **Diagnosis:**
```bash
   # Check crash logs
   journalctl -u pdsno-controller -n 200
   
   # Check core dumps
   coredumpctl list
```

2. **Recovery:**
```bash
   # Start in safe mode (if available)
   python scripts/run_controller.py --safe-mode
   
   # Reset to known-good configuration
   cp /opt/pdsno/config/context_runtime.yaml.backup \
      /opt/pdsno/config/context_runtime.yaml
   
   # Restart
   sudo systemctl start pdsno-controller
```

---

## 6. Maintenance

### Weekly Maintenance
```bash
# 1. Review logs for warnings
journalctl -u pdsno-controller --since "1 week ago" | grep -E "WARN|ERROR"

# 2. Check disk space
df -h /opt/pdsno

# 3. Verify backups
ls -lh /opt/pdsno/data/backups/

# 4. Run security audit
python scripts/security_audit.py

# 5. Update metrics dashboard
# Review Grafana dashboards
```

### Monthly Maintenance
```bash
# 1. Update dependencies
pip install -r requirements.txt --upgrade

# 2. Rotate secrets
python scripts/rotate_secrets.py

# 3. Clean old data
python scripts/cleanup_old_data.py --older-than 90days

# 4. Performance analysis
python scripts/analyze_performance.py --month

# 5. Generate compliance report
python scripts/generate_compliance_report.py
```

### Quarterly Maintenance
```bash
# 1. Full security audit
python scripts/security_audit.py --comprehensive

# 2. Disaster recovery drill
# Test restore from backup

# 3. Capacity planning review
# Check growth metrics, plan scaling

# 4. Update documentation
# Review and update runbook

# 5. Certificate renewal
bash scripts/generate_certs.sh
```

---

## 7. Contacts

### Escalation Path

**Level 1:** On-call Engineer
- Check runbook
- Basic troubleshooting
- Escalate if needed

**Level 2:** Senior Engineer
- Complex issues
- Performance problems
- Security incidents

**Level 3:** System Architect
- Architecture decisions
- Major incidents
- Design changes

### External Contacts

- **Vendor Support:** (for device issues)
- **Cloud Provider:** (if using cloud infrastructure)
- **Security Team:** (for security incidents)

---

## 8. Appendix

### Useful Commands Cheat Sheet
```bash
# Health check
curl http://localhost:8001/health

# View active devices
sqlite3 /opt/pdsno/data/pdsno.db "SELECT device_id, ip_address, status FROM devices WHERE status='active';"

# Check controller status
systemctl status pdsno-controller

# Tail logs
journalctl -u pdsno-controller -f

# Run discovery
python scripts/run_discovery.py --subnet 192.168.1.0/24

# Generate token
python scripts/generate_bootstrap_token.py --region zone-A --type regional

# Database backup
sqlite3 /opt/pdsno/data/pdsno.db ".backup '/opt/pdsno/data/backups/backup_$(date +%Y%m%d).db'"
```

### Configuration Files

- **Main config:** `/opt/pdsno/config/context_runtime.yaml`
- **Policy:** `/opt/pdsno/config/policy_default.yaml`
- **Systemd:** `/etc/systemd/system/pdsno-controller.service`
- **Certificates:** `/etc/pdsno/certs/`

---

**Document Version:** 1.0
**Last Updated:** 2026-02-25
**Next Review:** 2026-03-25