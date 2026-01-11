# System workflow (how it works)

This document is the English counterpart of the main Russian workflow description.

Because the original workflow file (`docs/ru/SYSTEM_WORKFLOW.md`) is extensive and includes many UI strings, examples, and router commands, this English version focuses on the practical, end-to-end flow and key rules.

## Core idea

The system implements **2FA for VPN sessions on MikroTik** by controlling existing router accounts (enable/disable) and optionally enabling/disabling firewall rules, while confirming sessions via Telegram.

## Key constraints

- The system works with **existing MikroTik accounts** (User Manager users or PPP secrets).  
  It **does not** create MikroTik users by itself in the intended setup.
- **VPN user passwords are not stored** in the system. The admin distributes them via a secure channel.
- Each system user can have **up to 2 linked MikroTik accounts**.

## End-to-end flow

1. **Admin prepares MikroTik**
   - Creates VPN accounts in User Manager (or PPP secrets, depending on router setup).
   - (Optional) Creates firewall rules for users (disabled by default), so the system can enable them after confirmation.

2. **User registers via Telegram**
   - The user uses the Telegram bot to register.
   - The admin approves the request in the web admin UI.

3. **Admin links MikroTik username(s)**
   - The admin links 1–2 existing MikroTik usernames to the approved user.

4. **User requests VPN access**
   - The user requests VPN via the bot.
   - The system enables the linked MikroTik account (and records a VPN session in the database).

5. **User connects using a standard VPN client**
   - The user connects with the router-issued username/password.

6. **Connection detection + confirmation**
   - The system periodically checks active sessions on MikroTik.
   - If “extra protection” (confirmation) is enabled, the user gets a Telegram prompt: “Was this you?”
   - On confirmation, the system marks the session active and can enable the firewall rule (if configured).
   - On rejection/timeout, the system disconnects/denies access (by disabling the MikroTik account and/or firewall rule depending on settings).

7. **Reminders / extension**
   - Sessions have a time limit.
   - The system sends reminders before expiration so the user can extend or end the session.

## Related documents

- Telegram message flow: `telegram_messages_flow.md`
- System flow diagram: `system_flow_diagram.md`
- Install: `../en/INSTALL.md`

## Full Russian workflow (source of truth)

If you need the complete step-by-step workflow, file references, and detailed examples, see:

- `../ru/SYSTEM_WORKFLOW.md`

