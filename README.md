# Flags.gg Python Client

A Python client library for the [Flags.gg](https://flags.gg) feature flag management system. This library provides a simple interface for checking feature flags with built-in caching, circuit breaking, and environment variable overrides.

## Installation

```bash
pip install flags-gg
```

## Quick Start

```python
from flags import new_client

# Create a client with authentication
client = new_client(
    project_id="your-project-id",
    agent_id="your-agent-id", 
    environment_id="your-environment-id"
)

# Check if a feature is enabled
if client.is_("new-feature").enabled():
    # Feature is enabled
    print("New feature is active!")
else:
    # Feature is disabled
    print("New feature is not active")

# List all flags
flags = client.list()
for flag in flags:
    print(f"{flag.details.name}: {'enabled' if flag.enabled else 'disabled'}")
```

## Features

- **Simple API**: Easy-to-use interface for checking feature flags
- **Caching**: Built-in caching with SQLite (persistent) or in-memory options
- **Circuit Breaker**: Protects against API failures with automatic fallback
- **Environment Overrides**: Override flags locally using environment variables
- **Thread-Safe**: Safe for use in multi-threaded applications
- **Zero Dependencies**: Only requires the `requests` library

## Configuration

### Authentication

The client requires three authentication parameters:
- `project_id`: Your Flags.gg project ID
- `agent_id`: Your agent ID
- `environment_id`: The environment ID (e.g., "production", "staging")

### Cache Options

By default, the client uses SQLite for persistent caching:

```python
# Use SQLite cache (default)
client = new_client(
    project_id="...",
    agent_id="...",
    environment_id="...",
    sqlite_path="/path/to/cache.db"  # Optional, defaults to /tmp/flags.db
)

# Use in-memory cache
client = new_client(
    project_id="...",
    agent_id="...",
    environment_id="...",
    use_memory_cache=True
)
```

### Advanced Configuration

```python
client = new_client(
    # Authentication
    project_id="your-project-id",
    agent_id="your-agent-id",
    environment_id="your-environment-id",
    
    # API Configuration
    base_url="https://custom-api.flags.gg",  # Custom API endpoint
    timeout=30,  # Request timeout in seconds (default: 10)
    max_retries=5,  # Maximum retry attempts (default: 3)
    
    # Cache Configuration  
    use_memory_cache=True,  # Use in-memory cache instead of SQLite
    
    # Custom User-Agent
    user_agent="MyApp/1.0"
)
```

## Environment Variable Overrides

You can override any flag locally using environment variables with the `FLAGS_` prefix:

```bash
# Override a flag named "new-feature"
export FLAGS_NEW_FEATURE=true

# Works with different naming conventions
export FLAGS_MY_FEATURE=true  # Maps to "my-feature", "my_feature", or "my feature"
```

Environment variables take precedence over API values, making them useful for local development and testing.

## Caching

The library includes two cache implementations:

### SQLite Cache (Default)
- Persists across application restarts
- Stored in `/tmp/flags.db` by default
- Thread-safe with proper locking
- Automatic cleanup of expired entries

### Memory Cache
- Faster performance
- Data lost on application restart
- Lower overhead for short-lived applications

Cache data is automatically refreshed based on the TTL provided by the Flags.gg API.

## Circuit Breaker

The built-in circuit breaker protects your application from API failures:

- Opens after a configurable number of failures (default: 3)
- Prevents cascading failures by short-circuiting API calls
- Automatically closes after a recovery timeout (10 seconds)
- Falls back to cached values when open

## Thread Safety

All operations are thread-safe:
- Memory cache uses read/write locks
- SQLite cache uses connection pooling and transactions
- Client operations are protected with appropriate locking

## API Reference

### Client Creation

```python
from flags import new_client

client = new_client(**options)
```

### Checking Flags

```python
# Check if a flag is enabled
if client.is_("feature-name").enabled():
    # Feature is enabled
    pass

# The is_() method returns a FlagResult object
result = client.is_("feature-name")
enabled = result.enabled()  # Returns bool
```

### Listing Flags

```python
# Get all flags
flags = client.list()

# Each flag has:
# - flag.enabled: bool
# - flag.details.name: str  
# - flag.details.id: str
```

## Error Handling

The client handles errors gracefully:

```python
# API failures fall back to cached values
result = client.is_("feature")  # Uses cache if API fails

# Invalid flags return disabled
result = client.is_("non-existent-flag")
assert not result.enabled()  # Always returns False for unknown flags
```

## Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=flags --cov-report=html
```

### Code Style

```bash
# Format code
black flags/ tests/

# Lint code
flake8 flags/ tests/

# Type checking
mypy flags/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/flags-gg/python-flags/issues).