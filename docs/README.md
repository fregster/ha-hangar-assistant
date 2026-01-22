# Hangar Assistant Documentation

## 📚 Documentation Index

### Getting Started
- [Main README](../README.md) - Project overview, installation, and quick start
- [CHANGELOG](../CHANGELOG.md) - Version history and release notes

### User Documentation
- [Entity Descriptions](ENTITY_DESCRIPTIONS.md) - Tooltips and descriptions for all entities
- [Automation Examples](HANGAR_AUTOMATION_EXAMPLES.md) - Practical automation scenarios

### Development Documentation

#### Code Quality
- [Code Quality Tests](CODE_QUALITY_TESTS.md) - Test suite for code quality validation
- [Code Quality Review](development/CODE_QUALITY_REVIEW.md) - Code quality audit results
- [Code Quality Fixes](development/CODE_QUALITY_FIXES.md) - Summary of fixes applied

#### Technical Implementation
- [Cache Consolidation Summary](development/CACHE_CONSOLIDATION_SUMMARY.md) - Unified cache manager implementation
- [Cache Migration Guide](development/CACHE_MIGRATION.md) - Migration from legacy caching

### Architecture & Planning
- [Hangar Architecture Plan](planning/HANGAR_ARCHITECTURE_PLAN.md) - Hangar system design and implementation
- [Integration Architecture](planning/INTEGRATION_ARCHITECTURE.md) - External integrations design
- [OpenWeatherMap Integration](planning/OPENWEATHERMAP_INTEGRATION_PLAN.md) - OWM API integration plan

### Release Notes
- [Version 2601.2.0](releases/RELEASE_NOTES_2601.2.0.md)

## 📁 Repository Structure

```
ha-hangar-assistant/
├── README.md                      # Main project documentation
├── CHANGELOG.md                   # Version history
├── LICENSE                        # MIT License
├── hacs.json                      # HACS integration manifest
├── pytest.ini                     # Test configuration
├── requirements.txt               # Python dependencies (dev & test)
├── requirements_test.txt          # Legacy (use requirements.txt)
├── .github/                       # GitHub workflows and copilot instructions
├── custom_components/             # Integration source code
│   └── hangar_assistant/
│       ├── __init__.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── select.py
│       ├── config_flow.py
│       ├── const.py
│       ├── manifest.json
│       ├── strings.json
│       ├── services.yaml
│       ├── brand/               # Branding assets
│       ├── dashboard_templates/ # Dashboard YAML templates
│       ├── prompts/            # AI system prompts
│       ├── references/         # Aviation reference materials
│       ├── translations/       # Language packs
│       └── utils/              # Utility modules
├── docs/                         # Documentation (you are here!)
│   ├── development/            # Development notes and reviews
│   ├── planning/              # Architecture and design docs
│   └── releases/              # Release notes archive
├── tests/                       # Comprehensive test suite
└── scripts/                     # Development scripts
```

## 🔧 Development Workflow

1. **Code Quality**: Run `scripts/run_validate_locally.sh` before commits
2. **Testing**: `pytest tests/` (502 tests, 100% pass rate required)
3. **Type Checking**: `mypy custom_components/hangar_assistant`
4. **Linting**: `flake8 custom_components/hangar_assistant`

## 📖 Contributing

See [.github/copilot-instructions.md](../.github/copilot-instructions.md) for:
- Code standards and patterns
- Architecture principles
- Backward compatibility requirements
- Testing requirements
- Documentation standards

## 🔗 External Links

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Documentation](https://hacs.xyz/)
- [Project Repository](https://github.com/yourusername/ha-hangar-assistant)
