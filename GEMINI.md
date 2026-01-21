# AI Assistant Instructions

This project uses comprehensive AI coding assistant instructions to ensure consistent code quality and adherence to project standards.

## 📋 Primary Instructions

All AI assistants (GitHub Copilot, Google Gemini, etc.) should follow:

**[.github/copilot-instructions.md](.github/copilot-instructions.md)**

This document contains:
- Project overview and architecture
- Code patterns and standards
- Backward compatibility requirements
- Testing requirements
- Documentation standards
- Development workflow

## 📚 Additional Context

For deeper understanding of the project structure and documentation:

**[docs/README.md](docs/README.md)** - Complete documentation index

## 🔑 Key Principles

1. **Backward Compatibility**: Existing installations must NEVER break
2. **Test Coverage**: All code changes require corresponding tests (502 tests, 100% pass rate)
3. **Type Safety**: Use mypy type hints throughout
4. **Code Quality**: Max complexity 10, flake8 compliant
5. **Documentation**: All classes and functions must have comprehensive docstrings
