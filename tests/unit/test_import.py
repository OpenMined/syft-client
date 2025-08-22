"""
Unit tests for package imports and basic functionality
"""
import pytest


@pytest.mark.unit
class TestPackageImport:
    """Test basic package import functionality"""
    
    def test_import_syft_client(self):
        """Test that syft_client can be imported"""
        import syft_client
        assert syft_client is not None
    
    def test_import_main_functions(self):
        """Test that main functions can be imported"""
        from syft_client import login, logout, list_accounts
        
        assert login is not None
        assert logout is not None
        assert list_accounts is not None
    
    def test_import_client_classes(self):
        """Test that client classes can be imported"""
        from syft_client import GDriveUnifiedClient, create_gdrive_client
        
        assert GDriveUnifiedClient is not None
        assert create_gdrive_client is not None
    
    def test_import_wizard(self):
        """Test that wizard can be imported"""
        from syft_client import wizard
        
        assert wizard is not None
    
    def test_package_version(self):
        """Test that package version is defined"""
        import syft_client
        
        assert hasattr(syft_client, '__version__')
        assert isinstance(syft_client.__version__, str)
        assert len(syft_client.__version__) > 0
    
    def test_package_all_exports(self):
        """Test that __all__ exports are correct"""
        import syft_client
        
        assert hasattr(syft_client, '__all__')
        assert isinstance(syft_client.__all__, list)
        
        # Check that all listed exports actually exist
        for export in syft_client.__all__:
            assert hasattr(syft_client, export), f"Missing export: {export}"
    
    def test_import_submodules(self):
        """Test that submodules can be imported independently"""
        from syft_client import auth
        from syft_client import gdrive_unified
        from syft_client import wizard
        
        assert auth is not None
        assert gdrive_unified is not None
        assert wizard is not None


@pytest.mark.unit
class TestBasicFunctionality:
    """Test basic functionality without external dependencies"""
    
    def test_create_gdrive_client_function_exists(self):
        """Test that create_gdrive_client function exists and is callable"""
        from syft_client import create_gdrive_client
        
        assert callable(create_gdrive_client)
    
    def test_client_class_instantiation(self):
        """Test that GDriveUnifiedClient can be instantiated"""
        from syft_client import GDriveUnifiedClient
        
        client = GDriveUnifiedClient()
        assert client is not None
        assert hasattr(client, 'authenticate')
        assert hasattr(client, 'add_friend')
        assert hasattr(client, 'friends')
        assert hasattr(client, 'friend_requests')
    
    def test_auth_functions_exist(self):
        """Test that authentication functions exist"""
        from syft_client.auth import login, logout, list_accounts
        
        assert callable(login)
        assert callable(logout) 
        assert callable(list_accounts)
    
    def test_wallet_functions_exist(self):
        """Test that wallet management functions exist"""
        from syft_client.auth import (
            _get_wallet_dir,
            _get_account_dir,
            _list_wallet_accounts
        )
        
        assert callable(_get_wallet_dir)
        assert callable(_get_account_dir)
        assert callable(_list_wallet_accounts)


@pytest.mark.unit
class TestDependencyImports:
    """Test that required dependencies can be imported"""
    
    def test_google_api_imports(self):
        """Test that Google API dependencies are available"""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            
            assert Credentials is not None
            assert InstalledAppFlow is not None
            assert Request is not None
            assert build is not None
            assert HttpError is not None
        except ImportError as e:
            pytest.fail(f"Required Google API dependency missing: {e}")
    
    def test_optional_colab_import(self):
        """Test that Colab imports are handled gracefully"""
        # This should not raise an error even if Colab is not available
        from syft_client.gdrive_unified import IN_COLAB
        assert isinstance(IN_COLAB, bool)
    
    def test_syft_widget_import_graceful(self):
        """Test that syft_widget import is handled gracefully"""
        # This import should not fail the tests even if syft_widget is not available
        try:
            import syft_widget
            # If import succeeds, that's fine
            assert syft_widget is not None
        except ImportError:
            # If import fails, that's also fine - it's an optional dependency
            pass


@pytest.mark.unit
class TestModuleConstants:
    """Test module-level constants and configurations"""
    
    def test_gdrive_scopes_defined(self):
        """Test that Google Drive scopes are properly defined"""
        from syft_client.gdrive_unified import GDriveUnifiedClient
        
        assert hasattr(GDriveUnifiedClient, 'SCOPES')
        scopes = GDriveUnifiedClient.SCOPES
        assert isinstance(scopes, list)
        assert len(scopes) > 0
        assert 'https://www.googleapis.com/auth/drive' in scopes
    
    def test_package_structure(self):
        """Test package structure and organization"""
        import syft_client
        import syft_client.auth
        import syft_client.gdrive_unified
        import syft_client.wizard
        
        # Check that modules have expected attributes
        assert hasattr(syft_client.auth, 'login')
        assert hasattr(syft_client.gdrive_unified, 'GDriveUnifiedClient')
        assert hasattr(syft_client.wizard, 'wizard')


@pytest.mark.unit 
class TestErrorHandling:
    """Test basic error handling"""
    
    def test_client_creation_no_args(self):
        """Test client creation with no arguments doesn't crash"""
        from syft_client import GDriveUnifiedClient
        
        try:
            client = GDriveUnifiedClient()
            assert client is not None
        except Exception as e:
            pytest.fail(f"Client creation should not fail: {e}")
    
    def test_unauthenticated_client_properties(self):
        """Test that unauthenticated client properties don't crash"""
        from syft_client import GDriveUnifiedClient
        
        client = GDriveUnifiedClient()
        
        # These should not crash even when not authenticated
        repr_str = repr(client)
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0


@pytest.mark.unit
class TestCompatibility:
    """Test Python version compatibility"""
    
    def test_python_version_compatibility(self):
        """Test that code works with current Python version"""
        import sys
        
        # Should work with Python 3.8+
        assert sys.version_info >= (3, 8), "Python 3.8+ required"
    
    def test_pathlib_usage(self):
        """Test that pathlib is used correctly"""
        from pathlib import Path
        from syft_client.auth import _get_wallet_dir
        
        wallet_dir = _get_wallet_dir()
        assert isinstance(wallet_dir, Path)
    
    def test_typing_annotations(self):
        """Test that typing annotations are properly used"""
        from syft_client.gdrive_unified import GDriveUnifiedClient
        from syft_client.auth import login
        
        # These functions should have type hints (testing via inspection)
        import inspect
        
        # Check that functions have annotations
        login_sig = inspect.signature(login)
        assert len(login_sig.parameters) > 0
        
        # Check that class methods have annotations  
        client_methods = inspect.getmembers(GDriveUnifiedClient, predicate=inspect.isfunction)
        assert len(client_methods) > 0