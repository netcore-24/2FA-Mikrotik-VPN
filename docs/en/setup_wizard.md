# Setup Wizard

Documentation for the system setup wizard.

## Overview

The setup wizard is an interactive tool that helps an administrator configure the system after the initial deployment. It provides step-by-step guidance with tips and instructions at each stage.

## Modes

### Automatic start
- The wizard starts automatically on the first login if setup is not completed
- This is determined by whether an admin user exists and core settings are configured

### Manual start
- The wizard can be started at any time from Settings → Setup Wizard
- Useful for reconfiguring the system or adding new settings later

### Restart
- You can restart setup from any step
- Allows changing previously configured parameters

## Wizard steps

### Step 1: Welcome
A welcome message describing the setup process.

### Step 2: Basic information
- System name
- UI language
- Time zone
- Admin email

### Step 3: Security
- Secret key generation
- JWT token configuration
- Create the first administrator

### Step 4: Telegram Bot
- Bot creation instructions
- Configure Telegram Bot Token
- Connection test

### Step 5: MikroTik Router
- Router connection settings
- Access setup instructions
- Connection test
- User Manager and Firewall configuration

### Step 6: Notifications
- Admin notifications configuration
- Telegram ID and email
- Notification types

### Step 7: Additional settings (optional)
- Web UI configuration
- Logging configuration
- Backup configuration

### Step 8: Review and finish
- Summary of all settings
- Readiness checks
- Finish setup

## Features

- **Progress tracking**: current step indicator (X of Y)
- **Navigation**: Back / Next / Skip buttons
- **Validation**: input validation on each step
- **Hints**: help and instructions per step
- **Progress persistence**: automatic save between steps

## Completion criteria

Setup is considered complete when:
- At least one administrator is created
- Telegram Bot Token is configured
- MikroTik connection is configured
- Core security settings are saved

After completion, the wizard will no longer auto-start on login.

More details are described below in this document.

