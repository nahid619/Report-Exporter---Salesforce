# exporter.py
# Salesforce Report Exporter - Exports reports as CSV using the UI export method
# Uses DYNAMIC API version matching the org

import time
import tempfile
import zipfile
import shutil
from pathlib import Path
import requests
from typing import Callable, Optional, List, Dict, Any


def get_org_api_version(instance_url: str, session_id: str = None) -> str:
    """
    Fetch the latest API version supported by the Salesforce org.
    This endpoint doesn't require authentication.
    
    Args:
        instance_url: The Salesforce instance URL
        session_id: Optional session ID (not required for this call)
        
    Returns:
        Latest API version string (e.g., "v61.0")
    """
    try:
        url = f"{instance_url.rstrip('/')}/services/data/"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            versions = response.json()
            if versions and len(versions) > 0:
                # Get the latest (last) version
                latest = versions[-1]
                version = latest.get("version", "58.0")
                return f"v{version}"
    except Exception:
        pass
    
    # Fallback to a safe default
    return "v58.0"


def retry_request(
    url: str,
    headers: dict = None,
    cookies: dict = None,
    max_retries: int = 3,
    timeout: int = 60,
    allow_redirects: bool = True
) -> requests.Response:
    """Make HTTP GET request with exponential backoff retry logic."""
    backoff = 1
    last_error = None
    headers = headers or {}
    cookies = cookies or {}

    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=timeout,
                allow_redirects=allow_redirects
            )

            if response.status_code == 200:
                return response

            if response.status_code in (429, 500, 502, 503, 504):
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        backoff = int(retry_after)
                    except ValueError:
                        pass
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            response.raise_for_status()

        except requests.Timeout as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

    raise Exception(f"Request failed after {max_retries} retries: {last_error}")


def safe_filename(name: str, max_length: int = 100) -> str:
    """Sanitize filename by removing invalid characters."""
    if not name:
        return "unnamed_report"
    safe = "".join(c if c.isalnum() or c in " ._-" else "_" for c in name)
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip("_ ")
    return safe[:max_length] if safe else "unnamed_report"


class SalesforceReportExporter:
    """
    Export Salesforce reports to CSV files and package them into a ZIP.
    
    Uses TWO methods:
    1. REST API to get list of reports (with metadata)
    2. UI Export URL to download actual CSV (bypasses 2000 row limit)
    
    API version is detected dynamically from the org.
    """

    def __init__(
        self,
        session_id: str,
        instance_url: str,
        api_version: str = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        self.session_id = session_id
        self.instance_url = instance_url.rstrip('/')
        self.progress_callback = progress_callback
        
        # Get API version dynamically if not provided
        if api_version:
            self.api_version = api_version if api_version.startswith('v') else f"v{api_version}"
        else:
            self.api_version = get_org_api_version(self.instance_url)
        
        # Build endpoints with dynamic version
        self.reports_list_endpoint = f"/services/data/{self.api_version}/analytics/reports"
        
        # Headers for REST API calls (list reports)
        self.api_headers = {
            "Authorization": f"Bearer {self.session_id}",
            "Accept": "application/json"
        }
        
        # Cookies for UI export (CSV download)
        self.export_cookies = {
            "sid": self.session_id
        }

    def list_reports(self) -> List[Dict[str, Any]]:
        """
        Fetch list of all available reports using REST API.
        Returns list of report metadata (id, name, format, etc.)
        """
        url = f"{self.instance_url}{self.reports_list_endpoint}"
        response = retry_request(url, headers=self.api_headers, timeout=60)
        
        data = response.json()
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("reports", data.get("records", []))
        return []

    def export_report_csv(self, report_id: str, timeout: int = 120) -> str:
        """
        Export a single report as CSV using the UI export URL method.
        
        This is the "screen scraping" approach that:
        - Bypasses the 2000 row API limit
        - Returns actual CSV content
        - Works with Lightning and Classic
        """
        # Build the export URL - mimics clicking "Export" in the UI
        export_url = (
            f"{self.instance_url}/{report_id}"
            f"?isdtp=p1&export=1&enc=UTF-8&xf=csv"
        )
        
        # Make request with session ID as cookie
        response = retry_request(
            export_url,
            cookies=self.export_cookies,
            timeout=timeout,
            allow_redirects=True
        )
        
        content = response.text
        
        # Check if we got HTML instead of CSV
        if content.strip().startswith('<!DOCTYPE') or content.strip().startswith('<html'):
            if 'login.salesforce.com' in content or 'ec=302' in content:
                raise Exception("Session expired or invalid. Please re-login.")
            elif 'You do not have access' in content:
                raise Exception("Access denied to this report.")
            else:
                raise Exception("Received HTML instead of CSV. Report may not be exportable.")
        
        return content

    def export_all_reports_to_zip(
        self,
        output_zip_path: str,
        delay_between_reports: float = 0.5
    ) -> Dict[str, Any]:
        """
        Export all reports to a ZIP file.
        """
        tmp_dir = Path(tempfile.mkdtemp(prefix="sf_reports_"))

        try:
            # Step 1: Get list of all reports
            reports = self.list_reports()
            total = len(reports)
            completed = 0
            failed: List[Dict[str, Any]] = []
            successful: List[str] = []

            if total == 0:
                with zipfile.ZipFile(output_zip_path, "w") as zf:
                    zf.writestr("_README.txt", "No reports found in this Salesforce org.")
                return {
                    "zip": output_zip_path,
                    "total": 0,
                    "failed": [],
                    "successful": [],
                    "api_version": self.api_version
                }

            used_filenames: Dict[str, int] = {}

            # Step 2: Export each report
            for report in reports:
                report_id = report.get("id")
                report_name = report.get("name") or report_id
                report_type = report.get("reportFormat", "TABULAR")

                base_name = safe_filename(report_name)
                if base_name in used_filenames:
                    used_filenames[base_name] += 1
                    filename = f"{base_name}_{used_filenames[base_name]}.csv"
                else:
                    used_filenames[base_name] = 1
                    filename = f"{base_name}.csv"

                csv_path = tmp_dir / filename

                try:
                    csv_content = self.export_report_csv(report_id)
                    
                    if not csv_content or len(csv_content.strip()) == 0:
                        raise Exception("Empty response received")
                    
                    first_line = csv_content.split('\n')[0] if csv_content else ""
                    if 'Error' in first_line and len(csv_content) < 500:
                        raise Exception(f"Salesforce error: {first_line[:100]}")
                    
                    csv_path.write_text(csv_content, encoding="utf-8")
                    successful.append(report_name)

                except Exception as e:
                    error_msg = str(e)
                    failed.append({
                        "id": report_id,
                        "name": report_name,
                        "type": report_type,
                        "error": error_msg
                    })
                    error_content = (
                        f"# Failed to export report\n"
                        f"# Report Name: {report_name}\n"
                        f"# Report ID: {report_id}\n"
                        f"# Report Type: {report_type}\n"
                        f"# Error: {error_msg}\n"
                    )
                    csv_path.write_text(error_content, encoding="utf-8")

                completed += 1
                
                if self.progress_callback:
                    try:
                        self.progress_callback(completed, total)
                    except Exception:
                        pass

                if delay_between_reports > 0 and completed < total:
                    time.sleep(delay_between_reports)

            # Step 3: Create ZIP file
            with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(tmp_dir.iterdir()):
                    if file_path.is_file():
                        zf.write(file_path, arcname=file_path.name)
                
                summary = self._create_summary(total, successful, failed)
                zf.writestr("_EXPORT_SUMMARY.txt", summary)

            return {
                "zip": output_zip_path,
                "total": total,
                "failed": failed,
                "successful": successful,
                "api_version": self.api_version
            }

        finally:
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass

    def _create_summary(
        self,
        total: int,
        successful: List[str],
        failed: List[Dict[str, Any]]
    ) -> str:
        """Create a summary text file for the export."""
        lines = [
            "SALESFORCE REPORT EXPORT SUMMARY",
            "=" * 40,
            f"Export Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Instance: {self.instance_url}",
            f"API Version: {self.api_version}",
            "",
            f"Total Reports: {total}",
            f"Successful: {len(successful)}",
            f"Failed: {len(failed)}",
            "",
        ]
        
        if failed:
            lines.append("FAILED REPORTS:")
            lines.append("-" * 40)
            for f in failed:
                lines.append(f"• {f.get('name')} ({f.get('type')})")
                lines.append(f"  ID: {f.get('id')}")
                lines.append(f"  Error: {f.get('error')}")
                lines.append("")
        
        return "\n".join(lines)