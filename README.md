# Salesforce Report Exporter (Universal)

A portable, cross-platform desktop application to bulk-export all Salesforce reports into a single ZIP file.

**🎯 Works on ANY Salesforce org - No Connected App required!**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Why This Tool?

Traditional Salesforce API tools require setting up a Connected App with OAuth configuration - this can be time-consuming and may not be possible if you're a consultant working on a client's org with limited admin access.

**This tool uses SOAP login** which only requires:
- ✅ Username
- ✅ Password  
- ✅ Security Token (optional if IP whitelisted)

No Connected App setup needed!

## Features

- **Universal Compatibility** - Works on any Salesforce org
- **No Connected App Required** - Uses SOAP authentication
- **Production & Sandbox Support** - Easy environment switching
- **Custom Domain Support** - Works with MyDomain configurations
- **Bulk Export** - Exports all accessible reports automatically
- **Progress Tracking** - Real-time progress and logging
- **Error Handling** - Graceful handling of failures
- **Cross-Platform** - Windows, macOS, and Linux

## Quick Start

```bash
# 1. Clone or download the project
git clone <repository-url>
cd salesforce-report-exporter

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py
```

## Requirements

- Python 3.10 or higher
- Salesforce account with API access
- Security Token (unless your IP is whitelisted)

## Project Structure

```
salesforce-report-exporter/
├── main.py              # Application entry point & UI
├── salesforce_auth.py   # SOAP authentication (no Connected App!)
├── exporter.py          # Report export logic
├── requirements.txt     # Python dependencies
├── README.md            # This file
└── docs/
    ├── SETUP_GUIDE.md   # Installation instructions
    ├── USER_GUIDE.md    # How to use
    └── FEATURES.md      # Feature documentation
```

## How It Works

1. **SOAP Login**: Authenticates using Salesforce's SOAP Partner API
2. **Session ID**: Receives a session ID (works like OAuth access token)
3. **REST API**: Uses the session ID to call REST Analytics API
4. **Export**: Downloads each report as CSV and packages into ZIP

The session ID from SOAP login is interchangeable with OAuth access tokens for REST API calls - this is the key that makes this tool work without a Connected App!

## Security Notes

- Credentials are never stored - entered fresh each session
- Session ID kept in memory only
- All Salesforce communication over HTTPS
- Security token adds extra protection

## Getting Your Security Token

1. Log in to Salesforce
2. Click your profile icon → **Settings**
3. Search for "Reset Security Token"
4. Click **Reset Security Token**
5. Check your email for the new token

## Documentation

- [Setup Guide](docs/SETUP_GUIDE.md) - Detailed installation
- [User Guide](docs/USER_GUIDE.md) - How to use the application
- [Features](docs/FEATURES.md) - Complete feature list

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Invalid username/password" | Check credentials and security token |
| "API not enabled" | Contact admin to enable API access |
| "IP not whitelisted" | Add security token to password OR whitelist IP |
| "Session expired" | Re-login and try again |

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.