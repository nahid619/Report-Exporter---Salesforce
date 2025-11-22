# Features Documentation

Complete feature list and technical specifications.

## Core Features

### Universal SOAP Authentication

**The key differentiator** - Works on ANY Salesforce org without setup.

**How it works:**
1. User provides username + password + security token
2. App sends SOAP login request to Salesforce Partner API
3. Salesforce returns Session ID and Instance URL
4. Session ID is used for all subsequent REST API calls

**Why this matters:**
- No Connected App configuration needed
- No Consumer Key/Secret required
- Works immediately on any org
- Perfect for consultants and temporary access

**Technical details:**
- Uses SOAP Partner API v61.0
- Session ID is interchangeable with OAuth access tokens
- Supports Production, Sandbox, and Custom Domains

### Multi-Environment Support

Seamlessly switch between environments:

| Environment | Login URL | Use Case |
|-------------|-----------|----------|
| Production | login.salesforce.com | Live org |
| Sandbox | test.salesforce.com | Dev/Test |
| Custom Domain | mycompany.my.salesforce.com | MyDomain orgs |

### Bulk Report Export

Automatically exports all accessible reports:

1. Fetches complete report list via REST Analytics API
2. Exports each report as UTF-8 CSV
3. Handles errors gracefully (continues on failure)
4. Creates single ZIP with all reports

**Specifications:**
- REST API Version: v61.0
- Output Format: CSV (UTF-8)
- Compression: ZIP with DEFLATE
- Encoding: UTF-8 for international characters

### Thread-Safe UI

Responsive interface during long operations:

- All network operations run in background threads
- Qt Signals communicate between threads safely
- UI never freezes during login or export
- Real-time progress updates

## Authentication Features

### Credential Handling

| Feature | Implementation |
|---------|----------------|
| Storage | Memory only, never persisted |
| Password | Masked input field |
| Token | Masked input field |
| Transmission | HTTPS only |

### Security Token Support

Handles Salesforce's security token requirement:

- **With Token**: Append to password automatically
- **Without Token**: Works if IP is whitelisted
- **SSO Users**: May not have token (use IP whitelisting)

### Session Management

- Session ID valid until:
  - Inactivity timeout (org setting)
  - User logs out
  - Application closes
- Re-authentication: Simply login again
- No refresh tokens needed

## Export Features

### Report Discovery

Automatically finds all reports:

```
GET /services/data/v61.0/analytics/reports
```

Returns all reports the user has access to view.

### CSV Export

Uses the UI export URL method (not the limited Analytics API):

```
GET /{reportId}?isdtp=p1&export=1&enc=UTF-8&xf=csv
Cookie: sid={session_id}
```

**Why this method?**
- Analytics REST API is limited to 2,000 rows
- UI export method has no row limit (up to org limits)
- Returns proper CSV, not JSON that needs conversion
- Works with both Lightning and Classic

### Supported Report Types

| Type | Export Support | Notes |
|------|----------------|-------|
| Tabular | ✅ Full | Best results |
| Summary | ✅ Full | Grouped data flattened |
| Matrix | ⚠️ Limited | Converted to tabular |
| Joined | ❌ No | API limitation |

### Error Handling

Comprehensive error recovery:

| Error | Response |
|-------|----------|
| 429 Rate Limited | Exponential backoff, retry |
| 5xx Server Error | Retry up to 3 times |
| 4xx Client Error | Log error, continue |
| Network Timeout | Retry with longer timeout |
| Parse Error | Log error, continue |

### Filename Handling

Safe filenames for all platforms:

- Invalid characters → underscore
- Multiple underscores → single
- Max length: 120 characters
- Duplicates: append counter (Report_2.csv)

## UI Features

### Credential Input

- Username field with placeholder
- Password field with masking
- Security token field with masking
- Environment dropdown
- Custom domain checkbox + input

### Progress Tracking

Real-time feedback:

```
Progress bar: [████████░░░░░░░░] 45%
Label: 45/100 reports (45%)
```

### Activity Log

Timestamped, scrollable log:

```
[14:30:01] Authenticating with Salesforce...
[14:30:03] Login successful! Instance: https://na1.salesforce.com
[14:30:05] Starting export...
[14:30:06] Exported 1/100
```

Features:
- Auto-scroll to latest
- Clear button
- Monospace font
- Timestamps

### Status Indicators

Visual feedback:
- 🔴 Not logged in
- 🟢 Logged in successfully
- 🔴 Login failed

## Technical Specifications

### API Versions

| API | Version |
|-----|---------|
| SOAP Partner | 61.0 |
| REST Analytics | v61.0 |

### Rate Limiting

Built-in protection:

- Default delay: 0.3s between reports
- Respects Retry-After headers
- Exponential backoff: 1s → 2s → 4s → ... → 60s max

### Performance Benchmarks

Typical export speeds (varies by network):

| Reports | Time |
|---------|------|
| 50 | ~20 seconds |
| 100 | ~40 seconds |
| 250 | ~2 minutes |
| 500 | ~4 minutes |
| 1000 | ~8 minutes |

### Memory Usage

Efficient resource handling:

- Reports processed one at a time
- Temporary files cleaned up automatically
- ZIP created incrementally
- Session data minimal (~1KB)

## Security Features

### No Persistent Storage

Nothing saved to disk:
- No credentials file
- No token cache
- No session persistence
- Clean slate each run

### Secure Transmission

All traffic encrypted:
- HTTPS for all API calls
- TLS 1.2+ required
- Certificate validation enabled

### Minimal Permissions

Only requires:
- API Enabled permission
- Read access to reports
- No admin access needed

## Comparison: SOAP vs OAuth

| Feature | This Tool (SOAP) | OAuth Tool |
|---------|------------------|------------|
| Setup required | None | Connected App |
| Works on any org | ✅ Yes | ❌ Needs config |
| Admin access needed | No | Yes (for setup) |
| Security | Username + Token | Client ID + Secret |
| Refresh tokens | No | Yes |
| Best for | Quick access, consulting | Permanent integrations |

## Limitations

### Known Limitations

1. **Joined Reports**: Cannot be exported via API
2. **Very Large Reports**: May timeout (try smaller date ranges)
3. **Real-time Data**: Snapshot at time of export
4. **Session Timeout**: Re-login required after inactivity

### Salesforce Limitations

- API call limits apply (check your org's limits)
- Report row limits apply
- Some report types not exportable

## Future Enhancements

Planned features:

- [ ] Selective report export (checkbox selection)
- [ ] Report folder filtering
- [ ] Parallel export with rate limiting
- [ ] Export scheduling
- [ ] Dark mode theme
- [ ] Standalone executables (.exe/.app)
- [ ] Command-line interface
- [ ] Export history logging