# MTG Proxy Secret Generation Guide

An MTG proxy secret is a 32-character hexadecimal string that serves as the authentication key for your Telegram proxy server. This guide shows you multiple ways to generate a secure secret.

## Method 1: Using OpenSSL (Recommended)

### On Linux/macOS:
```bash
openssl rand -hex 16
```

### On Windows (with OpenSSL installed):
```cmd
openssl rand -hex 16
```

**Example output:**
```
a1b2c3d4e5f6789012345678901234ab
```

## Method 2: Using Python

### Python script:
```python
import secrets
print(secrets.token_hex(16))
```

### One-liner:
```bash
python3 -c "import secrets; print(secrets.token_hex(16))"
```

## Method 3: Using Node.js

### Node.js script:
```javascript
const crypto = require('crypto');
console.log(crypto.randomBytes(16).toString('hex'));
```

### One-liner:
```bash
node -e "console.log(require('crypto').randomBytes(16).toString('hex'))"
```

## Method 4: Online Generator (Less Secure)

If you don't have access to command line tools:

1. Visit: https://www.random.org/bytes/
2. Set format to "Hexadecimal"
3. Generate 16 bytes
4. Copy the result (remove spaces)

**⚠️ Note:** Online generators are less secure than local generation.

## Method 5: Manual Generation (Not Recommended)

For educational purposes only - create a 32-character string using:
- Numbers: 0-9
- Letters: a-f (lowercase)

**Example:** `dd1234567890abcdef1234567890abcd`

## Using Your Secret

Once you have your 32-character hex secret:

1. **Add to .env file:**
   ```
   MTG_SECRET=your_32_character_secret_here
   ```

2. **Docker Compose will use it automatically:**
   ```yaml
   command: run 0.0.0.0:3128 ${MTG_SECRET}
   ```

3. **Test your secret format:**
   ```bash
   echo "your_secret_here" | grep -E '^[a-f0-9]{32}$'
   ```
   Should return your secret if valid.

## Security Tips

- ✅ **Generate locally** when possible
- ✅ **Use cryptographically secure** random generators
- ✅ **Keep secret private** - never share publicly
- ✅ **Use different secrets** for different servers
- ❌ **Don't reuse** secrets across services
- ❌ **Don't use** predictable patterns

## Example Valid Secrets

```
dd1234567890abcdef1234567890abcd
0123456789abcdef0123456789abcdef
a1b2c3d4e5f6789012345678901234ab
```

## Troubleshooting

**Secret too short/long:**
- Must be exactly 32 characters
- Only use 0-9 and a-f

**Invalid characters:**
- No uppercase letters (A-F)
- No special characters
- No spaces

**Testing your secret:**
```bash
# Should output exactly 32
echo "your_secret" | wc -c
```

Remember: A strong secret is crucial for proxy security!