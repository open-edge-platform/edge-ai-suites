# Quick Test Reference Guide

## 🚀 Running Tests

### Setup (First Time Only)
```bash
# Navigate to project directory
cd /edge-ai-suites/metro-ai-suite/image-based-video-search

# Create and activate virtual environment
python3 -m venv ./test-venv

source test-venv/bin/activate
```
### Install Requirements 
```bash
pip install -r ./test/requirements.txt
```

### Run All Tests with Coverage
```bash
# Note: You must temporarily modify server.py imports before running tests
# See "Important Notes" section below

# Run all tests with coverage
pytest test/ --cov=src/feature-matching --cov-report=term-missing

# Run all tests with HTML coverage report
pytest test/ --cov=src/feature-matching --cov-report=html
```

### Run Individual Test Files
```bash
pytest test/test_encoder.py -v
pytest test/test_milvus_utils.py -v
pytest test/test_schemas.py -v
pytest test/test_server.py -v
```

### Run Specific Test
```bash
pytest test/test_encoder.py::TestBase64ImageProcessor::test_processor_initialization_default_size -v
```

## 📊 Current Test Results

- **Total Tests:** 92
- **Passing:** 88 (95.7%)
- **Failing:** 4 (4.3%)
- **Overall Coverage:** 95%

### Coverage by Module
- encoder.py: 100%
- milvus_utils.py: 100%
- schemas.py: 100%
- server.py: 92%

## ⚠️ Important Notes

### Temporary Import Modification Required

Before running tests, you need to temporarily modify `src/feature-matching/server.py`:

**Change FROM (relative imports):**
```python
from .encoder import Base64ImageProcessor
from .milvus_utils import (...)
from .schemas import PayloadSchema, TensorSchema
```

**TO (absolute imports):**
```python
from encoder import Base64ImageProcessor
from milvus_utils import (...)
from schemas import PayloadSchema, TensorSchema
```

**Quick command to make this change:**
```bash
cd src/feature-matching
cp server.py server.py.bak  # Backup original
sed -i 's/from \.encoder import/from encoder import/g' server.py
sed -i 's/from \.milvus_utils import/from milvus_utils import/g' server.py
sed -i 's/from \.schemas import/from schemas import/g' server.py
```

**Restore after testing:**
```bash
cd src/feature-matching
mv server.py.bak server.py  # Restore original
```

### Why This Is Needed
The `src/feature-matching` directory uses hyphens (not valid in Python module names), so the tests add it to `sys.path` and import directly. The relative imports in `server.py` won't work in this configuration, so we temporarily convert them to absolute imports.

## 📁 Generated Reports

1. **htmlcov/index.html** - Interactive HTML coverage report

### View HTML Report
```bash
# Open in default browser
xdg-open htmlcov/index.html

# Or specify browser
firefox htmlcov/index.html
google-chrome htmlcov/index.html
```

## 🔧 Environment

- Python: 3.12.3
- Pytest: 8.4.2
- Virtual Env: test-venv
- Working Directory: `/edge-ai-suites/metro-ai-suite/image-based-video-search`

## 📚 Additional Resources

- **test/requirements.txt** - All test dependencies
- **test/conftest.py** - Pytest configuration


---

**Last Updated:** November 11, 2025
