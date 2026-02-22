# Briven Installation Guide

> **Purpose:** Step-by-step guide for deploying Briven instances on VPS/dedicated servers  
> **Author:** Auto-generated from deployment experience  
> **Last Updated:** December 21 2025  
> **Compatibility:** Docker-capable Linux servers (AlmaLinux, CentOS, Rocky, Ubuntu, Debian)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Installation](#docker-installation)
3. [Briven Container Deployment](#briven-container-deployment)
4. [Apache Reverse Proxy Configuration](#apache-reverse-proxy-configuration)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Authentication Setup](#authentication-setup)
7. [Domain & DNS Setup](#domain--dns-setup)
8. [Verification & Testing](#verification--testing)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance & Updates](#maintenance--updates)
11. [Quick Reference](#quick-reference)

---

## Prerequisites

### Server Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **RAM**     | 2 GB    | 4+ GB       |
| **Storage** | 20 GB   | 50+ GB      |
| **CPU**     | 1 vCPU  | 2+ vCPU     |
| **OS**      | Linux (64-bit) | AlmaLinux 9, Ubuntu 22.04+ |
| **Network** | Static IP | Dedicated IP with reverse DNS |

### Required Access

- Root or sudo access to the server
- SSH access (preferably on non-standard port)
- Domain/subdomain with DNS control
- SSL certificate (Let's Encrypt or commercial)

### Software Dependencies

- Docker Engine 24.0+
- Apache 2.4+ with mod_proxy, mod_proxy_http, mod_proxy_wstunnel, mod_ssl, mod_rewrite
- curl, git (optional)

---

## Docker Installation

> [!NOTE]
> For detailed Docker installation instructions and alternative methods, see the [Linux Installation section](installation.md#linux-installation) in the main installation guide.

### Method A: Debian/Ubuntu Systems

```bash
# Update package index
apt-get update

# Install prerequisites
apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu   $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |   tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
systemctl enable docker
systemctl start docker
```

### Method B: AlmaLinux/Rocky/CentOS/RHEL Systems

```bash
# Install required packages
dnf -y install dnf-plugins-core

# Add Docker repository (use CentOS repo for AlmaLinux/Rocky)
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker
dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
systemctl enable docker
systemctl start docker
```

### Method C: Generic (Convenience Script)

> ⚠️ **Note:** May not work on all distributions (e.g., AlmaLinux)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl enable docker
systemctl start docker
```

### Verify Docker Installation

```bash
docker --version
docker run hello-world
```

---

## Briven Container Deployment

### Step 1: Create Directory Structure

```bash
# Choose your installation path
BRIVEN_NAME="briven-instance"  # Change this to your instance name
BRIVEN_PATH="/opt/${BRIVEN_NAME}"

# Create directories
mkdir -p ${BRIVEN_PATH}
mkdir -p ${BRIVEN_PATH}/work_dir
mkdir -p ${BRIVEN_PATH}/memory
mkdir -p ${BRIVEN_PATH}/logs
```

### Step 2: Create Environment Configuration

```bash
# Create .env file with authentication
cat > ${BRIVEN_PATH}/.env << 'EOF'
# Briven Configuration
# Authentication (REQUIRED for web access)
AUTH_LOGIN=your_username_here
AUTH_PASSWORD=your_secure_password_here

# Optional: Additional configuration
# See Briven documentation for all options
EOF
```

> ⚠️ **CRITICAL:** `AUTH_LOGIN` is the **username**, not a boolean!
> - ✅ Correct: `AUTH_LOGIN=admin`
> - ❌ Wrong: `AUTH_LOGIN=true`

### Step 3: Choose Host Port

| Port | Use Case |
|------|----------|
| `50080` | Standard/recommended for reverse proxy setups |
| `50081`, `50082`... | Additional instances on same server |
| `80` | Direct access (not recommended for production) |

### Step 4: Pull and Run Container

```bash
# Set variables
BRIVEN_NAME="briven-instance"
BRIVEN_PATH="/opt/${BRIVEN_NAME}"
BRIVEN_PORT="50080"

# Pull latest image
docker pull briven/briven:latest

# Run container
docker run -d   --name ${BRIVEN_NAME}   --restart unless-stopped   -p ${BRIVEN_PORT}:80   -v ${BRIVEN_PATH}/.env:/briven/.env   -v ${BRIVEN_PATH}/usr:/briven/usr   briven/briven:latest
```

### Step 5: Verify Container

```bash
# Check container is running
docker ps | grep ${BRIVEN_NAME}

# Check logs
docker logs ${BRIVEN_NAME}

# Test local access
curl -I http://127.0.0.1:${BRIVEN_PORT}/
```

Expected response: `HTTP/1.1 302 FOUND` with `Location: /login` (if auth enabled)

---

## Apache Reverse Proxy Configuration

### Required Apache Modules

```bash
# Debian/Ubuntu
a2enmod proxy proxy_http proxy_wstunnel ssl rewrite headers
systemctl restart apache2

# AlmaLinux/CentOS (usually pre-loaded)
httpd -M | grep -E "proxy|rewrite|ssl"
```

### Configuration for Standard Apache (Debian/Ubuntu)

Create `/etc/apache2/sites-available/briven-instance.conf`:

```apache
# Briven Reverse Proxy Configuration
# Instance: briven-instance
# Domain: briven.example.com

# HTTP - Redirect to HTTPS
<VirtualHost *:80>
    ServerName briven.example.com
    ServerAlias www.briven.example.com

    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</VirtualHost>

# HTTPS - Proxy to Container
<VirtualHost *:443>
    ServerName briven.example.com
    ServerAlias www.briven.example.com
    ServerAdmin webmaster@example.com

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /path/to/certificate.crt
    SSLCertificateKeyFile /path/to/private.key
    SSLCertificateChainFile /path/to/chain.crt

    # Proxy Configuration
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:50080/
    ProxyPassReverse / http://127.0.0.1:50080/

    # WebSocket Support (Required for real-time features)
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/?(.*) ws://127.0.0.1:50080/$1 [P,L]

    # Logging
    ErrorLog ${APACHE_LOG_DIR}/briven-instance.error.log
    CustomLog ${APACHE_LOG_DIR}/briven-instance.access.log combined
</VirtualHost>
```

Enable and restart:

```bash
a2ensite briven-instance.conf
apache2ctl configtest
systemctl reload apache2
```

### Configuration for DirectAdmin Apache (AlmaLinux/CentOS)

#### Option A: Use httpd-includes.conf (Recommended)

Edit `/etc/httpd/conf/extra/httpd-includes.conf`:

```apache
# Briven Proxy Configuration
# Instance: briven-instance
# Domain: briven.example.com
# Note: Use specific IP, not wildcards, for DirectAdmin compatibility

<VirtualHost YOUR_SERVER_IP:80>
    ServerName briven.example.com
    ServerAlias www.briven.example.com

    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</VirtualHost>

<VirtualHost YOUR_SERVER_IP:443>
    ServerName briven.example.com
    ServerAlias www.briven.example.com
    ServerAdmin webmaster@example.com

    SSLEngine on
    # DirectAdmin SSL cert paths (adjust user and domain)
    SSLCertificateFile /usr/local/directadmin/data/users/USERNAME/domains/example.com.cert.combined
    SSLCertificateKeyFile /usr/local/directadmin/data/users/USERNAME/domains/example.com.key

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:50080/
    ProxyPassReverse / http://127.0.0.1:50080/

    # WebSocket Support
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/?(.*) ws://127.0.0.1:50080/$1 [P,L]

    ErrorLog /var/log/httpd/domains/briven.example.com.error.log
    CustomLog /var/log/httpd/domains/briven.example.com.access.log combined
</VirtualHost>
```

> ⚠️ **Important for DirectAdmin:**
> - Use **specific IP address** (e.g., `192.168.1.100:443`), not `*:443`
> - IP-bound vhosts take precedence over DirectAdmin's vhosts
> - SSL certs are in `/usr/local/directadmin/data/users/USERNAME/domains/`

#### Option B: Standalone conf.d file

If `/etc/httpd/conf.d/` is included in your Apache config:

```bash
# Check if conf.d is included
grep 'conf.d' /etc/httpd/conf/httpd.conf

# If not, add before directadmin-vhosts.conf include:
sed -i '/Include conf\/extra\/directadmin-vhosts.conf/i Include conf.d/*.conf' /etc/httpd/conf/httpd.conf

# Create config
mkdir -p /etc/httpd/conf.d
cat > /etc/httpd/conf.d/httpd-vhosts-briven.conf << 'EOF'
# Your vhost config here (same as Option A)
EOF
```

### Verify and Restart Apache

```bash
# Test configuration
httpd -t          # AlmaLinux/CentOS
apachectl -t      # Alternative
apache2ctl -t     # Debian/Ubuntu

# Restart
systemctl restart httpd   # AlmaLinux/CentOS
systemctl restart apache2 # Debian/Ubuntu
```

---

## SSL/TLS Configuration

### Option A: Let's Encrypt with Certbot

```bash
# Install Certbot
# Debian/Ubuntu:
apt-get install certbot python3-certbot-apache

# AlmaLinux/CentOS:
dnf install certbot python3-certbot-apache

# Obtain certificate
certbot --apache -d briven.example.com -d www.briven.example.com

# Auto-renewal (usually automatic, but verify)
certbot renew --dry-run
```

### Option B: DirectAdmin Auto-SSL

If using DirectAdmin, SSL is typically managed automatically:

1. Create domain/subdomain in DirectAdmin
2. Enable "SSL" for the domain
3. DirectAdmin will obtain Let's Encrypt certificate
4. Certs stored in `/usr/local/directadmin/data/users/USERNAME/domains/`

### Option C: Manual/Commercial Certificates

Place certificates in secure location:

```bash
mkdir -p /etc/ssl/briven
chmod 700 /etc/ssl/briven

# Copy your certificates
cp certificate.crt /etc/ssl/briven/
cp private.key /etc/ssl/briven/
cp chain.crt /etc/ssl/briven/  # if applicable

chmod 600 /etc/ssl/briven/*
```

---

## Authentication Setup

### Understanding Briven Authentication Variables

| Variable | Purpose | Example |
|----------|---------|--------|
| `AUTH_LOGIN` | The **username** for login | `AUTH_LOGIN=admin` |
| `AUTH_PASSWORD` | The **password** for login | `AUTH_PASSWORD=SecurePass123!` |

> ⚠️ **Common Mistake:** `AUTH_LOGIN` is the username, **not** a boolean to enable auth!

### Setting Up Authentication

```bash
# Edit .env file
vi /opt/briven-instance/.env

# Add/update these lines:
AUTH_LOGIN=your_username
AUTH_PASSWORD=your_secure_password

# Restart container to apply
docker restart briven-instance
```

### Password Requirements

- Minimum 8 characters recommended
- Special characters are supported (properly escaped)
- Avoid these characters in passwords: `' " \` $ \` (or escape carefully)

### Disabling Authentication (Not Recommended)

To disable authentication (local/dev use only):

```bash
# Remove or comment out both lines in .env:
# AUTH_LOGIN=
# AUTH_PASSWORD=

docker restart briven-instance
```

---

## Domain & DNS Setup

### DNS Configuration

Create an A record pointing to your server:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | briven | YOUR_SERVER_IP | 300 |
| A | www.briven | YOUR_SERVER_IP | 300 |

### DirectAdmin Subdomain Setup

1. Log into DirectAdmin
2. Navigate to: **Domain Setup** → Select domain → **Subdomain Management**
3. Create subdomain (e.g., `briven`)
4. Note: You'll override the DocumentRoot with Apache proxy config

### Verify DNS Propagation

```bash
# Check DNS resolution
dig briven.example.com +short
nslookup briven.example.com

# Should return your server IP
```

---

## Verification & Testing

### Step-by-Step Verification Checklist

```bash
# 1. Verify Docker container is running
docker ps | grep briven-instance

# 2. Check container logs for errors
docker logs briven-instance --tail 50

# 3. Test local container access
curl -I http://127.0.0.1:50080/
# Expected: HTTP/1.1 302 FOUND, Location: /login

# 4. Test Apache config
httpd -t   # or apache2ctl -t

# 5. Check Apache is proxying correctly
curl -I http://127.0.0.1:80 -H "Host: briven.example.com"
curl -Ik https://127.0.0.1:443 -H "Host: briven.example.com"

# 6. Test external HTTPS access
curl -I https://briven.example.com/
# Expected: HTTP/2 302 with Location: /login

# 7. Test login page loads
curl -s https://briven.example.com/login | grep -i "<title>"
# Expected: <title>Login - Briven</title>
```

### WebSocket Verification

```bash
# Install wscat if needed
npm install -g wscat

# Test WebSocket connection
wscat -c wss://briven.example.com/ws
```

---

## Troubleshooting

### Issue: "Invalid Credentials" on Login

**Cause:** Incorrect `.env` configuration

**Fix:**
```bash
# Verify .env inside container
docker exec briven-instance cat /briven/.env

# Ensure format is:
# AUTH_LOGIN=username  (NOT AUTH_LOGIN=true)
# AUTH_PASSWORD=password

# Restart after fixing
docker restart briven-instance
```

### Issue: 403 Forbidden

**Cause:** DirectAdmin vhost overriding custom proxy config

**Fix:**
```bash
# Check vhost order
httpd -S 2>&1 | grep your-domain

# Ensure custom config loads BEFORE directadmin-vhosts.conf
# Use specific IP binding (e.g., 192.168.1.1:443) not wildcards (*:443)

# Restart Apache
systemctl restart httpd
```

### Issue: 502 Bad Gateway

**Cause:** Container not running or wrong port

**Fix:**
```bash
# Check container status
docker ps -a | grep briven-instance

# If stopped, check logs
docker logs briven-instance

# Restart container
docker start briven-instance

# Verify port binding
netstat -tlnp | grep 50080
```

### Issue: 504 Gateway Timeout

**Cause:** Container overloaded or unresponsive

**Fix:**
```bash
# Check container resource usage
docker stats briven-instance --no-stream

# Restart container
docker restart briven-instance

# Check for memory issues
free -h
```

### Issue: WebSocket Connection Failed

**Cause:** Missing WebSocket proxy rules

**Fix:**
Ensure these lines are in your vhost config:

```apache
RewriteEngine On
RewriteCond %{HTTP:Upgrade} websocket [NC]
RewriteCond %{HTTP:Connection} upgrade [NC]
RewriteRule ^/?(.*) ws://127.0.0.1:50080/$1 [P,L]
```

### Issue: Container Won't Start

**Cause:** Port conflict or Docker issue

**Fix:**
```bash
# Check what's using the port
netstat -tlnp | grep 50080

# Remove conflicting container
docker rm -f conflicting-container

# Check Docker daemon
systemctl status docker
journalctl -u docker --since "1 hour ago"
```

### Issue: Changes to .env Not Taking Effect

**Cause:** Container needs restart to reload env

**Fix:**
```bash
docker restart briven-instance

# Verify env is loaded
docker exec briven-instance cat /briven/.env
```

---

## Maintenance & Updates

### Updating Briven

```bash
# Pull latest image
docker pull briven/briven:latest

# Stop and remove old container (data persists in volumes)
docker stop briven-instance
docker rm briven-instance

# Recreate with same settings
docker run -d   --name briven-instance   --restart unless-stopped   -p 50080:80   -v /opt/briven-instance/.env:/briven/.env   -v /opt/briven-instance/usr:/briven/usr   -v /opt/briven:latest
```

### Backup Strategy

```bash
# Backup all instance data
tar -czvf briven-backup-$(date +%Y%m%d).tar.gz /opt/briven-instance/

# Key items to backup:
# - /opt/briven-instance/.env (configuration)
# - /opt/briven-instance/memory/ (agent memories)
# - /opt/briven-instance/work_dir/ (working files)
```

### Monitoring

```bash
# Check container health
docker ps --format "table {{.Names}}	{{.Status}}	{{.Ports}}"

# View recent logs
docker logs --tail 100 -f briven-instance

# Resource usage
docker stats briven-instance
```

### Docker Cleanup

```bash
# Remove unused images
docker image prune -f

# Remove all unused Docker resources
docker system prune -f
```

---

## Quick Reference

### Essential Commands

```bash
# Container Management
docker start briven-instance
docker stop briven-instance
docker restart briven-instance
docker logs briven-instance
docker exec -it briven-instance bash

# Apache Management  
systemctl restart httpd    # RHEL/AlmaLinux
systemctl restart apache2  # Debian/Ubuntu
httpd -t                   # Test config

# Quick Diagnostics
docker ps | grep briven
curl -I https://your-domain.com/login
```

### Standard Paths

| Component | Path |
|-----------|----- |
| Instance Data | `/opt/briven-instance/` |
| Environment File | `/opt/briven-instance/.env` |
| Memory Storage | `/opt/briven-instance/memory/` |
| Work Directory | `/opt/briven-instance/work_dir/` |
| Logs | `/opt/briven-instance/logs/` |
| Apache Config (Standard) | `/etc/apache2/sites-available/` |
| Apache Config (DirectAdmin) | `/etc/httpd/conf/extra/httpd-includes.conf` |
| DirectAdmin SSL Certs | `/usr/local/directadmin/data/users/USER/domains/` |

### Standard Ports

| Port | Purpose |
|------|---------|
| 50080 | First Briven instance |
| 50081 | Second Briven instance |
| 50082 | Third Briven instance |
| 80 | HTTP (redirect to HTTPS) |
| 443 | HTTPS (main access) |

### .env Template

```bash
# Briven Configuration Template
# Copy and customize for each instance

# Authentication (REQUIRED for production)
AUTH_LOGIN=your_username
AUTH_PASSWORD=your_secure_password

# Optional: Additional settings
# Refer to Briven documentation for all options
```

---

## Appendix: Multi-Instance Setup

For running multiple Briven instances on the same server:

```bash
# Instance 1: briven-primary on port 50080
mkdir -p /opt/briven-primary
# ... create .env, run container on port 50080

# Instance 2: briven-dev on port 50081  
mkdir -p /opt/briven-dev
# ... create .env, run container on port 50081

# Instance 3: briven-backup on port 50082
mkdir -p /opt/briven-backup
# ... create .env, run container on port 50082
```

Each instance needs:
- Unique container name
- Unique host port
- Separate data directory
- Separate domain/subdomain
- Separate Apache vhost config

---

*This guide comes from successful Briven deployments across DirectAdmin and standard Linux environments.*

Contributed by @hurtdidit in the Briven Community.
