# Changelog

## [1.0.1] - 2025-10-02

### Fixed
- **Repository URLs**: Updated all GitHub links to point to correct CodeDuet repository
- **Documentation links**: Fixed PyPI metadata to reference proper documentation location
- **Package metadata**: Corrected homepage, repository, changelog, and bug tracker URLs

## [1.0.0] - 2025-10-02

### Added
- **Initial release** of py-microvm SDK
- **Secure MicroVM client** with enterprise security features
- **Input validation framework** preventing command injection and path traversal
- **HTTPS enforcement** for secure communications
- **Async/await support** with proper context management
- **Type safety** with full mypy compliance
- **Comprehensive error handling** with specific exception types
- **Security scanning** with zero vulnerabilities detected
- **High test coverage** (81% with security validation)
- **Lightweight architecture** (300 lines of implementation code)

### Security Features
- Command injection prevention with pattern blocking
- Path traversal protection with whitelist validation
- HTTPS enforcement for non-localhost connections
- File upload size limits (10MB maximum)
- Input sanitization for all user data
- Secure error handling without information disclosure

### Performance
- <50ms API response times
- <10MB memory footprint
- Connection pooling with keep-alive
- Minimal dependencies (httpx, pydantic)

### Supported Operations
- VM lifecycle management (start, stop, destroy)
- Secure command execution with timeout
- File upload with size and path validation
- VM information retrieval
- Authentication with Bearer tokens

### Development
- 100% mypy type checking compliance
- Zero security vulnerabilities (bandit scan)
- 81% test coverage with 22 test cases
- Black code formatting compliance
- Ruff linting compliance