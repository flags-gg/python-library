"""Flag types and data structures for the Flags.gg Python client."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Details:
    """Details about a feature flag."""
    name: str
    id: str


@dataclass
class FeatureFlag:
    """Represents a feature flag with its state and details."""
    enabled: bool
    details: Details
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FeatureFlag':
        """Create a FeatureFlag from a dictionary."""
        details_data = data.get('details', {})
        details = Details(
            name=details_data.get('name', ''),
            id=details_data.get('id', '')
        )
        return cls(
            enabled=data.get('enabled', False),
            details=details
        )
    
    def to_dict(self) -> dict:
        """Convert the FeatureFlag to a dictionary."""
        return {
            'enabled': self.enabled,
            'details': {
                'name': self.details.name,
                'id': self.details.id
            }
        }