# DNS Records — All Entries to Add in Ionos

**Date:** 2026-05-27
**VPS IP:** 82.165.32.162

Add all of these in Ionos DNS. After adding, wait 15–60 minutes for propagation then message me and I'll finish the server config.

---

## A Records (subdomains pointing to VPS)

Add these for both domains:

| Type | Host | Value         |
| ---- | ---- | ------------- |
| A    | mail | 82.165.32.162 |
| A    | crm  | 82.165.32.162 |

Do this for **christopherrehm.de** and also add the `mail` A record for **tandkcybernetics.net**.

---

## christopherrehm.de — 5 records

### MX (receiving email)

```
Type:     MX
Host:     @
Value:    mail.christopherrehm.de
Priority: 10
TTL:      3600
```

### SPF (authorised senders)

```
Type:  TXT
Host:  @
Value: v=spf1 ip4:82.165.32.162 -all
TTL:   3600
```

### DKIM (signature verification)

```
Type:  TXT
Host:  mail._domainkey
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAra2GKNDNoJJcMhYHvl7ZbOQeSnkcZSq9OOjURfBs2yJIP2I2RZyoXTUDMFkW+fyimXEqzuGaBE53tvo5lVNOOc0GZZkM5UnAxrFFuvB1gqP8PWx/x4T9VrFO3V/6YvsOO1AYqGrwzkOwW5VH6b4P5EaYiuaog6htodJ5VD1YRGjJOHpMimB2Si3cs+WjdxFqRCEhx2sM7RynIKvNHEyBKN5ZLcVEqn/RvlEK9JGhZZLgzoIfQDfWm8rg6dLE8miW8fejgILz9QTSmt0hbtONxaa0VdIDJ9gPE4V3nTtP0ghLXkY7Uxh6JdVz02NqV64E0BvQ0RDkP2GzYZv+rK2bIwIDAQAB
TTL:   3600
```

### DMARC (policy for failed checks)

```
Type:  TXT
Host:  _dmarc
Value: v=DMARC1; p=reject; rua=mailto:contact@christopherrehm.de
TTL:   3600
```

### DKIM for crm subdomain (outbound only)

```
Type:  TXT
Host:  mail._domainkey.crm
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn+1iCrNU0kd6tGQpnlwXp5nfXbYmc13D4AoGzsPxWdB8xxZUb4PAwKLolhP43mxbf33WN3bjBIcBIgpcNxF6WPQKvwMGy/zypfSkyV96Y4byKf/JcfNd8xWjSaBnE6o+OKvcnAxHVM8CkQdXbSWSX5ok6fPKj4ewOAvYlfSJvoXhLBr8/d2Zw8APC4+LxrYQ4PRfET44Gwvt/0OXk1nhierS9dYFNEoFLE4iL3/JfiS+50T9L8nXQCQsT7uhcqD+m5Nb6dTNmqdOAG/9fcaAXxezhslZGYgNcnV4iDyPQj4FwgWYTM2BGNwFNsglpKG/WhXO4eW/41zmogTnm0P4gQIDAQAB
TTL:   3600
```

### DKIM for notes-world subdomain (outbound only)

```
Type:  TXT
Host:  mail._domainkey.notes-world
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0tq7mBukVeZLRsrDJLCOBJtIuVjreY7LWZB8usorAFkaQHfIl8F7Vz6ZqZyS6N4MKsw/zW5sDHSGg+46dHr7sMMDbh3FuM5tp9t6GIo74EPW69ciicFwxMxXa/6nO4U6yuNMGR6vXq9YQxIpuEeucv0efIxkWZoSAMneyWR1DxG7zRZo0BF8x9H5K7qK1PlnboGREeNz7NWJaNjEDgQo1z7tQULkmVxG0KCwe6BBFHNYp3n/9RHIWSnSHLxNUXbZvC0sCns2vu489TpzYrHex29LLLG0pWxsS4NmcRSzt0KP4DSHlzkc6eWA2R+p1SmlN1Njf6Ci9Fy4bf+62pHV/QIDAQAB
TTL:   3600
```

### DKIM for euroart subdomain (outbound only)

```
Type:  TXT
Host:  mail._domainkey.euroart
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3Ulca5BBQJP2wgMTcsrRsDgb4j5qWCYZbViYr+Do9Y1ULvCtWgCevvrAP8a0NDuLsZ8IQJi3REgU57cPT0RPAqJQ8NGeM7RD8qOs6ZXCJvOi4F7Ns0pNrOKd1UE5jS0qNxJX61/71GrE4Yi2B+F8VLl8zEY3G35Vgi8QGsjN7WVx3bNQjoPkbTbCjmjNp/Djc+x+TaDL8sBQ4VcfsnazCiymyqHLZFQqoNPK7H077QFCDXFNlUOOmehorfibhzCKK7m6JlGvErsyMQbANXcbUeg6SDHz7fI9h5noclTgsiCbXrrokoulornt4C6u95NAsqCYzRImwKX9S4BFeDwcSQIDAQAB
TTL:   3600
```

---

## tandkcybernetics.net — 4 records

### MX (receiving email)

```
Type:     MX
Host:     @
Value:    mail.tandkcybernetics.net
Priority: 10
TTL:      3600
```

### SPF

```
Type:  TXT
Host:  @
Value: v=spf1 ip4:82.165.32.162 -all
TTL:   3600
```

### DKIM

```
Type:  TXT
Host:  mail._domainkey
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn4HxdXUZOLles5iRk1OnVbitsR5HdhXlfUWD9nHCxyhzaoW1+VWCtxSxpNHiB2GiB7nFXtNFKWKu2wa85Q8poy+yHoXhSDgfF19wxKsOqLu16lC1XoAN5HmpLlHhyZFYTqj4rQKS8g5qo9hxk0zzKA+/Mqi3c74CbdhurTgoP0NrMDbuGOd3gWaT8BYvE7gDArUWMLiWpydJVxM++sppNqdnJaiSEF6z7bZg8AAU7rOz4djdRwDO5fvv67EBSrn92Kfqzi233JAb2TVP6ZL67VwsG6bM5d7TmwODmScWg7tTOQKNDTeQbiv84swzSrKrwmM2rpnqd1l/4cfNUSw+vQIDAQAB
TTL:   3600
```

### DMARC

```
Type:  TXT
Host:  _dmarc
Value: v=DMARC1; p=reject; rua=mailto:contact@tandkcybernetics.net
TTL:   3600
```

---

## Summary Count

| Domain               | Records to add                                                   |
| -------------------- | ---------------------------------------------------------------- |
| christopherrehm.de   | 2 A + 1 MX + 1 SPF + 1 DKIM + 1 DMARC + 3 subdomain DKIM = **9** |
| tandkcybernetics.net | 1 A + 1 MX + 1 SPF + 1 DKIM + 1 DMARC = **5**                    |
| **Total**            | **14 records**                                                   |

---

## After Adding

Message me and I'll:

1. Run certbot for mail.christopherrehm.de (Snappymail SSL)
2. Run certbot for crm.christopherrehm.de (ArtCRM SSL)
3. Finish Postfix + Dovecot config
4. Create mailboxes (contact@christopherrehm.de, contact@tandkcybernetics.net)
5. Deploy ArtCRM from the repo
