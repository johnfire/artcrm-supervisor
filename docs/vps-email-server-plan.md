# VPS Email Server Plan

**Date:** 2026-05-27
**Status:** draft — not yet implemented

---

## Overview

One Postfix + Dovecot installation on 82.165.32.162 handles all email for all domains and apps.

**Postfix** — sends and receives email (SMTP)
**Dovecot** — gives IMAP access to personal mailboxes so you can read mail in any email client

---

## Mailboxes (personal, send + receive)

| Address                      | Domain               |
| ---------------------------- | -------------------- |
| contact@christopherrehm.de   | christopherrehm.de   |
| contact@tandkcybernetics.net | tandkcybernetics.net |

You'll be able to add these to any IMAP client (Thunderbird, mobile mail app, etc.) and send/receive normally.

---

## App Sending Addresses (outbound only, no mailbox)

| Address                                 | Used by           |
| --------------------------------------- | ----------------- |
| outreach@crm.christopherrehm.de         | ArtCRM Supervisor |
| no-reply@notes-world.christopherrehm.de | Notes World       |
| no-reply@euroart.christopherrehm.de     | EuroArt           |

These are configured as virtual aliases — Postfix accepts them and can send from them, but there's no mailbox to log into. When these subdomains eventually become standalone domains, the config just moves.

---

## DNS Records Required

### christopherrehm.de

```
# Receiving email
MX    christopherrehm.de    →    mail.christopherrehm.de    priority 10

# Mail server A record
A     mail.christopherrehm.de    →    82.165.32.162

# SPF — only our VPS is allowed to send
TXT   christopherrehm.de    →    "v=spf1 ip4:82.165.32.162 -all"

# DKIM — public key (generated during install)
TXT   mail._domainkey.christopherrehm.de    →    "v=DKIM1; k=rsa; p=<public key>"

# DMARC — reject anything that fails SPF or DKIM
TXT   _dmarc.christopherrehm.de    →    "v=DMARC1; p=reject; rua=mailto:contact@christopherrehm.de"
```

### tandkcybernetics.net

Same set of records, pointing to 82.165.32.162.

```
MX    tandkcybernetics.net    →    mail.tandkcybernetics.net    priority 10
A     mail.tandkcybernetics.net    →    82.165.32.162
TXT   tandkcybernetics.net    →    "v=spf1 ip4:82.165.32.162 -all"
TXT   mail._domainkey.tandkcybernetics.net    →    "v=DKIM1; k=rsa; p=<public key>"
TXT   _dmarc.tandkcybernetics.net    →    "v=DMARC1; p=reject; rua=mailto:contact@tandkcybernetics.net"
```

### Sending subdomains (SPF + DKIM only, no MX needed)

```
# crm.christopherrehm.de
TXT   crm.christopherrehm.de    →    "v=spf1 ip4:82.165.32.162 -all"
TXT   mail._domainkey.crm.christopherrehm.de    →    "v=DKIM1; k=rsa; p=<public key>"

# notes-world.christopherrehm.de
TXT   notes-world.christopherrehm.de    →    "v=spf1 ip4:82.165.32.162 -all"
TXT   mail._domainkey.notes-world.christopherrehm.de    →    "v=DKIM1; k=rsa; p=<public key>"

# euroart.christopherrehm.de
TXT   euroart.christopherrehm.de    →    "v=spf1 ip4:82.165.32.162 -all"
TXT   mail._domainkey.euroart.christopherrehm.de    →    "v=DKIM1; k=rsa; p=<public key>"
```

---

## Server Installation Steps

### 1. Install packages

```bash
sudo apt update
sudo apt install postfix postfix-mysql dovecot-core dovecot-imapd opendkim opendkim-tools
```

During Postfix install: choose "Internet Site", enter `christopherrehm.de` as system mail name.

### 2. Generate DKIM keys (one per domain)

```bash
sudo mkdir -p /etc/opendkim/keys/christopherrehm.de
sudo opendkim-genkey -b 2048 -d christopherrehm.de -D /etc/opendkim/keys/christopherrehm.de -s mail -v
sudo chown -R opendkim:opendkim /etc/opendkim/keys

# Repeat for tandkcybernetics.net and each subdomain
```

The public key goes into DNS (the `p=` value in the DKIM TXT record).
The private key stays on the server and signs outgoing mail.

### 3. Configure Postfix

Key settings in `/etc/postfix/main.cf`:

```
myhostname = mail.christopherrehm.de
mydomain = christopherrehm.de
virtual_mailbox_domains = christopherrehm.de, tandkcybernetics.net
virtual_transport = dovecot
milter_default_action = accept
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
```

### 4. Configure Dovecot

Set mail storage location and enable IMAP. Users authenticate with system accounts or a virtual user table.

### 5. Create mailboxes

```bash
sudo useradd -m -s /sbin/nologin chris-christopherrehm
sudo useradd -m -s /sbin/nologin chris-tandkcybernetics
# Set passwords for IMAP login
sudo passwd chris-christopherrehm
```

### 6. Test

```bash
# Send a test email
echo "Test" | mail -s "Test" contact@christopherrehm.de

# Check mail logs
sudo tail -f /var/log/mail.log
```

---

## App Configuration

Once the server is running, update each app's `.env` on the VPS:

**ArtCRM Supervisor:**

```
SMTP_HOST=localhost
SMTP_PORT=587
SMTP_USER=outreach@crm.christopherrehm.de
SMTP_PASSWORD=<password>
IMAP_HOST=localhost
IMAP_PORT=993
IMAP_USER=outreach@crm.christopherrehm.de
IMAP_PASSWORD=<password>
```

**Notes World / EuroArt** (transactional only, SMTP send):

```
SMTP_HOST=localhost
SMTP_PORT=587
SMTP_FROM=no-reply@notes-world.christopherrehm.de
```

---

## Reading Your Mail

Add to any IMAP client (Thunderbird, iOS Mail, etc.):

```
IMAP server:  82.165.32.162
IMAP port:    993 (SSL)
SMTP server:  82.165.32.162
SMTP port:    587 (STARTTLS)
Username:     contact@christopherrehm.de
Password:     <set during setup>
```

---

## Implementation Order

1. Install Postfix + Dovecot + OpenDKIM on VPS
2. Generate DKIM keys for all domains
3. Add DNS records (you paste, I tell you exactly what)
4. Verify deliverability (mail-tester.com gives a score)
5. Configure personal mailboxes
6. Update app env vars to use new mail server
7. Test end-to-end (send outreach from artcrm, receive reply, followup agent reads it)
