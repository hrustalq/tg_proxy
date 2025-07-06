# Telegram Proxy Bot Test Suite

This directory contains comprehensive tests for the Telegram Proxy Bot, ensuring 100% compliance with all user stories and functionality requirements.

## Test Structure

### Test Files Overview

- **`conftest.py`** - Test configuration, fixtures, and setup
- **`test_utils.py`** - Unit tests for utility functions
- **`test_database.py`** - Unit tests for database models and operations
- **`test_config.py`** - Tests for configuration management
- **`test_subscription.py`** - Tests for subscription logic and user stories compliance
- **`test_bot_handlers.py`** - Integration tests for bot command handlers
- **`test_payment.py`** - Tests for payment processing functionality

### Test Categories

#### Unit Tests (`@pytest.mark.unit`)
- Test individual functions and components in isolation
- Fast execution, no external dependencies
- Cover edge cases and error conditions

#### Integration Tests (`@pytest.mark.integration`)
- Test complete workflows and bot handlers
- Use real database connections (in-memory SQLite)
- Test user story compliance end-to-end

#### Database Tests (`@pytest.mark.database`)
- Test database models, relationships, and operations
- Use temporary test databases
- Verify data persistence and integrity

## User Story Coverage

### Epic 1: User Onboarding & Registration
- ✅ **US-001**: First Bot Interaction - `test_bot_handlers.py::TestStartCommand`
- ✅ **US-002**: Free Trial Access - `test_bot_handlers.py::TestFreeTrialCallback`

### Epic 2: Subscription Management
- ✅ **US-003**: Subscription Purchase - `test_bot_handlers.py::TestSubscribeCallback`
- ✅ **US-004**: Subscription Renewal - `test_payment.py::TestSuccessfulPayment`
- ✅ **US-005**: Subscription Status Check - `test_bot_handlers.py::TestStatusCommand`

### Epic 3: Proxy Configuration Management
- ✅ **US-006**: Proxy Configuration Access - `test_bot_handlers.py::TestConfigCommand`
- ✅ **US-007**: Proxy Configuration Generation - `test_bot_handlers.py::TestConfigCommand`
- ✅ **US-008**: Proxy Configuration Refresh - `test_bot_handlers.py::TestRefreshConfigCallback`

### Epic 4: Payment Processing
- ✅ **US-009**: Payment Pre-validation - `test_payment.py::TestPreCheckoutQuery`
- ✅ **US-010**: Payment Confirmation - `test_payment.py::TestSuccessfulPayment`

### Epic 5: Multi-Server Support
- ✅ **US-011**: Multiple Proxy Servers - `test_utils.py::TestGetProxyConfigText`
- ✅ **US-012**: Server Configuration Format - `test_utils.py::TestGetProxyConfigText`

### Epic 6: Security & Access Control
- ✅ **US-013**: Subscription Validation - `test_subscription.py::TestSubscriptionValidation`
- ✅ **US-014**: Secure Secret Generation - `test_utils.py::TestGenerateProxySecret`

### Epic 7: User Experience & Navigation
- ✅ **US-015**: Inline Keyboard Navigation - `test_bot_handlers.py` (various tests)
- ✅ **US-016**: Clear Status Messages - `test_bot_handlers.py::TestHelpCommand`

### Epic 8: Database & Data Management
- ✅ **US-017**: User Data Persistence - `test_database.py::TestUserModel`
- ✅ **US-018**: Payment Records - `test_database.py::TestPaymentModel`

## Running Tests

### Install Test Dependencies
```bash
pip install -r requirements-test.txt
```

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Database tests only
pytest -m database

# Slow tests (excluded by default)
pytest -m slow
```

### Run Tests with Coverage
```bash
pytest --cov=. --cov-report=html
```

### Run Specific Test Files
```bash
# Test utilities only
pytest tests/test_utils.py

# Test bot handlers only
pytest tests/test_bot_handlers.py

# Test specific function
pytest tests/test_utils.py::TestGenerateProxySecret::test_generates_32_character_secret
```

### Run Tests with Verbose Output
```bash
pytest -v
```

## Test Data and Fixtures

### User Fixtures
- **`test_user`** - Basic user without subscription
- **`subscribed_user`** - User with active subscription (15 days remaining)
- **`expired_user`** - User with expired subscription (1 day ago)
- **`trial_user`** - User who previously used free trial

### Database Fixtures
- **`test_db`** - Temporary SQLite database for testing
- **`db_session`** - Database session for each test
- **`test_proxy_config`** - Sample proxy configuration
- **`test_payment`** - Sample payment record

### Mock Fixtures
- **`mock_bot`** - Mock Telegram bot instance
- **`mock_message`** - Mock Telegram message
- **`mock_callback_query`** - Mock callback query
- **`test_settings`** - Test configuration settings

## Test Quality Metrics

### Coverage Requirements
- **Minimum Line Coverage**: 90%
- **Minimum Branch Coverage**: 85%
- **Critical Functions**: 100% coverage required

### Test Assertions
- All user stories have corresponding test assertions
- Edge cases and error conditions are tested
- Database integrity is verified
- API responses are validated

### Performance Requirements
- Unit tests: < 1 second per test
- Integration tests: < 5 seconds per test
- Total test suite: < 60 seconds

## Continuous Integration

Tests are designed to run in CI/CD environments with:
- Parallel test execution
- Temporary database creation
- Mock external services
- Deterministic test data

### Environment Variables for Testing
```bash
# Optional: Set test-specific database URL
TEST_DATABASE_URL=sqlite:///test.db

# Optional: Set test bot token (use dummy value)
TEST_BOT_TOKEN=test_token_for_ci
```

## Debugging Tests

### Common Issues

1. **Database Connection Errors**
   - Ensure temporary database is created correctly
   - Check that database fixtures are properly yielded

2. **Async Test Issues**
   - Use `pytest-asyncio` for async test support
   - Ensure all async fixtures are properly awaited

3. **Mock Configuration**
   - Verify all dependencies are mocked correctly
   - Check that mock return values match expected types

### Debugging Commands
```bash
# Run with debugging output
pytest -s --tb=long

# Run single test with full output
pytest -s -vv tests/test_specific.py::test_function

# Drop into debugger on failure
pytest --pdb
```

## Test Maintenance

### Adding New Tests
1. Follow existing naming conventions
2. Use appropriate test markers (`@pytest.mark.unit`, etc.)
3. Include user story references in docstrings
4. Ensure proper fixture usage
5. Add assertions for all expected behaviors

### Updating Tests
1. Update tests when user stories change
2. Maintain backward compatibility when possible
3. Update documentation for new test categories
4. Ensure coverage requirements are met

### Test Data Management
1. Use factories for generating test data
2. Keep test data minimal and focused
3. Clean up test data after each test
4. Use realistic but safe test values

## Security Considerations

- Test data does not contain real credentials
- Mock external API calls to prevent actual charges
- Use temporary databases that are automatically cleaned
- Ensure test isolation to prevent data leakage

## Performance Monitoring

Tests include performance assertions for:
- Database query efficiency
- API response times
- Memory usage in critical paths
- Concurrent user simulation

Run performance tests with:
```bash
pytest -m performance --benchmark-only
```