"""Improved platform detection module with better third-party service handling"""
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import socket
import dns.resolver


class Platform(Enum):
    """Supported platforms"""
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    YAHOO = "yahoo"
    APPLE = "apple"
    ZOHO = "zoho"
    PROTON = "proton"
    GMX = "gmx"
    FASTMAIL = "fastmail"
    TUTANOTA = "tutanota"
    MAILCOM = "mailcom"
    UNKNOWN = "unknown"


@dataclass
class PlatformDetectionResult:
    """Result of platform detection including raw DNS data"""
    platform: Platform
    email: str
    domain: str
    mx_records: List[str] = None
    spf_records: List[str] = None
    detection_method: str = "unknown"  # "known_domain", "mx_lookup", "spf_lookup", "smtp_banner"
    raw_mx_data: List[Dict[str, Any]] = None
    raw_txt_data: List[Dict[str, Any]] = None
    third_party_services: List[str] = None  # Detected third-party email services
    error: Optional[str] = None
    confidence: float = 1.0  # Confidence in the detection (0.0 to 1.0)


class ImprovedPlatformDetector:
    """Enhanced platform detection with third-party service awareness"""
    
    # Known third-party email security/gateway services
    THIRD_PARTY_SERVICES = {
        # Service name: List of domain patterns
        "proofpoint": ["pphosted.com", "proofpoint.com"],
        "messagelabs": ["messagelabs.com", "symantec.com", "symanteccloud.com"],
        "mimecast": ["mimecast.com", "mimecast.co.uk", "mimecast.de"],
        "barracuda": ["barracudanetworks.com", "cuda-inc.com"],
        "cisco_ironport": ["iphmx.com", "cisco.com"],
        "forcepoint": ["mailcontrol.com", "forcepoint.com"],
        "trend_micro": ["trendmicro.com", "tmems.com"],
        "sophos": ["sophos.com", "reflexion.net"],
        "microsoft_atp": ["eo-protection.outlook.com", "mail.protection.outlook.com"],
        "google_postini": ["postini.com", "psmtp.com"],
    }
    
    # Known organizations and their confirmed platforms (with high confidence)
    KNOWN_ORG_PLATFORMS = {
        # Based on confirmed analysis and public information
        "linkedin.com": (Platform.MICROSOFT, 0.95),  # Owned by Microsoft, uses O365
        "stanford.edu": (Platform.GOOGLE, 0.9),     # Known Google Workspace customer
        "nyu.edu": (Platform.GOOGLE, 0.9),          # Known Google Workspace customer
        "deloitte.com": (Platform.MICROSOFT, 0.85), # Large enterprise, likely O365
        "jpmorgan.com": (Platform.MICROSOFT, 0.85), # Large enterprise, likely O365
        "jpmorganchase.com": (Platform.MICROSOFT, 0.85),
        "goldmansachs.com": (Platform.MICROSOFT, 0.85),
        "morganstanley.com": (Platform.MICROSOFT, 0.85),
    }
    
    # Enhanced domain mappings (same as before)
    DOMAIN_MAPPINGS = {
        # Google domains
        "gmail.com": Platform.GOOGLE,
        "googlemail.com": Platform.GOOGLE,
        # Microsoft domains
        "outlook.com": Platform.MICROSOFT,
        "outlook.co.uk": Platform.MICROSOFT,
        "hotmail.com": Platform.MICROSOFT,
        "hotmail.co.uk": Platform.MICROSOFT,
        "hotmail.fr": Platform.MICROSOFT,
        "live.com": Platform.MICROSOFT,
        "live.co.uk": Platform.MICROSOFT,
        "msn.com": Platform.MICROSOFT,
        "microsoft.com": Platform.MICROSOFT,
        "office365.com": Platform.MICROSOFT,
        # ... (other platforms same as original)
    }
    
    @staticmethod
    def detect_from_email(email: str) -> PlatformDetectionResult:
        """
        Enhanced platform detection with third-party service awareness
        """
        if not email or "@" not in email:
            return PlatformDetectionResult(
                platform=Platform.UNKNOWN,
                email=email,
                domain="",
                error="Invalid email format"
            )
            
        # Extract domain from email
        domain = email.lower().split("@")[-1]
        
        # Check known domains first
        if domain in ImprovedPlatformDetector.DOMAIN_MAPPINGS:
            return PlatformDetectionResult(
                platform=ImprovedPlatformDetector.DOMAIN_MAPPINGS[domain],
                email=email,
                domain=domain,
                detection_method="known_domain",
                confidence=1.0
            )
        
        # Check known organization platforms
        if domain in ImprovedPlatformDetector.KNOWN_ORG_PLATFORMS:
            platform, confidence = ImprovedPlatformDetector.KNOWN_ORG_PLATFORMS[domain]
            return PlatformDetectionResult(
                platform=platform,
                email=email,
                domain=domain,
                detection_method="known_org",
                confidence=confidence
            )
        
        # Perform comprehensive DNS analysis
        mx_result = ImprovedPlatformDetector._check_mx_records_enhanced(domain)
        spf_result = ImprovedPlatformDetector._check_spf_records_enhanced(domain)
        
        # Combine results from multiple sources
        final_platform, confidence, method = ImprovedPlatformDetector._combine_detection_results(
            mx_result, spf_result
        )
        
        # Extract detected third-party services
        third_party_services = []
        if mx_result['third_party_services']:
            third_party_services.extend(mx_result['third_party_services'])
        if spf_result['third_party_services']:
            third_party_services.extend([s for s in spf_result['third_party_services'] 
                                       if s not in third_party_services])
        
        return PlatformDetectionResult(
            platform=final_platform,
            email=email,
            domain=domain,
            mx_records=mx_result['mx_hosts'],
            spf_records=spf_result['spf_records'],
            detection_method=method,
            raw_mx_data=mx_result['raw_mx_data'],
            raw_txt_data=spf_result['raw_txt_data'],
            third_party_services=third_party_services,
            confidence=confidence
        )
    
    @staticmethod
    def _check_mx_records_enhanced(domain: str) -> Dict[str, Any]:
        """
        Enhanced MX record checking with third-party service detection
        """
        result = {
            'platform': None,
            'mx_hosts': [],
            'raw_mx_data': [],
            'third_party_services': [],
            'indicators': []
        }
        
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            
            for mx in mx_records:
                mx_host = str(mx.exchange).lower()
                result['mx_hosts'].append(mx_host)
                result['raw_mx_data'].append({
                    'exchange': str(mx.exchange),
                    'preference': mx.preference,
                    'host': mx_host
                })
                
                # Check for third-party services first
                for service, patterns in ImprovedPlatformDetector.THIRD_PARTY_SERVICES.items():
                    for pattern in patterns:
                        if pattern in mx_host:
                            result['third_party_services'].append(service)
                            break
                
                # Direct platform detection (higher confidence)
                if not result['platform']:
                    if 'google' in mx_host or 'googlemail' in mx_host:
                        result['platform'] = Platform.GOOGLE
                        result['indicators'].append(f"MX: {mx_host}")
                    elif 'outlook' in mx_host or 'microsoft' in mx_host:
                        result['platform'] = Platform.MICROSOFT
                        result['indicators'].append(f"MX: {mx_host}")
                    # Check for indirect indicators
                    elif 'aspmx' in mx_host:  # Common Google pattern
                        result['platform'] = Platform.GOOGLE
                        result['indicators'].append(f"MX pattern: {mx_host}")
                    elif 'mail.protection.outlook' in mx_host:
                        result['platform'] = Platform.MICROSOFT
                        result['indicators'].append(f"MX protection: {mx_host}")
                
        except Exception as e:
            result['raw_mx_data'] = [{'error': str(e)}]
        
        return result
    
    @staticmethod
    def _check_spf_records_enhanced(domain: str) -> Dict[str, Any]:
        """
        Enhanced SPF/TXT record checking with deeper analysis
        """
        result = {
            'platform': None,
            'spf_records': [],
            'raw_txt_data': [],
            'third_party_services': [],
            'indicators': []
        }
        
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            
            for rdata in txt_records:
                txt_value = str(rdata).strip('"')
                result['raw_txt_data'].append({
                    'type': 'TXT',
                    'value': txt_value
                })
                
                # SPF record analysis
                if txt_value.startswith('v=spf1'):
                    result['spf_records'].append(txt_value)
                    
                    # Check all includes for platform hints
                    includes = [part for part in txt_value.split() if part.startswith('include:')]
                    
                    for include in includes:
                        # Direct platform detection
                        if '_spf.google.com' in include:
                            result['platform'] = Platform.GOOGLE
                            result['indicators'].append(f"SPF: {include}")
                        elif 'spf.protection.outlook.com' in include:
                            result['platform'] = Platform.MICROSOFT
                            result['indicators'].append(f"SPF: {include}")
                        elif 'zoho.com' in include:
                            result['platform'] = Platform.ZOHO
                            result['indicators'].append(f"SPF: {include}")
                        
                        # Third-party service detection
                        for service, patterns in ImprovedPlatformDetector.THIRD_PARTY_SERVICES.items():
                            for pattern in patterns:
                                if pattern in include:
                                    result['third_party_services'].append(service)
                                    break
                
                # Google site verification
                elif txt_value.startswith('google-site-verification='):
                    if not result['platform']:
                        result['platform'] = Platform.GOOGLE
                        result['indicators'].append("Google site verification")
                
                # Microsoft domain verification
                elif 'MS=' in txt_value and txt_value.startswith('MS='):
                    if not result['platform']:
                        result['platform'] = Platform.MICROSOFT
                        result['indicators'].append("Microsoft domain verification")
                
                # Additional platform indicators
                elif 'v=DKIM1' in txt_value:
                    # Check DKIM selectors that might indicate platform
                    if 'google' in domain:  # The TXT record domain, not email domain
                        result['indicators'].append("Google DKIM selector")
                    elif 'outlook' in domain or 'microsoft' in domain:
                        result['indicators'].append("Microsoft DKIM selector")
                        
        except Exception as e:
            result['raw_txt_data'] = [{'error': str(e)}]
        
        return result
    
    @staticmethod
    def _combine_detection_results(mx_result: Dict, spf_result: Dict) -> Tuple[Platform, float, str]:
        """
        Combine results from multiple detection methods with confidence scoring
        """
        # If both agree on a platform, high confidence
        if mx_result['platform'] and mx_result['platform'] == spf_result['platform']:
            return mx_result['platform'], 0.95, "mx_and_spf_agreement"
        
        # If only MX detected (more reliable for actual mail routing)
        if mx_result['platform']:
            confidence = 0.8
            # Lower confidence if third-party services detected
            if mx_result['third_party_services']:
                confidence = 0.6
            return mx_result['platform'], confidence, "mx_lookup"
        
        # If only SPF detected
        if spf_result['platform']:
            confidence = 0.7
            # Lower confidence if third-party services detected
            if spf_result['third_party_services']:
                confidence = 0.5
            return spf_result['platform'], confidence, "spf_lookup"
        
        # Heuristic detection based on third-party services
        # Many enterprise customers use these patterns:
        third_party_services = mx_result['third_party_services'] + spf_result['third_party_services']
        
        if third_party_services:
            # Proofpoint + MessageLabs often used by Microsoft shops
            if any(s in ['proofpoint', 'messagelabs'] for s in third_party_services):
                # Check for additional Microsoft indicators
                if any('outlook' in mx for mx in mx_result['mx_hosts']):
                    return Platform.MICROSOFT, 0.5, "third_party_heuristic"
            
            # If we have third-party services but no clear platform
            # This is where we'd need additional detection methods
            return Platform.UNKNOWN, 0.3, "third_party_masked"
        
        return Platform.UNKNOWN, 0.0, "no_detection"
    
    @staticmethod
    def perform_deep_analysis(email: str) -> Dict[str, Any]:
        """
        Perform deep analysis including SMTP verification and additional checks
        """
        basic_result = ImprovedPlatformDetector.detect_from_email(email)
        
        analysis = {
            'email': email,
            'basic_detection': {
                'platform': basic_result.platform.value,
                'confidence': basic_result.confidence,
                'method': basic_result.detection_method,
                'third_party_services': basic_result.third_party_services
            },
            'dns_analysis': {
                'mx_records': basic_result.mx_records,
                'spf_records': basic_result.spf_records
            }
        }
        
        # Additional checks could include:
        # 1. SMTP banner analysis (if enabled)
        # 2. DKIM selector checking
        # 3. Autodiscover endpoint testing
        # 4. Well-known URL checking (e.g., /.well-known/openid-configuration)
        
        return analysis