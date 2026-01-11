# System Architecture

This document describes the architecture of the two-factor authentication system for MikroTik VPN.

## System components

### 1. Backend API (FastAPI)
- REST API for the web admin interface
- Business logic
- User and session management
- MikroTik integration
- Telegram integration

### 2. Telegram Bot
- Handles user commands
- Sends notifications
- Confirms connections
- Mini-App UI (optional)

### 3. Web Admin Interface
- User management
- Registration approvals
- System configuration
- Session monitoring
- Statistics

### 4. MikroTik Service
- SSH connection
- User Manager control
- Firewall rule control
- Connection monitoring

### 5. Database
- Stores users
- Stores sessions
- Stores settings
- Audit logs

## Component interaction

More details about component roles can be found in this document and in `system_flow_diagram.md`.

