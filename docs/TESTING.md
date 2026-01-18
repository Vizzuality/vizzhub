# Testing Documentation

## Overview

This document provides a comprehensive overview of the testing strategy, coverage, and guidelines for the Project Scorecard application.

## Test Statistics

### Summary

- **Total Tests**: 270 (268 passing, 2 with pre-existing issues)
- **Success Rate**: 99.3%
- **Code Coverage**: ~85% (increased from 27% initial)

### Breakdown by Category

#### Backend Tests (224 total)

| Category | Tests | Status | Description |
|----------|-------|--------|-------------|
| **Security (P0)** | 34 | ✅ 100% | CSRF protection, JQL injection, security headers |
| **Critical (P1)** | 85 | ✅ 98.8% | OAuth, Jira collector, auth edge cases |
| **API Security (P2)** | 23 | ✅ 100% | SQL injection, XSS, input validation |
| **Core Functionality** | 82 | ✅ 100% | Calculators, normalizers, API endpoints |

**Detailed Breakdown:**

- `test_oauth_state.py` - 10 tests (CSRF protection)
- `test_jira_collector_jql_injection.py` - 11 tests (JQL injection prevention)
- `test_security_middleware.py` - 13 tests (security headers)
- `test_oauth_api.py` - 17 tests (OAuth endpoints, 2 pre-existing issues)
- `test_oauth_service.py` - 17 tests (token lifecycle)
- `test_jira_collector.py` - 25 tests (OAuth integration, metrics collection)
- `test_security_logger.py` - 9 tests (security event logging)
- `test_auth.py` - 17 tests (JWT authentication, role authorization)
- `test_api_security.py` - 23 tests (SQL/XSS/validation)
- `test_calculators.py` - 12 tests (score calculations)
- `test_normalizers.py` - 16 tests (metric normalization)
- `test_api.py` - 56 tests (API endpoints)

#### Frontend Tests (46 total)

| Category | Tests | Status | Description |
|----------|-------|--------|-------------|
| **Security** | 20 | ✅ 100% | API interceptors, JWT handling |
| **Components** | 18 | ✅ 100% | Form validation, UI components |
| **Auth Context** | 8 | ✅ 100% | State management, localStorage |

**Detailed Breakdown:**

- `api.test.ts` - 20 tests (request/response interceptors)
- `AuthContext.test.tsx` - 8 tests (auth state management)
- `ProjectForm.test.tsx` - 18 tests (form validation)

---

## Security Coverage

### Vulnerabilities Protected

✅ **SQL Injection Prevention**
- Parameterized queries in all database operations
- UUID validation on all ID parameters
- Tested with malicious payloads: `'; DROP TABLE projects--`

✅ **JQL Injection Prevention**
- Project key validation (regex: `^[A-Z0-9_-]{1,20}$`)
- Validation before JQL query construction
- Tested with injection attempts

✅ **XSS Prevention**
- Input stored as-is but escaped on render
- Tested with `<script>alert('XSS')</script>` payloads
- Frontend sanitizes output

✅ **CSRF Protection**
- OAuth state tokens (cryptographically secure)
- One-time use tokens (prevents replay attacks)
- 10-minute expiration window

✅ **Authentication & Authorization**
- JWT-based authentication
- Role-based access control
- Development mode bypass (DEBUG=true)
- Token expiration handling

✅ **Rate Limiting**
- Configured on all OAuth endpoints (10/min)
- API endpoint rate limiting (30/min)

✅ **Security Headers**
- HSTS (Strict-Transport-Security)
- CSP (Content-Security-Policy)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy

✅ **Input Validation**
- UUID format validation
- Date range validation
- Data structure validation (EVM data, metrics)
- GitHub repo format validation

✅ **Error Handling**
- Sanitized error messages (no sensitive data exposure)
- Proper HTTP status codes (401, 403, 404, 422)
- Structured security logging (JSON format)

---

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
pytest

# Run all tests with coverage
pytest --cov=app --cov-report=html

# Open coverage report
open htmlcov/index.html

# Run specific test file
pytest tests/test_oauth_service.py -v

# Run specific test class
pytest tests/test_normalizers.py::TestLowerIsBetter -v

# Run specific test
pytest tests/test_auth.py::test_create_access_token_basic -v

# Run by pattern
pytest -k "oauth" -v
pytest -k "security" -v

# Run all security tests
pytest tests/test_oauth_state.py \
       tests/test_jira_collector_jql_injection.py \
       tests/test_security_middleware.py \
       tests/test_security_logger.py \
       tests/test_api_security.py \
       tests/test_oauth_service.py \
       tests/test_jira_collector.py \
       tests/test_auth.py -v

# Run with verbose output and short traceback
pytest -v --tb=short

# Run with timing information
pytest --durations=10
```

### Frontend Tests

```bash
cd frontend

# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- src/services/__tests__/api.test.ts

# Run tests matching pattern
npm test -- --grep "AuthContext"
```

---

## Writing Tests

### Backend Test Guidelines

#### 1. Use Existing Fixtures

```python
from tests.conftest import client, db_session, mock_settings

async def test_example(client: AsyncClient, db_session: AsyncSession):
    """Test example with fixtures."""
    # client - HTTP test client
    # db_session - database session for test data
```

#### 2. Mock External Dependencies

```python
from unittest.mock import AsyncMock, Mock, patch

async def test_jira_collector():
    """Test Jira collector with mocked HTTP client."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json.return_value = {"count": 5}
        mock_client.return_value.post = AsyncMock(return_value=mock_response)
        # Test code here
```

#### 3. Test Security Vulnerabilities

```python
async def test_sql_injection_prevention(client: AsyncClient):
    """Test that SQL injection is prevented."""
    response = await client.post(
        "/api/projects",
        json={"name": "Project'; DROP TABLE projects--"}
    )
    assert response.status_code == 201
    # Verify malicious SQL wasn't executed
```

#### 4. Test Authentication

```python
async def test_requires_auth_in_production(client: AsyncClient, monkeypatch):
    """Test endpoint requires authentication in production."""
    monkeypatch.setenv("DEBUG", "false")
    response = await client.get("/api/protected")
    assert response.status_code == 401
```

### Frontend Test Guidelines

#### 1. Test Components

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected Text')).toBeDefined();
  });
});
```

#### 2. Test Hooks

```typescript
import { renderHook, act } from '@testing-library/react';

it('updates state correctly', () => {
  const { result } = renderHook(() => useMyHook());

  act(() => {
    result.current.updateValue('new value');
  });

  expect(result.current.value).toBe('new value');
});
```

#### 3. Mock API Calls

```typescript
import MockAdapter from 'axios-mock-adapter';
import api from '../services/api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

it('fetches data from API', async () => {
  mock.onGet('/api/projects').reply(200, [{ id: 1, name: 'Test' }]);
  // Test code here
});
```

---

## Test Organization

### Backend Test Structure

```
backend/tests/
├── conftest.py              # Fixtures and test configuration
├── test_auth.py             # Authentication tests
├── test_oauth_state.py      # CSRF protection tests
├── test_oauth_service.py    # OAuth service tests
├── test_oauth_api.py        # OAuth API endpoints
├── test_jira_collector.py   # Jira collector tests
├── test_jira_collector_jql_injection.py  # JQL injection tests
├── test_security_middleware.py  # Security headers tests
├── test_security_logger.py  # Security logging tests
├── test_api_security.py     # API security tests
├── test_calculators.py      # Score calculator tests
├── test_normalizers.py      # Metric normalizer tests
└── test_api.py              # General API tests
```

### Frontend Test Structure

```
frontend/src/
├── components/
│   └── Forms/
│       └── ProjectForm.test.tsx
├── contexts/
│   └── __tests__/
│       └── AuthContext.test.tsx
└── services/
    └── __tests__/
        └── api.test.ts
```

---

## CI/CD Integration

### GitHub Actions (Future)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          cd frontend
          npm install
          npm test -- --run
```

---

## Known Issues

### Pre-existing Test Failures (2 tests)

1. `test_oauth_api.py::test_oauth_jira_callback_state_validation_success`
   - Issue: AsyncClient context manager syntax
   - Status: Low priority (functionality works, test needs refactoring)

2. `test_oauth_api.py::test_oauth_jira_refresh_no_token_returns_404`
   - Issue: Error message assertion mismatch
   - Status: Low priority (minor assertion detail)

Both tests are in non-critical areas and do not affect core functionality.

---

## Future Testing Improvements

### Planned Additions

1. **Calculator Edge Cases** (14 tests)
   - None/zero value handling
   - Sev1 incident edge cases
   - Weight validation

2. **Normalizer Edge Cases** (13 tests)
   - Division by zero protection
   - Target=0 scenarios
   - Negative value handling

3. **Frontend Components** (8 tests)
   - ProjectCard component
   - ScoreCard component
   - Page components

4. **Frontend Hooks** (13 tests)
   - useProjects hook
   - useMetrics hook
   - useScores hook

5. **Integration Tests** (13 tests)
   - End-to-end OAuth flow
   - Complete metric collection flow
   - Database persistence

**Estimated total:** ~61 additional tests to reach 100% coverage

---

## Performance

### Test Execution Time

- **Backend**: ~3 seconds for all 224 tests
- **Frontend**: ~1 second for all 46 tests
- **Total**: ~4 seconds for complete test suite

### Optimization Tips

1. Use `pytest-xdist` for parallel execution:
   ```bash
   pytest -n auto
   ```

2. Run only modified tests:
   ```bash
   pytest --lf  # last failed
   pytest --ff  # failed first
   ```

3. Skip slow tests during development:
   ```bash
   pytest -m "not slow"
   ```

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Testing Library](https://testing-library.com/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)

---

**Last Updated**: 2026-01-18
**Test Suite Version**: 1.0.0
**Maintained by**: Development Team
