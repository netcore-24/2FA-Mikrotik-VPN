# How the system works

This is a real-world working scenario — from preparing MikroTik to the user connecting and the system controlling the session.

## 1) Prepare MikroTik

1. The administrator **creates a VPN user on MikroTik** (User Manager or a PPP secret — depends on router configuration).
2. If needed, the administrator creates/configures a **firewall rule** with a comment containing `2FA` (if “extra protection” is planned).  
   **Important:** firewall rule discovery relies on `comment` containing `2FA` — rules without `2FA` will not be found.

Important: the system does **not have to** create users on MikroTik (it can manage existing ones). In the current project configuration, management and synchronization are supported, but the baseline logic always relies on accounts on the router.

## 2) User registration

1. The user interacts with the **Telegram bot** and submits a registration request.
2. The administrator opens the web UI → **Users** and **approves** the request.

## 3) Linking MikroTik accounts

1. The administrator opens the user → **Edit**.
2. Specifies up to **two** MikroTik usernames (e.g. `vpn_user_ivan`).
3. Saves changes.

## 4) Access request and VPN connection

1. The user requests access via the Telegram bot (command/button “get VPN”).
2. The system creates/updates a VPN session record and **allows connection** (MikroTik activation depends on the chosen flow).
3. The user connects with a standard VPN client (Windows/macOS/Linux/Android/iOS) using the MikroTik account username/password.

## 5) Active session control and “extra protection”

1. The system periodically checks active connections on MikroTik (User Manager sessions / PPP active).
2. If **extra protection** is enabled, the user receives a Telegram confirmation prompt (“Was this you?”).
3. After confirmation, the system may **enable the firewall rule** (if linked) and mark the session as active.

## 6) End and extend

1. The session has a time limit (configured in the UI).
2. Before expiration, the system sends an extension reminder.
3. If the user doesn’t extend, the session ends and access may be revoked (depending on policy).

