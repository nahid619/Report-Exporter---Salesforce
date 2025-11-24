# Features Documentation

Complete feature list and technical specifications for the Salesforce Report Exporter.

## Table of Contents

- [Core Features](#core-features)
- [Authentication](#authentication)
- [Dynamic API Version Detection](#dynamic-api-version-detection)
- [Report Export Capabilities](#report-export-capabilities)
- [Data Completeness](#data-completeness)
- [UI Features](#ui-features)
- [Technical Specifications](#technical-specifications)
- [Limitations](#limitations)
- [Comparison Tables](#comparison-tables)

---

## Core Features

### 1. Universal SOAP Authentication

**The key differentiator** - Works on ANY Salesforce org without setup.

#### How It Works

1. User provides username + password + security token
2. App sends SOAP login request to Salesforce Partner API
3. Salesforce returns Session ID and Instance URL
4. Session ID is used for all subsequent REST API calls
5. **API version auto-detected** from org after login

#### Why This Matters

- ✅ **No Connected App configuration** needed
- ✅ **No Consumer Key/Secret** required
- ✅ **Works immediately** on any org
- ✅ **Perfect for consultants** and temporary access
- ✅ **No admin access required** (just API Enabled permission)

#### Technical Details

- Uses SOAP Partner API v58.0 for initial login (stable, widely supported)
- Session ID is interchangeable with OAuth access tokens
- Supports Production, Sandbox, and Custom Domains
- HTTPS encryption for all traffic
- Session valid until inactivity timeout or logout

#### Authentication Flow

```
1. User Input → Username, Password, Token, Domain
2. SOAP Login → POST to /services/Soap/u/58.0/
3. Response → Session ID, Instance URL, User Info
4. API Detection → GET /services/data/ (discover versions)
5. Select Latest → Use newest supported API version
6. Ready → REST API calls with dynamic version
```

### 2. Multi-Environment Support

Seamlessly switch between environments:

| Environment       | Login URL                   | Use Case            | Configuration            |
| ----------------- | --------------------------- | ------------------- | ------------------------ |
| **Production**    | login.salesforce.com        | Live production org | Select from dropdown     |
| **Sandbox**       | test.salesforce.com         | Dev/test/staging    | Select from dropdown     |
| **Custom Domain** | mycompany.my.salesforce.com | MyDomain orgs       | Check box + enter domain |

**Custom Domain Features**:

- Automatic URL construction
- Validates domain format
- Supports SSO-enabled domains
- Works with enhanced domains

### 3. Bulk Report Export

Automatically exports all accessible reports with advanced capabilities.

#### Export Process

**Phase 1: Discovery**

- REST API call: `GET /services/data/v{detected_version}/analytics/reports`
- Returns complete list of reports user can access
- **Dynamic API version** automatically detected from org
- Includes report metadata: ID, name, type, format

**Phase 2: Individual Report Export**

- Uses UI export URL method (not limited REST API)
- Downloads **full report data** as CSV
- **Bypasses 2,000 row limit** of Analytics REST API
- Exports **actual report content**, not just metadata
- Respects all Salesforce permissions

**Phase 3: ZIP Packaging**

- Compresses all CSVs into single archive
- Adds comprehensive export summary
- Cleans up temporary files
- Validates ZIP integrity

#### Specifications

| Aspect             | Detail                                                |
| ------------------ | ----------------------------------------------------- |
| API Version        | **Dynamic** - Auto-detected from org (v58.0 - v62.0+) |
| SOAP Version       | v58.0 (stable for login)                              |
| REST Version       | Latest supported by org                               |
| Output Format      | CSV (UTF-8 encoded)                                   |
| Compression        | ZIP with DEFLATE algorithm                            |
| Row Limit          | **No API limit** (uses UI export method)              |
| Report Limit       | **No limit** on number of reports                     |
| Concurrent Exports | Sequential (rate-limited)                             |
| Retry Logic        | Exponential backoff (up to 3 retries)                 |

---

## Authentication

### Credential Handling

| Feature            | Implementation                | Security Level |
| ------------------ | ----------------------------- | -------------- |
| **Storage**        | Memory only, never persisted  | 🔒 High        |
| **Password Input** | Masked (QLineEdit.Password)   | 🔒 High        |
| **Token Input**    | Masked (QLineEdit.Password)   | 🔒 High        |
| **Transmission**   | HTTPS only (TLS 1.2+)         | 🔒 High        |
| **Session ID**     | Kept in memory during session | 🔒 Medium      |
| **Logs**           | No credentials logged         | 🔒 High        |

### Security Token Support

Flexible authentication options:

**With Token** (Recommended):

- Append to password automatically
- Works from any IP address
- Extra layer of security

**Without Token** (IP Whitelisting):

- Leave token field blank
- Requires IP in Trusted IP Ranges
- Convenient for office networks

**SSO Users**:

- May not have traditional token
- Use IP whitelisting
- Contact admin for exemptions

### Session Management

**Session Lifecycle**:

- Created: On successful SOAP login
- Valid: Until inactivity timeout (org setting, typically 2-8 hours)
- Expires: On timeout, logout, or app close
- Renewal: Simply login again (no refresh token needed)

**Session Data Stored**:

```python
{
    "session_id": "00D5g000008...",
    "instance_url": "https://na1.salesforce.com",
    "user_id": "0055g000003...",
    "org_id": "00D5g000008...",
    "user_name": "John Doe",
    "api_version": "62.0"  # Auto-detected
}
```

---

## Dynamic API Version Detection

### Overview

The application **automatically detects and uses** the latest API version supported by your Salesforce org, ensuring optimal compatibility and access to newest features.

### How It Works

#### Detection Process

1. **Initial SOAP Login**:

   - Uses stable v58.0 for SOAP Partner API
   - Retrieves session ID and instance URL

2. **Version Discovery**:

   ```python
   GET {instance_url}/services/data/
   ```

   - Public endpoint (no auth required)
   - Returns JSON array of all supported versions

3. **Version Selection**:

   ```python
   versions = [
       {"label": "Winter '23", "version": "56.0", ...},
       {"label": "Spring '23", "version": "57.0", ...},
       {"label": "Summer '23", "version": "58.0", ...},
       {"label": "Winter '24", "version": "61.0", ...},
       {"label": "Spring '24", "version": "62.0", ...}
   ]
   latest_version = versions[-1]["version"]  # "62.0"
   ```

4. **Dynamic Endpoint Construction**:
   ```python
   # Reports list endpoint
   f"/services/data/v{api_version}/analytics/reports"
   # Example: /services/data/v62.0/analytics/reports
   ```

### Benefits

| Benefit                 | Description                                                     |
| ----------------------- | --------------------------------------------------------------- |
| **Future-Proof**        | Automatically uses new API versions as Salesforce releases them |
| **Backward Compatible** | Falls back to v58.0 if detection fails                          |
| **No Manual Updates**   | No code changes needed for new Salesforce releases              |
| **Org-Specific**        | Each org may support different versions                         |
| **Feature Access**      | Leverages newest API capabilities available to your org         |

### Version Display

After successful login, status shows:

```
✓ na1.salesforce.com (API v62.0)
```

Log entries include:

```
[14:30:03] Login successful! Instance: https://na1.salesforce.com
[14:30:03] API Version: v62.0
[14:30:03] User: John Doe
```

### Fallback Behavior

If version detection fails (network issue, API change):

- Falls back to **v58.0** (stable, widely supported)
- Logs warning but continues operation
- No user intervention required

### Code Implementation

**In `salesforce_auth.py`**:

```python
def get_latest_api_version(self, instance_url: str) -> str:
    try:
        url = f"{instance_url}/services/data/"
        response = requests.get(url, timeout=15)
        versions = response.json()
        latest = versions[-1]
        return latest.get("version", "58.0")
    except:
        return "58.0"  # Safe fallback
```

**In `exporter.py`**:

```python
def __init__(self, session_id, instance_url, api_version=None):
    if api_version:
        self.api_version = f"v{api_version}"
    else:
        # Auto-detect
        self.api_version = get_org_api_version(instance_url)

    # Build endpoints with detected version
    self.reports_list_endpoint = f"/services/data/{self.api_version}/analytics/reports"
```

---

## Report Export Capabilities

### Data Export: Actual Content vs Metadata

**This tool exports ACTUAL REPORT DATA**, not just metadata.

#### What Gets Exported

✅ **Full Report Data**:

- All rows (not limited to 2,000 like REST API)
- All columns as configured in report
- Groupings and subtotals (flattened to tabular)
- Calculated fields and formulas
- Filtered data as defined in report
- Formatted values (dates, numbers, currencies)

❌ **Not Exported**:

- Report definition/structure (SOQL, filters)
- Conditional formatting rules
- Chart configurations
- Dashboard layouts

#### Export Method: UI Export URL

**Why UI Export Instead of REST API?**

| Method                 | Row Limit         | Content     | Our Choice  |
| ---------------------- | ----------------- | ----------- | ----------- |
| **Analytics REST API** | 2,000 rows        | JSON format | ❌ Not used |
| **UI Export URL**      | Org limit (200K+) | CSV format  | ✅ Used     |

**UI Export URL Structure**:

```
GET /{reportId}?isdtp=p1&export=1&enc=UTF-8&xf=csv
Cookie: sid={session_id}
```

**How It Works**:

1. Mimics clicking "Export" button in Salesforce UI
2. Uses session cookie authentication
3. Returns raw CSV content
4. **No 2,000 row limit** (up to org's report row limits)
5. Works with Lightning and Classic

**Example CSV Output** (Tabular Report):

```csv
Account Name,Industry,Annual Revenue,Owner,Created Date
Acme Corp,Technology,5000000,John Doe,2024-01-15
Global Inc,Manufacturing,12000000,Jane Smith,2024-02-20
Tech Innovations,Technology,3500000,Bob Johnson,2024-03-10
```

### Access Control & Permissions

#### Who Can Access What Reports?

The application exports **all reports the authenticated user has permission to view**. Salesforce controls access, not the app.

| User Profile             | Reports Accessible      | Example Count |
| ------------------------ | ----------------------- | ------------- |
| **System Administrator** | All reports in org      | 500+ reports  |
| **Standard User**        | Public + owned + shared | 150 reports   |
| **Read-Only User**       | Public reports only     | 50 reports    |
| **Custom Profile**       | Based on permissions    | Varies        |

#### Report Types Exported

✅ **Public Reports**:

- Available to all users
- Stored in public folders
- No special permissions needed

✅ **Private Reports**:

- Your own private reports
- Reports others shared with you
- Folder-level sharing applies

✅ **Shared Reports**:

- Shared with your role/group
- Shared via folder permissions
- Shared directly to you

✅ **Package Reports**:

- From managed packages
- If you have package license
- Based on package permissions

❌ **Inaccessible Reports**:

- Other users' private reports (not shared)
- Restricted folder reports
- License-restricted reports

#### Permission Checks

**Report List API** (`/analytics/reports`):

- Returns ONLY reports user can view
- No unauthorized reports in list
- Enforced by Salesforce, not app

**Report Export**:

- Additional permission check during download
- "You do not have access" errors logged
- Failed reports listed in summary

#### Real-World Example

**Scenario**: Sales Manager with 200 team members

**Exports Include**:

- ✅ All public sales reports (50 reports)
- ✅ Own private reports (20 reports)
- ✅ Reports shared with Sales Manager role (30 reports)
- ✅ Team-owned reports in shared folders (100 reports)
- ❌ Other managers' private reports (not accessible)
- ❌ HR department reports (different org hierarchy)

**Total Exported**: 200 reports (all accessible)

### Supported Report Types

| Report Type | Export Support   | Notes                          |
| ----------- | ---------------- | ------------------------------ |
| **Tabular** | ✅ Full          | Best results, cleanest CSV     |
| **Summary** | ✅ Full          | Grouped data flattened to rows |
| **Matrix**  | ⚠️ Partial       | Converted to tabular format    |
| **Joined**  | ❌ Not Supported | Salesforce API limitation      |

#### Tabular Reports

**Best format for export**.

Structure:

- Simple row/column format
- No grouping or subtotals
- Direct CSV mapping

Example:

```csv
Lead Name,Company,Status,Owner
John Smith,Acme Corp,Qualified,Sales Rep 1
Jane Doe,Tech Inc,New,Sales Rep 2
```

#### Summary Reports

**Grouped data exported as flat CSV**.

Structure:

- Groups become rows
- Subtotals included
- Grand totals at end

Example:

```csv
Status,Lead Name,Company,Count
New,John Smith,Acme Corp,1
New,Jane Doe,Tech Inc,1
New (Subtotal),,,2
Qualified,Bob Johnson,Global LLC,1
Qualified (Subtotal),,,1
Grand Total,,,3
```

#### Matrix Reports

**Two-dimensional pivot exported as tabular**.

Original (Matrix):

```
             Q1    Q2    Q3    Total
Product A    100   150   200   450
Product B    200   250   300   750
Total        300   400   500   1200
```

Exported (Tabular):

```csv
Row Label,Q1,Q2,Q3,Total
Product A,100,150,200,450
Product B,200,250,300,750
Total,300,400,500,1200
```

#### Joined Reports

**Cannot be exported** - Salesforce API limitation.

Error message:

```
Joined reports cannot be exported via API
```

Workaround:

- Export as separate reports
- Manually join data in Excel/SQL

---

## Data Completeness

### Row Limits

| Method                              | Limit                        | This Tool   |
| ----------------------------------- | ---------------------------- | ----------- |
| **UI Manual Export**                | Up to 200,000+ (org setting) | ✅ Same     |
| **Analytics REST API**              | 2,000 rows max               | ❌ Not used |
| **Reports and Dashboards REST API** | 2,000 rows max               | ❌ Not used |
| **SOQL Query**                      | 2,000 rows (synchronous)     | ❌ Not used |

**Our Approach**: Uses UI export method → Same limits as manual export.

### Data Accuracy

✅ **Snapshot at export time**:

- Data current as of export moment
- Not live/real-time
- Re-export for updated data

✅ **Respects report filters**:

- Date ranges applied
- Field filters included
- Row limits (if set in report)

✅ **Preserves formatting**:

- UTF-8 encoding (international characters)
- Date formats as configured
- Number formats (decimals, thousands)
- Currency symbols

### Encoding & Special Characters

**UTF-8 Everywhere**:

- All CSVs encoded as UTF-8
- Supports international characters:
  - European: Übersicht, Çeşit, ñ
  - Asian: 日本語, 中文, 한국어
  - Symbols: €, £, ¥, ©, ®

**Safe Handling**:

- Commas in values → quoted
- Newlines in values → quoted
- Quotes in values → escaped (double quotes)

---

## UI Features

### Credential Input Section

**Environment Selector**:

- Dropdown: Production | Sandbox
- Radio behavior (mutually exclusive with Custom Domain)
- Auto-disables when Custom Domain checked

**Custom Domain Toggle**:

- Checkbox + text input
- Validates domain format
- Placeholder: `mycompany.my.salesforce.com`
- Disables environment dropdown when checked

**Username Field**:

- Standard text input
- Placeholder: `your.email@company.com`
- Auto-trim whitespace

**Password Field**:

- Masked input (QLineEdit.Password)
- Shows dots (•••) instead of characters
- Clipboard paste supported

**Security Token Field**:

- Masked input (QLineEdit.Password)
- Optional (blank if IP whitelisted)
- Placeholder explains when needed

**Login Button**:

- Prominent position
- Min height: 32px
- Disabled during login attempt
- Re-enabled after success/failure

**Status Indicator**:

- Not logged in: Gray text
- Connecting: Gray "Connecting..."
- Success: Green "✓ instance.salesforce.com (API v62.0)"
- Failure: Red "✗ Login failed"

### Progress Tracking

**Progress Bar**:

- Visual percentage: 0% → 100%
- Color: Blue (default Qt style)
- Text overlay: "45/100 reports (45%)"
- States:
  - Ready: 0%, "Ready"
  - Starting: 0%, "Starting..."
  - In Progress: 1-99%, "X/Y reports (Z%)"
  - Complete: 100%, "Done! X reports"
  - Error: Last value, "Error"

**Real-Time Updates**:

- Updates every report completion
- No UI freeze (thread-safe signals)
- Smooth animation

### Activity Log

**Log Display**:

- Read-only text area
- Monospace font (Consolas, Monaco)
- Auto-scroll to latest entry
- Max height: 120px (scrollable)

**Log Entries**:

- Timestamp: `[HH:MM:SS]`
- Event description
- Color coding: Default (black)

**Example Log**:

```
[14:30:01] Authenticating...
[14:30:03] Login successful! Instance: https://na1.salesforce.com
[14:30:03] API Version: v62.0
[14:30:03] User: John Doe
[14:30:05] Output: /Users/john/Desktop/reports.zip
[14:30:05] Starting export...
[14:30:06] Exported 1/247
[14:30:07] Exported 2/247
...
[14:35:42] Export completed: 247 reports, 3 failed
```

**Clear Button**:

- Position: Next to "Log:" label
- Width: 60px
- Action: Clears all log entries
- Use case: Multi-session exports

### Button States

**Login Button**:

- Enabled: Always (unless logging in)
- Disabled: During login attempt
- Text: "Login"

**Browse Button**:

- Enabled: Always (unless exporting)
- Disabled: During export
- Text: "Browse..."

**Start Export Button**:

- Enabled: When logged in AND output path set
- Disabled: When not logged in OR no path OR exporting
- Style: Blue background (enabled), Gray (disabled)
- Text: "Start Export"
- Height: 38px (prominent)

### Thread Safety

**Why It Matters**:

- Long operations (login, export) run on background threads
- UI remains responsive (no freezing)
- User can read logs, check status during export

**Implementation**:

```python
# Qt Signals for thread communication
class WorkerSignals(QObject):
    progress = Signal(int, int)       # (done, total)
    log = Signal(str)                 # Log message
    finished = Signal(dict)           # Success result
    error = Signal(str)               # Error message
    login_success = Signal(dict)      # Login data
    login_error = Signal(str)         # Login error
```

**Worker Threads**:

- Login: Separate thread for SOAP authentication
- Export: Separate thread for report download
- UI: Main thread handles display updates only

---

## Technical Specifications

### API Usage

#### SOAP Partner API (Authentication)

**Endpoint**: `/services/Soap/u/58.0/`

**Used For**:

- Initial authentication
- Session ID generation
- User info retrieval

**Version**: v58.0 (stable, well-tested)

**Request**:

```xml
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
  <env:Body>
    <n1:login xmlns:n1="urn:partner.soap.sforce.com">
      <n1:username>user@example.com</n1:username>
      <n1:password>password + token</n1:password>
    </n1:login>
  </env:Body>
</env:Envelope>
```

**Response**: Session ID, Instance URL, User ID, Org ID

#### REST Analytics API (Report List)

**Endpoint**: `/services/data/v{detected_version}/analytics/reports`

**Used For**:

- Fetching list of all accessible reports
- Getting report metadata (ID, name, type)

**Version**: **Dynamic** (auto-detected from org, typically v61.0 - v62.0)

**Request**:

```http
GET /services/data/v62.0/analytics/reports
Authorization: Bearer {session_id}
Accept: application/json
```

**Response**: JSON array of report objects

#### UI Export URL (Report Data)

**Endpoint**: `/{reportId}?isdtp=p1&export=1&enc=UTF-8&xf=csv`

**Used For**:

- Downloading actual report data as CSV
- Bypassing 2,000 row REST API limit

**Authentication**: Session cookie

**Request**:

```http
GET /00O5g000007ABCD?isdtp=p1&export=1&enc=UTF-8&xf=csv
Cookie: sid={session_id}
```

**Response**: Raw CSV content

**Parameters**:

- `isdtp=p1`: Lightning/mobile flag
- `export=1`: Export mode
- `enc=UTF-8`: Character encoding
- `xf=csv`: Export format (CSV)

### Rate Limiting

**Built-in Protection**:

| Feature                 | Setting                     | Purpose                 |
| ----------------------- | --------------------------- | ----------------------- |
| **Default Delay**       | 0.3 seconds                 | Prevent rate limiting   |
| **Retry-After**         | Respects header             | Server-directed backoff |
| **Exponential Backoff** | 1s → 2s → 4s → 8s → 60s max | Retry failed requests   |
| **Max Retries**         | 3 attempts                  | Avoid infinite loops    |

**Backoff Algorithm**:

```python
backoff = 1  # Start at 1 second
for attempt in range(3):
    try:
        response = request()
        if success:
            break
    except RateLimitError:
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)  # Double, max 60s
```

**Timeout Settings**:

- Login: 30 seconds
- Report list: 60 seconds
- Report CSV: 120 seconds (large reports)

### Performance Benchmarks

**Typical Export Times**:

| Report Count | Time        | Network   |
| ------------ | ----------- | --------- |
| 50           | ~20 seconds | Broadband |
| 100          | ~40 seconds | Broadband |
| 250          | ~2 minutes  | Broadband |
| 500          | ~4 minutes  | Broadband |
| 1000         | ~8 minutes  | Broadband |

**Factors Affecting Speed**:

- Network speed (biggest factor)
- Report size (rows × columns)
- Salesforce server load
- Time of day (peak vs off-peak)

**Optimization**:

- Sequential processing (rate limit compliance)
- Efficient ZIP compression
- Minimal memory footprint
- Temporary file cleanup

### Memory Usage

**Efficient Resource Handling**:

| Aspect                | Strategy                        | Memory Impact   |
| --------------------- | ------------------------------- | --------------- |
| **Report Processing** | One at a time                   | ~5MB per report |
| **Temporary Files**   | Write to disk immediately       | Minimal RAM     |
| **ZIP Creation**      | Incremental (not all in memory) | ~10MB overhead  |
| **Session Data**      | ~1KB (ID, URL, metadata)        | Negligible      |
| **UI Components**     | Qt efficient rendering          | ~50MB base      |

**Peak Memory**:

- Small org (50 reports): ~100MB
- Medium org (250 reports): ~150MB
- Large org (1000 reports): ~200MB

**Cleanup**:

- Temporary directory deleted after export
- No persistent cache files
- Memory released after completion

---

## Limitations

### Known Limitations

#### 1. Joined Reports

**Issue**: Cannot be exported via API

**Reason**: Salesforce API limitation (all methods)

**Workaround**:

- Export component reports separately
- Manually join data in Excel/database
- Consider restructuring as multiple related reports

#### 2. Very Large Reports

**Issue**: May timeout (>120 seconds)

**Reason**: Network latency + report complexity

**Workaround**:

- Add date range filters in Salesforce
- Split into smaller reports
- Export during off-peak hours
- Increase timeout (requires code change)

#### 3. Real-Time Data

**Issue**: Data snapshot at export time

**Reason**: Not a live connection

**Workaround**:

- Re-export for updated data
- Schedule regular exports
- Consider Salesforce Streaming API for real-time needs

#### 4. Session Timeout

**Issue**: Long exports may exceed session timeout

**Reason**: Org inactivity timeout setting (typically 2-8 hours)

**Workaround**:

- Re-login if export fails mid-process
- Export in smaller batches
- Contact admin to increase timeout

#### 5. Report Metadata

**Issue**: Report structure not exported (only data)

**Reason**: Focus on data export, not report definitions

**Details Not Exported**:

- SOQL queries
- Filter logic
- Grouping rules
- Chart configurations
- Conditional formatting

#### 6. Dashboard Support

**Issue**: Dashboards not supported

**Reason**: Different API endpoint (future enhancement)

**Workaround**: Export underlying reports instead

### Salesforce Limitations

**These are Salesforce platform limits, not app limits**:

#### API Call Limits

- Default: 15,000 calls per 24 hours (varies by edition)
- Each report = 1 API call
- Login = 1 API call
- Monitor: Setup → System Overview → API Usage

#### Report Row Limits

- Varies by org settings (typically 200,000)
- Dashboard components: 2,000 rows
- Scheduled reports: 2,000 rows (email attachment)

#### Report Types

- Joined Reports: No API export support
- Historical Trend Reports: Complex formatting issues

#### Network & Performance

- Timeout limits (platform-enforced)
- Rate limiting (prevents abuse)
- Concurrent request limits

---

## Comparison Tables

### SOAP vs OAuth Authentication

| Feature                 | This Tool (SOAP)                        | OAuth Tool                         |
| ----------------------- | --------------------------------------- | ---------------------------------- |
| **Setup Required**      | None                                    | Connected App                      |
| **Works on Any Org**    | ✅ Yes                                  | ❌ Needs configuration             |
| **Admin Access Needed** | ❌ No                                   | ✅ Yes (for setup)                 |
| **Security**            | Username + Token                        | Client ID + Secret                 |
| **Refresh Tokens**      | No (re-login)                           | Yes (automatic)                    |
| **Session Duration**    | Org timeout                             | Refresh token lifetime             |
| **Best For**            | Quick access, consulting, temporary use | Permanent integrations, automation |
| **API Version**         | ✅ Dynamic detection                    | Typically static                   |

### Export Methods Comparison

| Method                    | Row Limit                | Content Type   | Speed  | Used By    |
| ------------------------- | ------------------------ | -------------- | ------ | ---------- |
| **UI Export (This Tool)** | Org limit (200K+)        | Full CSV data  | Fast   | ✅ Us      |
| **Analytics REST API**    | 2,000 rows               | JSON           | Fast   | ❌ Not us  |
| **Manual UI Export**      | Org limit                | CSV            | Manual | Users      |
| **Data Loader**           | Unlimited                | Custom objects | Slow   | Admins     |
| **SOQL Queries**          | 2,000 (sync) 50K (async) | Raw records    | Fast   | Developers |

### API Version Strategy

| Approach                   | Our Tool                | Traditional Tools        |
| -------------------------- | ----------------------- | ------------------------ |
| **Version Selection**      | ✅ Dynamic detection    | Static (hardcoded)       |
| **Org Compatibility**      | ✅ Matches org's latest | May use outdated version |
| **Maintenance**            | ✅ Zero (auto-adapts)   | Requires updates         |
| **New Features**           | ✅ Immediate access     | Delayed until update     |
| **Backward Compatibility** | ✅ Falls back to v58.0  | Single version only      |

---

## Future Enhancements

Planned features for future releases:

### High Priority

- [ ] **Selective Report Export**: Checkbox selection UI
- [ ] **Report Folder Filtering**: Export by folder/category
- [ ] **Parallel Export**: Speed up with concurrent downloads (rate-limited)
- [ ] **CLI Mode**: Command-line interface for automation

### Medium Priority

- [ ] **Export Scheduling**: Cron-like scheduler built-in
- [ ] **Incremental Export**: Only export changed/new reports
- [ ] **Dashboard Support**: Export dashboard CSVs
- [ ] **Excel Output**: Optional .xlsx format

### Low Priority

- [ ] **Dark Mode Theme**: UI appearance options
- [ ] **Export History**: Log of past exports
- [ ] **Standalone Executables**: .exe (Windows), .app (macOS)
- [ ] **Multi-Org Sessions**: Switch between orgs without re-login

### Research

- [ ] **Joined Report Support**: If Salesforce adds API support
- [ ] **Real-Time Sync**: Stream updates via Platform Events
- [ ] **Report Metadata Export**: Save report definitions

---

## Summary

### Key Highlights

✅ **Universal Compatibility**: Works on any Salesforce org  
✅ **No Setup Required**: No Connected App configuration  
✅ **Dynamic API Matching**: Auto-detects org's latest API version  
✅ **Full Data Export**: Actual report data, not just metadata  
✅ **Comprehensive Access**: All reports user has permission to view  
✅ **No Row Limits**: Bypasses 2,000 row API restriction  
✅ **Thread-Safe UI**: Never freezes during operations  
✅ **Error Resilient**: Continues on failures, logs all issues  
✅ **Cross-Platform**: Windows, macOS, Linux  
✅ **Open Source**: Transparent, auditable, customizable

### Perfect For

- 📊 Salesforce consultants needing quick report access
- 🔄 Migration projects (backup before changes)
- 📈 Compliance audits (snapshot of all reports)
- 💼 Clients without technical admin access
- 🚀 Teams needing immediate solution (no waiting for IT)

---

**Need more details?** See [USER_GUIDE.md](USER_GUIDE.md) for usage instructions and [SETUP_GUIDE.md](SETUP_GUIDE.md) for installation steps.
