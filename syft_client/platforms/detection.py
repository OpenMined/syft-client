"""Platform detection module"""

import socket
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import dns.resolver


class Platform(Enum):
    """Supported platforms"""

    GOOGLE_PERSONAL = "google_personal"  # Personal Gmail accounts
    GOOGLE_ORG = "google_org"  # Google Workspace accounts
    MICROSOFT = "microsoft"
    YAHOO = "yahoo"
    APPLE = "apple"
    ZOHO = "zoho"
    PROTON = "proton"
    GMX = "gmx"
    FASTMAIL = "fastmail"
    TUTANOTA = "tutanota"
    MAILCOM = "mailcom"
    QQ = "qq"  # Tencent QQ Mail - China
    NETEASE = "netease"  # NetEase (163.com, 126.com) - China
    MAILRU = "mailru"  # Mail.ru - Russia
    YANDEX = "yandex"  # Yandex Mail - Russia
    NAVER = "naver"  # Naver Mail - South Korea
    DROPBOX = "dropbox"  # Dropbox
    SMTP = "smtp"  # Generic SMTP
    UNKNOWN = "unknown"


@dataclass
class PlatformDetectionResult:
    """Result of platform detection including raw DNS data"""

    platform: Platform
    email: str
    domain: str
    mx_records: List[str] = None
    spf_records: List[str] = None
    detection_method: str = (
        "unknown"  # "known_domain", "mx_lookup", "spf_lookup", "smtp_banner"
    )
    raw_mx_data: List[Dict[str, Any]] = None
    raw_txt_data: List[Dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 0.0  # 0-1 confidence score
    third_party_service: Optional[str] = None
    detection_hints: List[str] = field(default_factory=list)


class PlatformProperties:
    """Properties of each platform"""

    # Primary platforms - email providers that are tied to specific email addresses
    PRIMARY_PLATFORMS = {
        Platform.GOOGLE_PERSONAL,
        Platform.GOOGLE_ORG,
        Platform.MICROSOFT,
        Platform.YAHOO,
        Platform.APPLE,
        Platform.ZOHO,
        Platform.PROTON,
        Platform.GMX,
        Platform.FASTMAIL,
        Platform.TUTANOTA,
        Platform.MAILCOM,
        Platform.QQ,
        Platform.NETEASE,
        Platform.MAILRU,
        Platform.YANDEX,
        Platform.NAVER,
        Platform.SMTP,
    }

    # Secondary platforms - services that can work with any email
    SECONDARY_PLATFORMS = {
        Platform.DROPBOX,
    }

    @staticmethod
    def is_primary(platform: Platform) -> bool:
        """Check if platform is a primary (email provider) platform"""
        return platform in PlatformProperties.PRIMARY_PLATFORMS

    @staticmethod
    def is_secondary(platform: Platform) -> bool:
        """Check if platform is a secondary (any email) platform"""
        return platform in PlatformProperties.SECONDARY_PLATFORMS

    @staticmethod
    def can_support_any_email(platform: Platform) -> bool:
        """Check if platform can work with any email address"""
        return platform in PlatformProperties.SECONDARY_PLATFORMS


class PlatformDetector:
    """Detects which platform an email belongs to"""

    # Known organizations and their email platforms
    # Based on public information and DNS analysis
    # Third-party service patterns
    THIRD_PARTY_PATTERNS = {
        "pphosted.com": "proofpoint",
        "proofpoint.com": "proofpoint",
        "messagelabs.com": "messagelabs",
        "messagelabs.net": "messagelabs",
        "iphmx.com": "ironport",
        "ironport.com": "ironport",
        "mimecast.com": "mimecast",
        "mimecast.net": "mimecast",
        "barracuda.com": "barracuda",
        "barracudanetworks.com": "barracuda",
        "forcepoint.com": "forcepoint",
        "mailcontrol.com": "forcepoint",
        "appriver.com": "appriver",
    }

    # Known organizations and their confirmed platforms
    # Based on public information, case studies, and DNS analysis
    KNOWN_ORG_PLATFORMS = {
        # Microsoft-owned or confirmed Microsoft users
        "linkedin.com": (Platform.MICROSOFT, "Microsoft-owned company"),
        "skype.com": (Platform.MICROSOFT, "Microsoft-owned service"),
        "github.com": (Platform.MICROSOFT, "Microsoft-owned company"),
        # Known Google Workspace customers (from public case studies)
        "stanford.edu": (Platform.GOOGLE_ORG, "Google Workspace customer"),
        "nyu.edu": (Platform.GOOGLE_ORG, "Google Workspace customer"),
        "airbnb.com": (Platform.GOOGLE_ORG, "Google Workspace customer"),
        "spotify.com": (Platform.GOOGLE_ORG, "Google Workspace customer"),
        "uber.com": (Platform.GOOGLE_ORG, "Google Workspace customer"),
        # Known Microsoft 365 customers (from public case studies)
        "jpmorgan.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "jpmorganchase.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "deloitte.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "deloite.com.au": (Platform.MICROSOFT, "Deloitte Australia"),
        "pwc.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "ey.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "kpmg.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "goldmansachs.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "morganstanley.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "bankofamerica.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        "wellsfargo.com": (Platform.MICROSOFT, "Microsoft 365 customer"),
        # Educational institutions - Microsoft
        "harvard.edu": (Platform.MICROSOFT, "Harvard University - Microsoft 365"),
        "alumni.harvard.edu": (Platform.MICROSOFT, "Harvard Alumni"),
        "post.harvard.edu": (Platform.MICROSOFT, "Harvard affiliates"),
        "mit.edu": (Platform.MICROSOFT, "MIT - Microsoft Exchange"),
        "csail.mit.edu": (Platform.MICROSOFT, "MIT CSAIL"),
        "yale.edu": (Platform.MICROSOFT, "Yale University - Microsoft 365"),
        "wustl.edu": (Platform.MICROSOFT, "Washington University in St. Louis"),
        "case.edu": (Platform.MICROSOFT, "Case Western Reserve University"),
        "rutgers.edu": (Platform.MICROSOFT, "Rutgers University"),
        # Educational institutions - Google
        "illinois.edu": (
            Platform.GOOGLE_ORG,
            "University of Illinois - Google Workspace",
        ),
        "umich.edu": (Platform.GOOGLE_ORG, "University of Michigan - Google Workspace"),
        "ucsd.edu": (Platform.GOOGLE_ORG, "UC San Diego - Google Workspace"),
        "ucr.edu": (Platform.GOOGLE_ORG, "UC Riverside - Google Workspace"),
        "utexas.edu": (Platform.GOOGLE_ORG, "UT Austin - Google Workspace"),
        "umn.edu": (Platform.GOOGLE_ORG, "University of Minnesota - Google Workspace"),
        "gmu.edu": (Platform.GOOGLE_ORG, "George Mason University - Google Workspace"),
        "gwu.edu": (
            Platform.GOOGLE_ORG,
            "George Washington University - Google Workspace",
        ),
        "gwmail.gwu.edu": (Platform.GOOGLE_ORG, "GWU student email"),
        # UK Universities
        "ox.ac.uk": (Platform.MICROSOFT, "University of Oxford - Microsoft 365"),
        "cs.ox.ac.uk": (Platform.MICROSOFT, "Oxford Computer Science"),
        "eng.ox.ac.uk": (Platform.MICROSOFT, "Oxford Engineering"),
        "maths.ox.ac.uk": (Platform.MICROSOFT, "Oxford Mathematics"),
        "stats.ox.ac.uk": (Platform.MICROSOFT, "Oxford Statistics"),
        "chch.ox.ac.uk": (Platform.MICROSOFT, "Christ Church Oxford"),
        "linacre.ox.ac.uk": (Platform.MICROSOFT, "Linacre College Oxford"),
        "balliol.ox.ac.uk": (Platform.MICROSOFT, "Balliol College Oxford"),
        "wolfson.ox.ac.uk": (Platform.MICROSOFT, "Wolfson College Oxford"),
        "sjc.ox.ac.uk": (Platform.MICROSOFT, "St John's College Oxford"),
        "spc.ox.ac.uk": (Platform.MICROSOFT, "St Peter's College Oxford"),
        "new.ox.ac.uk": (Platform.MICROSOFT, "New College Oxford"),
        "univ.ox.ac.uk": (Platform.MICROSOFT, "University College Oxford"),
        "cam.ac.uk": (Platform.MICROSOFT, "University of Cambridge - Microsoft 365"),
        "ed.ac.uk": (Platform.MICROSOFT, "University of Edinburgh - Microsoft 365"),
        "imperial.ac.uk": (Platform.MICROSOFT, "Imperial College London"),
        "ic.ac.uk": (Platform.MICROSOFT, "Imperial College London"),
        "glasgow.ac.uk": (Platform.MICROSOFT, "University of Glasgow"),
        "st-andrews.ac.uk": (Platform.MICROSOFT, "University of St Andrews"),
        "liverpool.ac.uk": (Platform.MICROSOFT, "University of Liverpool"),
        # Government organizations
        "nih.gov": (Platform.MICROSOFT, "National Institutes of Health"),
        "census.gov": (Platform.MICROSOFT, "US Census Bureau"),
        "state.gov": (Platform.MICROSOFT, "US State Department"),
        "anl.gov": (Platform.MICROSOFT, "Argonne National Laboratory"),
        "lanl.gov": (Platform.MICROSOFT, "Los Alamos National Laboratory"),
        # Major tech companies
        "amazon.com": (Platform.GOOGLE_ORG, "Amazon - Google Workspace"),
        "amazon.co.uk": (Platform.GOOGLE_ORG, "Amazon UK"),
        "amazon.co": (Platform.GOOGLE_ORG, "Amazon regional"),
        "intel.com": (Platform.MICROSOFT, "Intel Corporation"),
        "cisco.com": (Platform.MICROSOFT, "Cisco Systems"),
        "samsung.com": (Platform.MICROSOFT, "Samsung Electronics"),
        "darktrace.com": (Platform.MICROSOFT, "Darktrace cybersecurity"),
        "bitdefender.com": (Platform.GOOGLE_ORG, "Bitdefender antivirus"),
        "cloudflare.com": (Platform.GOOGLE_ORG, "Cloudflare - Google Workspace"),
        # Healthcare & Pharma
        "roche.com": (Platform.MICROSOFT, "Roche pharmaceutical"),
        "jhmi.edu": (Platform.MICROSOFT, "Johns Hopkins Medicine"),
        "jhuapl.edu": (Platform.MICROSOFT, "Johns Hopkins APL"),
        "mssm.edu": (Platform.MICROSOFT, "Mount Sinai School of Medicine"),
        # Financial & Consulting additional
        "affirm.com": (Platform.GOOGLE_ORG, "Affirm fintech - Google Workspace"),
        "bloomberg.net": (Platform.MICROSOFT, "Bloomberg LP"),
        # European institutions
        "inria.fr": (Platform.MICROSOFT, "INRIA French research"),
        "cnr.it": (Platform.MICROSOFT, "Italian National Research Council"),
        "fraunhofer.de": (Platform.MICROSOFT, "Fraunhofer Society"),
        "cern.ch": (Platform.MICROSOFT, "CERN - Microsoft 365"),
        # International organizations
        "ieee.org": (
            Platform.MICROSOFT,
            "IEEE - Institute of Electrical and Electronics Engineers",
        ),
        "acm.org": (Platform.MICROSOFT, "ACM - Association for Computing Machinery"),
        "wikimedia.org": (
            Platform.GOOGLE_ORG,
            "Wikimedia Foundation - Google Workspace",
        ),
        "icrc.org": (Platform.MICROSOFT, "International Committee of the Red Cross"),
    }

    # Known email domain mappings
    DOMAIN_MAPPINGS = {
        # Google domains (~43% market share)
        "gmail.com": Platform.GOOGLE_PERSONAL,
        "googlemail.com": Platform.GOOGLE_PERSONAL,
        # Microsoft domains (~18% market share)
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
        # Yahoo domains (~10% market share)
        "yahoo.com": Platform.YAHOO,
        "yahoo.co.uk": Platform.YAHOO,
        "yahoo.fr": Platform.YAHOO,
        "yahoo.de": Platform.YAHOO,
        "yahoo.ca": Platform.YAHOO,
        "yahoo.co.jp": Platform.YAHOO,
        "ymail.com": Platform.YAHOO,
        "rocketmail.com": Platform.YAHOO,
        # Apple domains (~8% market share)
        "icloud.com": Platform.APPLE,
        "me.com": Platform.APPLE,
        "mac.com": Platform.APPLE,
        # Zoho domains (~4% market share)
        "zoho.com": Platform.ZOHO,
        "zohomail.com": Platform.ZOHO,
        "zoho.eu": Platform.ZOHO,
        # ProtonMail domains (~2% market share)
        "proton.me": Platform.PROTON,
        "protonmail.com": Platform.PROTON,
        "protonmail.ch": Platform.PROTON,
        "pm.me": Platform.PROTON,
        # GMX domains (~2% market share)
        "gmx.com": Platform.GMX,
        "gmx.net": Platform.GMX,
        "gmx.de": Platform.GMX,
        "gmx.at": Platform.GMX,
        "gmx.ch": Platform.GMX,
        # Fastmail domains (~1% market share)
        "fastmail.com": Platform.FASTMAIL,
        "fastmail.fm": Platform.FASTMAIL,
        "fastmail.us": Platform.FASTMAIL,
        # Tutanota domains (<1% market share)
        "tutanota.com": Platform.TUTANOTA,
        "tutanota.de": Platform.TUTANOTA,
        "tutamail.com": Platform.TUTANOTA,
        "tuta.io": Platform.TUTANOTA,
        # Mail.com domains (<1% market share)
        "mail.com": Platform.MAILCOM,
        "email.com": Platform.MAILCOM,
        "usa.com": Platform.MAILCOM,
        "myself.com": Platform.MAILCOM,
        "consultant.com": Platform.MAILCOM,
        "post.com": Platform.MAILCOM,
        "europe.com": Platform.MAILCOM,
        "asia.com": Platform.MAILCOM,
        "iname.com": Platform.MAILCOM,
        "writeme.com": Platform.MAILCOM,
        "dr.com": Platform.MAILCOM,
        "engineer.com": Platform.MAILCOM,
        "cheerful.com": Platform.MAILCOM,
        # QQ Mail domains (Tencent - China)
        "qq.com": Platform.QQ,
        "foxmail.com": Platform.QQ,  # Foxmail is owned by Tencent/QQ
        # NetEase Mail domains (China)
        "163.com": Platform.NETEASE,
        "126.com": Platform.NETEASE,
        "yeah.net": Platform.NETEASE,
        "vip.163.com": Platform.NETEASE,
        # Mail.ru domains (Russia)
        "mail.ru": Platform.MAILRU,
        "list.ru": Platform.MAILRU,
        "bk.ru": Platform.MAILRU,
        "inbox.ru": Platform.MAILRU,
        # Yandex Mail domains (Russia)
        "yandex.ru": Platform.YANDEX,
        "yandex.com": Platform.YANDEX,
        "ya.ru": Platform.YANDEX,
        # Naver Mail domains (South Korea)
        "naver.com": Platform.NAVER,
        "navercorp.com": Platform.NAVER,
        # Other regional providers (keep as UNKNOWN for now)
        "sina.cn": Platform.UNKNOWN,  # Sina Mail - Chinese email service
        "sina.com": Platform.UNKNOWN,  # Sina Mail
        "139.com": Platform.UNKNOWN,  # China Mobile mail
        "188.com": Platform.UNKNOWN,  # China Telecom mail
        "rambler.ru": Platform.UNKNOWN,  # Rambler Mail - Russian email service
        "rediffmail.com": Platform.UNKNOWN,  # Rediffmail - Indian email service
        "libero.it": Platform.UNKNOWN,  # Libero Mail - Italian email service
        "web.de": Platform.UNKNOWN,  # WEB.DE - German email service
        "t-online.de": Platform.UNKNOWN,  # T-Online - German email service
        "laposte.net": Platform.UNKNOWN,  # La Poste - French email service
        "orange.com": Platform.UNKNOWN,  # Orange Mail - French email service
        "terra.com.br": Platform.UNKNOWN,  # Terra Mail - Brazilian email service
        "btinternet.com": Platform.UNKNOWN,  # BT Internet - UK ISP email
        "ntlworld.com": Platform.UNKNOWN,  # NTL World - UK ISP email
        "xtra.co.nz": Platform.UNKNOWN,  # Xtra Mail - New Zealand ISP email
        "optusnet.com.au": Platform.UNKNOWN,  # Optus - Australian ISP email
        "iinet.net.au": Platform.UNKNOWN,  # iiNet - Australian ISP email
        "tiscali.co.za": Platform.UNKNOWN,  # Tiscali - South African ISP email
        # Privacy-focused email providers
        "posteo.de": Platform.UNKNOWN,  # Posteo - German privacy email
        "posteo.net": Platform.UNKNOWN,  # Posteo alternative domain
        "mailbox.org": Platform.UNKNOWN,  # Mailbox.org - German privacy email
        "mailfence.com": Platform.UNKNOWN,  # Mailfence - Belgian privacy email
        "simplelogin.com": Platform.UNKNOWN,  # SimpleLogin - email aliasing service
        "skiff.com": Platform.UNKNOWN,  # Skiff Mail - privacy email
    }

    @staticmethod
    def detect_from_email(email: str) -> PlatformDetectionResult:
        """
        Detect platform from email address with full details

        Args:
            email: Email address to analyze

        Returns:
            PlatformDetectionResult with platform and DNS details
        """
        if not email or "@" not in email:
            return PlatformDetectionResult(
                platform=Platform.UNKNOWN,
                email=email,
                domain="",
                error="Invalid email format",
            )

        # Extract domain from email
        domain = email.lower().split("@")[-1]

        # Check known domains first
        if domain in PlatformDetector.DOMAIN_MAPPINGS:
            return PlatformDetectionResult(
                platform=PlatformDetector.DOMAIN_MAPPINGS[domain],
                email=email,
                domain=domain,
                detection_method="known_domain",
                confidence=1.0,
            )

        # Check known organization platforms
        if domain in PlatformDetector.KNOWN_ORG_PLATFORMS:
            platform, reason = PlatformDetector.KNOWN_ORG_PLATFORMS[domain]
            return PlatformDetectionResult(
                platform=platform,
                email=email,
                domain=domain,
                detection_method="known_org",
                confidence=0.95,
                detection_hints=[f"Known organization: {reason}"],
            )

        # For unknown domains, perform comprehensive DNS analysis
        mx_result = PlatformDetector._analyze_mx_records(domain)
        spf_result = PlatformDetector._analyze_spf_records(domain)
        txt_result = PlatformDetector._analyze_txt_records(domain)

        # Combine results with confidence scoring
        final_platform, confidence, method, third_party = (
            PlatformDetector._combine_results(mx_result, spf_result, txt_result)
        )

        # Collect detection hints
        detection_hints = []
        if mx_result.get("hints"):
            detection_hints.extend(mx_result["hints"])
        if spf_result.get("hints"):
            detection_hints.extend(spf_result["hints"])
        if txt_result.get("hints"):
            detection_hints.extend(txt_result["hints"])

        # Return detection result with all collected information
        return PlatformDetectionResult(
            platform=final_platform,
            email=email,
            domain=domain,
            mx_records=mx_result.get("mx_hosts", []),
            spf_records=spf_result.get("spf_records", []),
            detection_method=method,
            raw_mx_data=mx_result.get("raw_data", []),
            raw_txt_data=spf_result.get("raw_data", []),
            confidence=confidence,
            third_party_service=third_party,
            detection_hints=detection_hints,
        )

        # Note: We don't automatically do SMTP verification in the main flow
        # because it's intrusive and can get blocked. Users should call
        # verify_email_smtp() explicitly if they want SMTP verification.

    # Supported platforms for login
    SUPPORTED_PLATFORMS = {
        Platform.GOOGLE_PERSONAL,
        Platform.GOOGLE_ORG,
        Platform.MICROSOFT,
        Platform.YAHOO,
        Platform.APPLE,
        Platform.ZOHO,
        Platform.PROTON,
        Platform.GMX,
        Platform.FASTMAIL,
        Platform.MAILCOM,
        Platform.DROPBOX,
        Platform.SMTP,
    }

    @staticmethod
    def is_supported(platform: Platform) -> bool:
        """Check if a platform is currently supported"""
        return platform in PlatformDetector.SUPPORTED_PLATFORMS

    @staticmethod
    def _analyze_mx_records(domain: str) -> Dict[str, Any]:
        """Enhanced MX record analysis with third-party detection"""
        result = {
            "platform": None,
            "mx_hosts": [],
            "raw_data": [],
            "third_party": None,
            "hints": [],
        }

        try:
            # Get MX records for the domain
            mx_records = dns.resolver.resolve(domain, "MX")

            # Process each MX record
            for mx in mx_records:
                mx_host = str(mx.exchange).lower()
                result["mx_hosts"].append(mx_host)
                result["raw_data"].append(
                    {
                        "exchange": str(mx.exchange),
                        "preference": mx.preference,
                        "host": mx_host,
                    }
                )

                # Check for third-party services first
                for pattern, service in PlatformDetector.THIRD_PARTY_PATTERNS.items():
                    if pattern in mx_host:
                        result["third_party"] = service
                        result["hints"].append(f"MX points to {service}")
                        break

                # Only detect platform from first match
                if result["platform"] is None:
                    # Enhanced Google detection - check if it's a known Gmail domain
                    if any(
                        pattern in mx_host
                        for pattern in ["google", "googlemail", "aspmx"]
                    ):
                        # If it's a known Gmail domain, it's personal
                        if domain in ["gmail.com", "googlemail.com"]:
                            result["platform"] = Platform.GOOGLE_PERSONAL
                            result["hints"].append("Personal Gmail account")
                        else:
                            # Otherwise it's likely Google Workspace
                            result["platform"] = Platform.GOOGLE_ORG
                            result["hints"].append("Google Workspace pattern in MX")
                    # Microsoft 365 / Outlook
                    elif any(
                        pattern in mx_host
                        for pattern in ["outlook", "microsoft", "office365"]
                    ):
                        result["platform"] = Platform.MICROSOFT
                        result["hints"].append("Microsoft pattern in MX")
                    # Yahoo
                    elif "yahoo" in mx_host:
                        result["platform"] = Platform.YAHOO
                    elif "apple" in mx_host or "icloud" in mx_host:
                        result["platform"] = Platform.APPLE
                    elif "zoho" in mx_host:
                        result["platform"] = Platform.ZOHO
                    elif "proton" in mx_host or "protonmail" in mx_host:
                        result["platform"] = Platform.PROTON
                    elif "gmx" in mx_host:
                        result["platform"] = Platform.GMX
                    elif "fastmail" in mx_host or "messagingengine" in mx_host:
                        result["platform"] = Platform.FASTMAIL
                    elif "tutanota" in mx_host:
                        result["platform"] = Platform.TUTANOTA
                    # QQ Mail
                    elif "qq.com" in mx_host:
                        result["platform"] = Platform.QQ
                    # NetEase
                    elif any(
                        pattern in mx_host
                        for pattern in ["163.com", "126.com", "netease"]
                    ):
                        result["platform"] = Platform.NETEASE
                    # Mail.ru
                    elif "mail.ru" in mx_host:
                        result["platform"] = Platform.MAILRU
                    # Yandex
                    elif "yandex" in mx_host:
                        result["platform"] = Platform.YANDEX
                    # Naver
                    elif "naver" in mx_host:
                        result["platform"] = Platform.NAVER

        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _analyze_spf_records(domain: str) -> Dict[str, Any]:
        """Enhanced SPF record analysis"""
        result = {"platform": None, "spf_records": [], "raw_data": [], "hints": []}

        try:
            # Get TXT records for the domain
            txt_records = dns.resolver.resolve(domain, "TXT")

            # Process each TXT record
            for rdata in txt_records:
                txt_value = str(rdata).strip('"')

                result["raw_data"].append({"type": "TXT", "value": txt_value})

                if txt_value.startswith("v=spf1"):
                    result["spf_records"].append(txt_value)

                    # Check all includes, not just the first one
                    includes = [
                        part
                        for part in txt_value.split()
                        if part.startswith("include:")
                    ]

                    for include in includes:
                        if "_spf.google.com" in include:
                            # Check if it's a known Gmail domain
                            if domain in ["gmail.com", "googlemail.com"]:
                                result["platform"] = Platform.GOOGLE_PERSONAL
                                result["hints"].append(
                                    "Personal Gmail SPF include found"
                                )
                            else:
                                result["platform"] = Platform.GOOGLE_ORG
                                result["hints"].append(
                                    "Google Workspace SPF include found"
                                )
                        elif "spf.protection.outlook.com" in include:
                            result["platform"] = Platform.MICROSOFT
                            result["hints"].append("Microsoft SPF include found")
                        elif "zoho.com" in include:
                            result["platform"] = Platform.ZOHO
                            result["hints"].append("Zoho SPF include found")
                        elif "proofpoint" in include:
                            result["hints"].append("Proofpoint SPF include found")
                        elif "messagelabs" in include:
                            result["hints"].append("MessageLabs SPF include found")

        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _analyze_txt_records(domain: str) -> Dict[str, Any]:
        """Analyze other TXT records for platform hints"""
        result = {"platform": None, "hints": []}

        try:
            txt_records = dns.resolver.resolve(domain, "TXT")

            for rdata in txt_records:
                txt_value = str(rdata).strip('"')

                # Google site verification
                if txt_value.startswith("google-site-verification="):
                    # Check if it's a known Gmail domain
                    if domain in ["gmail.com", "googlemail.com"]:
                        result["platform"] = Platform.GOOGLE_PERSONAL
                        result["hints"].append("Personal Gmail site verification found")
                    else:
                        result["platform"] = Platform.GOOGLE_ORG
                        result["hints"].append(
                            "Google Workspace site verification found"
                        )

                # Microsoft domain verification
                elif txt_value.startswith("MS="):
                    result["platform"] = Platform.MICROSOFT
                    result["hints"].append("Microsoft domain verification found")

                # Apple domain verification
                elif txt_value.startswith("apple-domain-verification="):
                    result["platform"] = Platform.APPLE
                    result["hints"].append("Apple domain verification found")

        except Exception:
            pass  # TXT lookup failures are common

        return result

    @staticmethod
    def _combine_results(
        mx_result: Dict, spf_result: Dict, txt_result: Dict
    ) -> tuple[Platform, float, str, Optional[str]]:
        """
        Combine results from different detection methods with confidence scoring
        Returns: (platform, confidence, method, third_party_service)
        """
        third_party = mx_result.get("third_party")

        # If all agree on a platform, high confidence
        platforms = [
            r["platform"]
            for r in [mx_result, spf_result, txt_result]
            if r.get("platform")
        ]
        if platforms and all(p == platforms[0] for p in platforms):
            return platforms[0], 0.95, "multiple_methods", third_party

        # If MX and SPF agree, good confidence
        if mx_result.get("platform") and mx_result.get("platform") == spf_result.get(
            "platform"
        ):
            return mx_result["platform"], 0.85, "mx_and_spf", third_party

        # If only MX detected (most reliable)
        if mx_result.get("platform"):
            confidence = 0.7 if not third_party else 0.5
            return mx_result["platform"], confidence, "mx_only", third_party

        # If only SPF detected
        if spf_result.get("platform"):
            return spf_result["platform"], 0.6, "spf_only", third_party

        # If only TXT records detected
        if txt_result.get("platform"):
            return txt_result["platform"], 0.5, "txt_only", third_party

        # If third-party detected but no platform, make educated guess
        if third_party:
            # Many enterprises with third-party services use Microsoft
            return Platform.MICROSOFT, 0.3, "third_party_heuristic", third_party

        return Platform.UNKNOWN, 0.0, "no_detection", third_party

    @staticmethod
    def _check_smtp_verification(
        email: str, domain: str
    ) -> tuple[Optional[Platform], Dict[str, Any]]:
        """
        Use SMTP commands to verify email existence and detect provider
        Based on: https://www.labnol.org/internet/email/verify-email-address/18401/

        Returns: (platform, smtp_response_data)
        """
        import smtplib

        smtp_data = {}

        try:
            # Get MX records
            mx_records = dns.resolver.resolve(domain, "MX")
            if not mx_records:
                return None, {"error": "No MX records found"}

            # Sort by preference and use the primary MX server
            mx_list = sorted([(mx.preference, str(mx.exchange)) for mx in mx_records])
            mx_host = mx_list[0][1]
            smtp_data["mx_host"] = mx_host

            # Connect to SMTP server
            smtp = smtplib.SMTP(timeout=10)
            smtp.set_debuglevel(0)  # No debug output

            # Connect and get banner
            code, banner = smtp.connect(mx_host, 25)
            smtp_data["banner"] = banner.decode("utf-8", errors="ignore")
            smtp_data["connect_code"] = code

            # Detect platform from banner
            banner_lower = banner.decode("utf-8", errors="ignore").lower()
            detected_platform = None

            if "google" in banner_lower or "gmail" in banner_lower:
                # Check if it's a known Gmail domain
                if domain in ["gmail.com", "googlemail.com"]:
                    detected_platform = Platform.GOOGLE_PERSONAL
                else:
                    detected_platform = Platform.GOOGLE_ORG
            elif "microsoft" in banner_lower or "outlook" in banner_lower:
                detected_platform = Platform.MICROSOFT
            elif "yahoo" in banner_lower:
                detected_platform = Platform.YAHOO

            # Send HELO
            code, message = smtp.helo("verification.local")
            smtp_data["helo_response"] = {
                "code": code,
                "message": message.decode("utf-8", errors="ignore"),
            }

            # Try to verify the email address
            # First, set a fake sender
            code, message = smtp.mail("test@verification.local")
            smtp_data["mail_from_response"] = {
                "code": code,
                "message": message.decode("utf-8", errors="ignore"),
            }

            # Now try the actual recipient
            code, message = smtp.rcpt(email)
            smtp_data["rcpt_to_response"] = {
                "code": code,
                "message": message.decode("utf-8", errors="ignore"),
                "exists": code == 250,  # 250 means address exists
            }

            # Check response for additional platform hints
            if "google" in message.decode("utf-8", errors="ignore").lower():
                # Check if it's a known Gmail domain
                if domain in ["gmail.com", "googlemail.com"]:
                    detected_platform = Platform.GOOGLE_PERSONAL
                else:
                    detected_platform = Platform.GOOGLE_ORG

            smtp.quit()

            return detected_platform, smtp_data

        except smtplib.SMTPServerDisconnected:
            smtp_data["error"] = "Server disconnected - may have rate limiting"
        except smtplib.SMTPConnectError as e:
            smtp_data["error"] = f"Connection error: {str(e)}"
        except Exception as e:
            smtp_data["error"] = f"SMTP verification failed: {str(e)}"

        return None, smtp_data


# Convenience functions
def detect_platform_full(email: str) -> PlatformDetectionResult:
    """Detect platform from email address with full details"""
    return PlatformDetector.detect_from_email(email)


def detect_primary_platform(
    email: str, provider: Optional[str] = None, raise_on_unknown: bool = True
) -> Platform:
    """
    Detect platform from email address (backward compatible)

    Args:
        email: Email address to detect platform for
        provider: Optional provider override (e.g., 'google_personal', 'microsoft')
        raise_on_unknown: If True, raise helpful error for unknown platforms

    Returns:
        Platform enum

    Raises:
        ValueError: If provider is invalid, platform unknown, or platform unsupported
    """
    # If provider is specified, try to use it
    if provider:
        try:
            platform = Platform(provider.lower())
        except ValueError:
            # Create list of valid provider strings
            supported_providers = sorted(
                [p.value for p in PlatformDetector.SUPPORTED_PLATFORMS]
            )
            raise ValueError(
                f"Invalid provider '{provider}'. Valid options are: {', '.join(supported_providers)}"
            )
    else:
        # Otherwise auto-detect
        result = PlatformDetector.detect_from_email(email)
        platform = result.platform

    # Check if platform is supported
    if platform != Platform.UNKNOWN and not PlatformDetector.is_supported(platform):
        supported = sorted([p.value for p in PlatformDetector.SUPPORTED_PLATFORMS])
        raise ValueError(
            f"\nThe email provider '{platform.value}' was detected but is not currently supported.\n\n"
            f"Supported providers are: {', '.join(supported)}\n\n"
            f"If you believe this is incorrect, you can try specifying a different provider:\n"
            f"  login(email='{email}', provider='microsoft')      # If using Office 365\n"
            f"  login(email='{email}', provider='google_personal') # If personal Gmail\n"
            f"  login(email='{email}', provider='google_org')      # If Google Workspace\n"
        )

    # Handle unknown platform if requested
    if raise_on_unknown and platform == Platform.UNKNOWN:
        provider_examples = {
            "google_personal": "Personal Gmail accounts",
            "google_org": "Google Workspace (organizational)",
            "microsoft": "Outlook, Hotmail, Live, Office 365",
            "yahoo": "Yahoo Mail",
            "apple": "iCloud Mail",
            "zoho": "Zoho Mail",
            "proton": "ProtonMail",
            "gmx": "GMX Mail",
            "fastmail": "Fastmail",
            "mailcom": "Mail.com",
            "dropbox": "Dropbox (file storage only)",
            "smtp": "Generic SMTP/IMAP email",
        }

        # Format provider list with examples
        provider_list = []
        for prov, desc in provider_examples.items():
            provider_list.append(f"  • '{prov}' - {desc}")

        raise ValueError(
            f"\nCould not automatically detect the email provider for: {email}\n\n"
            f"Please re-run login() and specify your email provider manually:\n\n"
            f"  login(email='{email}', provider='provider_name')\n\n"
            f"Supported providers:\n" + "\n".join(provider_list) + "\n\n"
            f"Example:\n"
            f"  login(email='{email}', provider='microsoft')      # for Office 365\n"
            f"  login(email='{email}', provider='google_personal') # for personal Gmail\n"
            f"  login(email='{email}', provider='google_org')      # for Google Workspace\n"
        )

    return platform


def get_secondary_platforms() -> List[Platform]:
    """
    Get list of secondary platforms that can work with any email address

    Returns:
        List of Platform enums that support any email
    """
    return list(PlatformProperties.SECONDARY_PLATFORMS)


def verify_email_smtp(email: str) -> Dict[str, Any]:
    """
    Verify if an email address exists using SMTP commands

    Returns dict with:
    - exists: bool indicating if email exists
    - platform: detected platform if any
    - smtp_data: raw SMTP response data
    """
    if not email or "@" not in email:
        return {"exists": False, "error": "Invalid email format"}

    domain = email.lower().split("@")[-1]
    platform, smtp_data = PlatformDetector._check_smtp_verification(email, domain)

    result = {
        "email": email,
        "domain": domain,
        "exists": smtp_data.get("rcpt_to_response", {}).get("exists", False),
        "platform": platform.value if platform else "unknown",
        "smtp_data": smtp_data,
    }

    return result
