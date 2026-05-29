"""Tests for enclave attestation verification."""

from unittest.mock import patch

import pytest

from syft_client.sync.version.attestation import (
    EXPECTED_SYFT_VERSION,
    AttestationError,
    AttestationResult,
    verify_attestation_token,
)

FAKE_IMAGE_DIGEST = "sha256:abc123"


def _valid_claims(**overrides):
    """Build a valid claims dict, optionally overriding specific fields."""
    claims = {
        "secboot": True,
        "dbgstat": "disabled-since-boot",
        "eat_nonce": [EXPECTED_SYFT_VERSION],
        "submods": {
            "container": {
                "image_digest": FAKE_IMAGE_DIGEST,
                "image_reference": "docker.io/openmined/syft-enclave:latest",
            }
        },
    }
    claims.update(overrides)
    return claims


@pytest.fixture
def mock_verify():
    """Patch google id_token.verify_token to return valid claims."""
    with (
        patch("syft_client.sync.version.attestation.id_token.verify_token") as mock_vt,
        patch("syft_client.sync.version.attestation.google_requests.Request"),
    ):
        mock_vt.return_value = _valid_claims()
        yield mock_vt


class TestVerifyAttestationToken:
    @pytest.mark.skip(reason="version hash check is currently disabled")
    def test_all_checks_pass(self, mock_verify):
        result = verify_attestation_token("fake-token", verbose=False)
        assert result.all_passed()
        assert len(result.checks) == 5
        assert all(c.passed for c in result.checks)

    def test_jwt_signature_failure(self, mock_verify):
        mock_verify.side_effect = ValueError("bad signature")
        with pytest.raises(AttestationError, match="JWT signature"):
            verify_attestation_token("fake-token", verbose=False)

    def test_secure_boot_disabled(self, mock_verify):
        mock_verify.return_value = _valid_claims(secboot=False)
        with pytest.raises(AttestationError, match="Secure boot"):
            verify_attestation_token("fake-token", verbose=False)

    def test_secure_boot_missing(self, mock_verify):
        claims = _valid_claims()
        del claims["secboot"]
        mock_verify.return_value = claims
        with pytest.raises(AttestationError, match="Secure boot"):
            verify_attestation_token("fake-token", verbose=False)

    def test_debug_enabled(self, mock_verify):
        mock_verify.return_value = _valid_claims(dbgstat="enabled")
        with pytest.raises(AttestationError, match="Debug mode"):
            verify_attestation_token("fake-token", verbose=False)

    def test_version_mismatch(self, mock_verify):
        mock_verify.return_value = _valid_claims(eat_nonce=["0.0.1"])
        with pytest.raises(AttestationError, match="Version mismatch"):
            verify_attestation_token("fake-token", verbose=False)

    @pytest.mark.skip(reason="version check is currently disabled")
    def test_version_missing(self, mock_verify):
        mock_verify.return_value = _valid_claims(eat_nonce=[])
        with pytest.raises(AttestationError, match="Version mismatch"):
            verify_attestation_token("fake-token", verbose=False)

    def test_version_as_string(self, mock_verify):
        """Google returns eat_nonce as a string for single nonce."""
        mock_verify.return_value = _valid_claims(eat_nonce=EXPECTED_SYFT_VERSION)
        result = verify_attestation_token("fake-token", verbose=False)
        version_check = next(c for c in result.checks if c.name == "version_match")
        assert version_check.passed is not False

    def test_image_digest_mismatch(self, mock_verify):
        with patch(
            "syft_client.sync.version.attestation.EXPECTED_IMAGE_DIGEST",
            "sha256:expected",
        ):
            mock_verify.return_value = _valid_claims()
            with pytest.raises(AttestationError, match="Image digest"):
                verify_attestation_token("fake-token", verbose=False)

    @pytest.mark.skip(reason="version check is currently disabled")
    def test_image_digest_skipped_when_not_configured(self, mock_verify):
        """When EXPECTED_IMAGE_DIGEST is empty, image check passes with skip note."""
        result = verify_attestation_token("fake-token", verbose=False)
        image_check = next(c for c in result.checks if c.name == "image_digest")
        assert image_check.passed
        assert "skipped" in image_check.detail

    def test_image_digest_matches(self, mock_verify):
        with patch(
            "syft_client.sync.version.attestation.EXPECTED_IMAGE_DIGEST",
            FAKE_IMAGE_DIGEST,
        ):
            result = verify_attestation_token("fake-token", verbose=False)
            image_check = next(c for c in result.checks if c.name == "image_digest")
            assert image_check.passed
            assert "matches" in image_check.detail

    def test_error_carries_result(self, mock_verify):
        mock_verify.return_value = _valid_claims(secboot=False)
        with pytest.raises(AttestationError) as exc_info:
            verify_attestation_token("fake-token", verbose=False)
        assert exc_info.value.result is not None
        assert exc_info.value.result.first_failure().name == "secure_boot"

    def test_fails_fast_on_first_error(self, mock_verify):
        """Earlier failure should prevent later checks from running."""
        mock_verify.return_value = _valid_claims(secboot=False)
        with pytest.raises(AttestationError) as exc_info:
            verify_attestation_token("fake-token", verbose=False)
        check_names = [c.name for c in exc_info.value.result.checks]
        assert "jwt_signature" in check_names
        assert "secure_boot" in check_names
        assert "version_match" not in check_names


class TestAttestationResult:
    def test_all_passed(self):
        result = AttestationResult()
        result.add("a", "A", True, "ok")
        result.add("b", "B", True, "ok")
        assert result.all_passed()

    def test_not_all_passed(self):
        result = AttestationResult()
        result.add("a", "A", True, "ok")
        result.add("b", "B", False, "fail")
        assert not result.all_passed()

    def test_first_failure(self):
        result = AttestationResult()
        result.add("a", "A", True, "ok")
        result.add("b", "B", False, "fail")
        result.add("c", "C", False, "also fail")
        assert result.first_failure().name == "b"

    def test_first_failure_none_when_all_pass(self):
        result = AttestationResult()
        result.add("a", "A", True, "ok")
        assert result.first_failure() is None
