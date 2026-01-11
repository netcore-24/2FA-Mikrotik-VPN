# System Algorithm

Detailed description of the two-factor authentication workflow.

## Main stages

### 1. User registration
The user registers via the Telegram bot, the administrator reviews and approves the registration.

### 2. VPN access request
The user requests access via the bot, the system enables the user in MikroTik User Manager.

### 3. Connect and confirm
The user connects to VPN, the system detects the connection and requests confirmation in Telegram.

### 4. Firewall rule activation
After confirmation, the firewall rule for the user is enabled and the reminder timer is started.

### 5. Work continuation reminder
After a configured period, the system sends a reminder; the user can extend or end the session.

More details for each stage are described below in this document.

