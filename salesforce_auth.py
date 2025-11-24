# salesforce_auth.py
# Universal Salesforce authentication using SOAP login
# NO CONNECTED APP REQUIRED - Works on any Salesforce org!

import requests
import re
from typing import Optional
from xml.etree import ElementTree as ET


class SalesforceAuthError(Exception):
    """Custom exception for Salesforce authentication errors"""
    pass


class SalesforceAuth:
    """
    Authenticate to Salesforce using SOAP login.
    
    This method works on ANY Salesforce org without requiring:
    - Connected App configuration
    - Consumer Key / Secret
    - OAuth configuration
    
    Only requires:
    - Username
    - Password
    - Security Token (unless IP is whitelisted)
    """
    
    def __init__(self):
        self.api_version = None  # Will be set dynamically
    
    def get_latest_api_version(self, instance_url: str) -> str:
        """
        Fetch the latest API version supported by the Salesforce org.
        
        Args:
            instance_url: The Salesforce instance URL
            
        Returns:
            Latest API version string (e.g., "61.0")
        """
        try:
            # This endpoint doesn't require authentication
            url = f"{instance_url}/services/data/"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                versions = response.json()
                if versions and len(versions) > 0:
                    # Get the latest (last) version
                    latest = versions[-1]
                    version = latest.get("version", "61.0")
                    return version
        except Exception:
            pass
        
        # Fallback to a safe default
        return "58.0"
    
    def login(
        self,
        username: str,
        password: str,
        security_token: str = "",
        domain: str = "login"
    ) -> dict:
        """
        Authenticate to Salesforce using SOAP login.
        
        Args:
            username: Salesforce username (email)
            password: Salesforce password
            security_token: Security token (append to password). 
                          Leave empty if your IP is whitelisted.
            domain: Login domain - 'login' for production, 'test' for sandbox,
                   or full custom domain like 'mycompany.my.salesforce.com'
        
        Returns:
            dict with session_id, instance_url, user_id, org_id, api_version
        
        Raises:
            SalesforceAuthError: If authentication fails
        """
        # Build the login URL - use a base version for SOAP login
        # (SOAP login works with older versions too)
        if domain in ('login', 'test'):
            base_url = f"https://{domain}.salesforce.com"
        elif domain.endswith('.salesforce.com'):
            base_url = f"https://{domain}"
        else:
            base_url = f"https://{domain}.salesforce.com"
        
        # Use a stable SOAP version for login (this always works)
        login_url = f"{base_url}/services/Soap/u/58.0"
        
        # Combine password and security token
        full_password = password + security_token
        
        # Build SOAP request
        soap_body = self._build_login_soap(username, full_password)
        
        headers = {
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPAction": "login"
        }
        
        try:
            response = requests.post(
                login_url,
                data=soap_body,
                headers=headers,
                timeout=30
            )
        except requests.RequestException as e:
            raise SalesforceAuthError(f"Network error during login: {str(e)}")
        
        # Parse response
        result = self._parse_login_response(response)
        
        # Now get the actual API version from the org
        instance_url = result.get("instance_url", "")
        if instance_url:
            api_version = self.get_latest_api_version(instance_url)
            result["api_version"] = api_version
            self.api_version = api_version
        else:
            result["api_version"] = "58.0"
            self.api_version = "58.0"
        
        return result
    
    def _build_login_soap(self, username: str, password: str) -> str:
        """Build the SOAP XML for login request"""
        username = self._xml_escape(username)
        password = self._xml_escape(password)
        
        return f"""<?xml version="1.0" encoding="utf-8" ?>
<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:partner.soap.sforce.com">
  <env:Header>
    <urn:CallOptions>
      <urn:client>SalesforceReportExporter</urn:client>
    </urn:CallOptions>
  </env:Header>
  <env:Body>
    <n1:login xmlns:n1="urn:partner.soap.sforce.com">
      <n1:username>{username}</n1:username>
      <n1:password>{password}</n1:password>
    </n1:login>
  </env:Body>
</env:Envelope>"""
    
    def _xml_escape(self, text: str) -> str:
        """Escape special XML characters"""
        replacements = [
            ("&", "&amp;"),
            ("<", "&lt;"),
            (">", "&gt;"),
            ("'", "&apos;"),
            ('"', "&quot;"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text
    
    def _parse_login_response(self, response: requests.Response) -> dict:
        """Parse the SOAP login response"""
        
        if response.status_code != 200:
            error_msg = self._extract_soap_fault(response.text)
            if error_msg:
                raise SalesforceAuthError(f"Login failed: {error_msg}")
            raise SalesforceAuthError(
                f"Login failed with HTTP {response.status_code}: {response.text[:500]}"
            )
        
        try:
            root = ET.fromstring(response.text)
            
            ns = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'sf': 'urn:partner.soap.sforce.com'
            }
            
            fault = root.find('.//soapenv:Fault', ns)
            if fault is not None:
                fault_string = fault.find('faultstring')
                msg = fault_string.text if fault_string is not None else "Unknown error"
                raise SalesforceAuthError(f"Login failed: {msg}")
            
            result = root.find('.//sf:result', ns)
            if result is None:
                result = self._find_element_by_local_name(root, 'result')
            
            if result is None:
                raise SalesforceAuthError("Could not parse login response - no result found")
            
            session_id = self._get_element_text(result, 'sessionId', ns)
            if not session_id:
                raise SalesforceAuthError("No session ID in response")
            
            server_url = self._get_element_text(result, 'serverUrl', ns)
            instance_url = self._extract_instance_url(server_url)
            
            user_info = result.find('.//sf:userInfo', ns)
            if user_info is None:
                user_info = self._find_element_by_local_name(result, 'userInfo')
            
            user_id = ""
            org_id = ""
            user_name = ""
            if user_info is not None:
                user_id = self._get_element_text(user_info, 'userId', ns)
                org_id = self._get_element_text(user_info, 'organizationId', ns)
                user_name = self._get_element_text(user_info, 'userFullName', ns)
            
            return {
                "session_id": session_id,
                "instance_url": instance_url,
                "server_url": server_url,
                "user_id": user_id,
                "org_id": org_id,
                "user_name": user_name
            }
            
        except ET.ParseError as e:
            raise SalesforceAuthError(f"Failed to parse login response: {str(e)}")
    
    def _get_element_text(self, parent, tag_name: str, ns: dict) -> str:
        """Get text from element by tag name"""
        elem = parent.find(f'.//sf:{tag_name}', ns)
        if elem is not None and elem.text:
            return elem.text
        
        elem = self._find_element_by_local_name(parent, tag_name)
        if elem is not None and elem.text:
            return elem.text
        
        return ""
    
    def _find_element_by_local_name(self, parent, local_name: str):
        """Find element by local name ignoring namespace"""
        for elem in parent.iter():
            tag = elem.tag
            if '}' in tag:
                tag = tag.split('}')[1]
            if tag == local_name:
                return elem
        return None
    
    def _extract_instance_url(self, server_url: str) -> str:
        """Extract instance URL from server URL"""
        if not server_url:
            return ""
        
        match = re.match(r'(https://[^/]+)', server_url)
        if match:
            return match.group(1)
        return server_url
    
    def _extract_soap_fault(self, xml_text: str) -> Optional[str]:
        """Try to extract SOAP fault message from response"""
        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                if 'faultstring' in elem.tag.lower() or elem.tag.endswith('faultstring'):
                    return elem.text
            
            for elem in root.iter():
                tag = elem.tag.lower()
                if 'message' in tag or 'error' in tag:
                    if elem.text:
                        return elem.text
        except:
            pass
        return None


def salesforce_login(
    username: str,
    password: str,
    security_token: str = "",
    domain: str = "login"
) -> dict:
    """
    Quick login to Salesforce.
    
    Returns:
        dict with session_id, instance_url, user_id, org_id, api_version
    """
    auth = SalesforceAuth()
    return auth.login(username, password, security_token, domain)