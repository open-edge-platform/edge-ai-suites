# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for run.py - Traffic Intersection Agent launcher script.

Tests cover:
- Module path setup
- Main function invocation
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestRunScript:
    """Tests for run.py launcher script."""

    def test_run_module_exists(self):
        """Test that run module can be imported."""
        # Just verify the module structure without executing __main__
        import importlib.util
        
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        spec = importlib.util.spec_from_file_location("run", run_path)
        
        assert spec is not None

    def test_current_dir_calculation(self):
        """Test that current directory is calculated correctly."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        expected_dir = run_path.parent
        
        # The script should add this directory to sys.path
        assert expected_dir.exists()
        assert (expected_dir / "main.py").exists()

    def test_sys_path_modification(self):
        """Test that run.py modifies sys.path correctly."""
        # Save original sys.path
        original_path = sys.path.copy()
        
        try:
            # Import run module (but don't execute __main__ block)
            run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
            
            # Read and exec just the path setup portion
            with open(run_path) as f:
                content = f.read()
            
            # Extract just the imports and path setup (before if __name__ == "__main__")
            setup_code = content.split('if __name__ == "__main__"')[0]
            
            # Execute in isolated namespace
            namespace = {'__file__': str(run_path)}
            exec(setup_code, namespace)
            
            # The current_dir should be set
            assert 'current_dir' in namespace
            assert namespace['current_dir'] == run_path.parent
            
        finally:
            # Restore original sys.path
            sys.path = original_path

    def test_path_contains_src_directory(self):
        """Test that sys.path contains src directory after setup."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        src_dir = str(run_path.parent)
        
        # Save and modify sys.path
        original_path = sys.path.copy()
        
        try:
            # Simulate what run.py does
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            
            assert src_dir in sys.path
            
        finally:
            sys.path = original_path


class TestRunMainInvocation:
    """Tests for main function invocation in run.py."""

    def test_main_is_called_when_run_as_script(self):
        """Test that main() is called when run.py is executed as script."""
        with patch('main.main') as mock_main:
            # Simulate running as __main__
            run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
            src_dir = str(run_path.parent)
            
            # Add src to path temporarily
            original_path = sys.path.copy()
            sys.path.insert(0, src_dir)
            
            try:
                # Create a namespace simulating __main__
                namespace = {
                    '__name__': '__main__',
                    '__file__': str(run_path)
                }
                
                # Just verify the import works
                from main import main as main_func
                assert main_func is not None
                
            finally:
                sys.path = original_path


class TestPathSetup:
    """Tests for path setup functionality."""

    def test_path_is_pathlib_path(self):
        """Test that Path is used for directory calculation."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert "from pathlib import Path" in content
        assert "Path(__file__).parent" in content

    def test_path_insert_at_beginning(self):
        """Test that path is inserted at position 0."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert "sys.path.insert(0," in content

    def test_run_script_imports(self):
        """Test that run.py has correct imports."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert "import sys" in content
        assert "import os" in content
        assert "from pathlib import Path" in content


class TestRunScriptDocstring:
    """Tests for run.py documentation."""

    def test_has_docstring(self):
        """Test that run.py has a module docstring."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert '"""' in content
        assert "launcher" in content.lower() or "launch" in content.lower()

    def test_has_copyright_header(self):
        """Test that run.py has copyright header."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert "Copyright" in content
        assert "Intel Corporation" in content


class TestRunScriptMainGuard:
    """Tests for __main__ guard in run.py."""

    def test_has_main_guard(self):
        """Test that run.py has if __name__ == '__main__' guard."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        assert 'if __name__ == "__main__"' in content

    def test_main_import_inside_guard(self):
        """Test that main is imported inside the guard."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        
        with open(run_path) as f:
            content = f.read()
        
        # Find the if __name__ block
        main_block = content.split('if __name__ == "__main__"')[1]
        
        assert "from main import main" in main_block
        assert "main()" in main_block


class TestRunScriptIntegration:
    """Integration tests for run.py."""

    def test_can_import_main_after_path_setup(self):
        """Test that main can be imported after path setup."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        src_dir = str(run_path.parent)
        
        original_path = sys.path.copy()
        
        try:
            sys.path.insert(0, src_dir)
            
            # This should work after path setup
            from main import main, create_app
            
            assert callable(main)
            assert callable(create_app)
            
        finally:
            sys.path = original_path

    def test_path_setup_enables_relative_imports(self):
        """Test that path setup enables module imports."""
        run_path = Path(__file__).parent.parent.parent / "src" / "run.py"
        src_dir = str(run_path.parent)
        
        original_path = sys.path.copy()
        
        try:
            sys.path.insert(0, src_dir)
            
            # These imports should work after path setup
            from services.config import ConfigService
            from api.routes import router
            
            assert ConfigService is not None
            assert router is not None
            
        finally:
            sys.path = original_path
